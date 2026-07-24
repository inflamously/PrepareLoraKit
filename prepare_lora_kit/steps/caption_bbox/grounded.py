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
from prepare_lora_kit.steps.caption_bbox import gap_fill
from prepare_lora_kit.steps.caption_bbox import prompts as cap_utils

# The observe pass emits a headed fact list, which needs more room than a caption.
_OBSERVE_MIN_TOKENS = 320
# The gap pass emits at most three short noun phrases, never prose.
_GAP_MAX_TOKENS = 48


def _degenerate(text: str) -> bool:
    return len(text.strip()) < 3


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

    # A. OBSERVE — the grounding pass.
    _emit("observing", "Observing visible details")
    facts = runtime.run_prompt(
        image,
        cap_utils.build_observe_prompt(annotation_lines),
        max_new_tokens=max(max_new_tokens, _OBSERVE_MIN_TOKENS),
    )
    check_cancel(cancel_check)

    # B. COMPOSE — fluent caption from the observed facts.
    _emit("composing", "Composing caption")
    draft = runtime.run_prompt(
        image,
        cap_utils.build_compose_prompt(
            facts,
            annotation_lines,
            concept_token,
            style_mode=style_mode,
            template=runtime.caption_prompt,
        ),
        max_new_tokens=max_new_tokens,
    )
    if _degenerate(draft):
        # Extremely unlikely for a working prompted model; fall back to a plain
        # single-pass caption rather than returning the headed fact list.
        draft = runtime.run_prompt(
            image,
            cap_utils.build_full_image_prompt(
                annotation_lines, concept_token, template=runtime.caption_prompt
            ),
            max_new_tokens=max_new_tokens,
        )
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
    return gap_fill.merge_missing_phrases(draft, gap_fill.parse_gap_phrases(missing))
