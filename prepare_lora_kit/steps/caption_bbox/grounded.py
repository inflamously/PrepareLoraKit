"""Grounded caption generation: observe → compose → gap-fill.

Splits the single-shot VLM caption into prompt passes over the *same*
already-loaded model, so accuracy comes from grounding the caption in observed
facts rather than from a bigger model:

- **A. OBSERVE** — list only-visible facts under fixed headings (the accuracy pass).
- **B. COMPOSE** — write one fluent caption from those facts + bbox placement.
- **C. GAP-FILL** — *conditional and additive*: only when a cheap text signal says
  the draft is thin, ask the model for the elements it omitted and merge them in
  Python (:mod:`.gap_fill`). It cannot reword or drop what the draft already says.

Used only for prompt-capable (``image-text-to-text``) runtimes; the caller in
``vlm.CaptionRuntime.caption_image`` falls back to the single pass for classic
``image-to-text`` models, which cannot follow multi-turn instructions. Each stage
degrades gracefully: an empty/degenerate result falls back to the prior stage so the
pipeline never returns worse than a single pass.
"""
from __future__ import annotations

from typing import Any, Callable

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.steps.caption_bbox import caption_text, gap_fill
from prepare_lora_kit.steps.caption_bbox import prompts as cap_utils

# The observe pass emits a headed fact list, which needs more room than a caption.
_OBSERVE_MIN_TOKENS = 320
# The gap pass emits at most three short noun phrases, never prose.
_GAP_MAX_TOKENS = 48

# When the human has decomposed the image into this many labelled regions — or one
# label this descriptive — their labels are better grounding than anything the model
# can observe about itself, so the observe pass is skipped.
_MIN_ANNOTATIONS = 2
_MIN_SOLO_LABEL_WORDS = 4


def _degenerate(text: str) -> bool:
    return len(text.strip()) < 3


def _labels(annotation_lines: list[dict] | tuple) -> list[str]:
    labels = []
    for ann in annotation_lines or ():
        label = str((ann.get("label") if isinstance(ann, dict) else ann) or "").strip()
        if label:
            labels.append(label)
    return labels


def _annotations_suffice(annotation_lines: list[dict] | tuple) -> bool:
    """True when region labels can stand in for the observe pass.

    Region labels are human-authored (and hand-editable in the UI), so where they
    exist they are strictly better grounding than the model's own observations —
    and skipping the pass saves a whole image encode, which is what a pass actually
    costs. A single terse tag ("hat") says too little about the image as a whole to
    qualify; the word count is the only signal available for telling a real region
    caption from a bare marker.
    """
    labels = _labels(annotation_lines)
    if len(labels) >= _MIN_ANNOTATIONS:
        return True
    return bool(labels) and len(caption_text.content_words(labels[0])) >= _MIN_SOLO_LABEL_WORDS


def _note_pass(runtime: Any, stage: str) -> None:
    """Record a generation pass for the report, if the runtime keeps that tally.

    ``runtime`` is duck-typed here (tests and the region captioner pass their own),
    so pass accounting stays optional rather than part of the contract.
    """
    note = getattr(runtime, "note_pass", None)
    if note is not None:
        note(stage)


def generate_grounded_caption(
        runtime: Any,
        image: Any,
        annotation_lines: list[dict],
        concept_token: str | None,
        *,
        style_mode: bool,
        max_new_tokens: int = 200,
        cancel_check: CancelCheck | None = None,
        emit: Callable[[str, str], None] | None = None,
) -> str:
    """Run the observe → compose → verify pipeline and return the final caption.

    ``runtime`` must expose ``run_prompt(image, prompt, *, max_new_tokens)`` and a
    ``caption_prompt`` attribute (the optional custom compose template).
    """
    def _emit(stage: str, message: str) -> None:
        if emit is not None:
            emit(stage, message)

    # Optional like ``note_pass``: the runtime is duck-typed at this boundary.
    domain_brief = getattr(runtime, "domain_brief", None)

    # A. OBSERVE — the grounding pass, skipped when the human already supplied the
    # facts. An empty ``facts`` tells build_compose_prompt to switch to its
    # annotation-led grounding section.
    facts = ""
    if not _annotations_suffice(annotation_lines):
        _emit("observing", "Observing visible details")
        facts = runtime.run_prompt(
            image,
            cap_utils.build_observe_prompt(annotation_lines, domain_brief=domain_brief),
            max_new_tokens=max(max_new_tokens, _OBSERVE_MIN_TOKENS),
        )
        _note_pass(runtime, "observe")
        check_cancel(cancel_check)

    # B. COMPOSE — fluent caption from the observed or annotated facts.
    _emit("composing", "Composing caption")
    draft = runtime.run_prompt(
        image,
        cap_utils.build_compose_prompt(
            facts,
            annotation_lines,
            concept_token,
            style_mode=style_mode,
            template=runtime.caption_prompt,
            domain_brief=domain_brief,
        ),
        max_new_tokens=max_new_tokens,
    )
    _note_pass(runtime, "compose")
    if _degenerate(draft):
        # Extremely unlikely for a working prompted model; fall back to a plain
        # single-pass caption rather than returning the headed fact list.
        draft = runtime.run_prompt(
            image,
            cap_utils.build_full_image_prompt(
                annotation_lines, concept_token, template=runtime.caption_prompt,
                domain_brief=domain_brief,
            ),
            max_new_tokens=max_new_tokens,
        )
        _note_pass(runtime, "compose_fallback")
    check_cancel(cancel_check)

    # C. GAP-FILL — additive, and only when the draft looks thin. A good draft skips
    # the pass entirely, which is the whole saving: on a VLM the cost of a pass is
    # dominated by re-encoding the image, not by the tokens it decodes.
    if gap_fill.needs_gap_pass(draft, annotation_lines) is None:
        return draft

    _emit("verifying", "Checking for missing details")
    missing = runtime.run_prompt(
        image,
        cap_utils.build_gap_prompt(draft),
        max_new_tokens=_GAP_MAX_TOKENS,
    )
    _note_pass(runtime, "gap")
    return gap_fill.merge_missing_phrases(draft, gap_fill.parse_gap_phrases(missing))
