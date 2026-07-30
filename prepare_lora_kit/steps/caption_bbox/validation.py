"""Caption cleanup, validation, and spot-check display for CaptionBboxStep."""
from __future__ import annotations

import random
from pathlib import Path

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.report import reporter
from prepare_lora_kit.steps.caption_bbox import caption_text as cap_text
from prepare_lora_kit.steps.caption_bbox.gap_fill import merge_missing_phrases


def _label_text(label: str, concept_token: str | None) -> str:
    """The descriptive part of a region label, without the concept token.

    A region captioned in the UI has already had the token applied to its own crop
    sidecar (``artifacts._update_bbox_caption`` writes ``"<token>, <caption>"``), so
    the label can arrive carrying it. The token belongs once, at the head of the
    caption, which is the job of the check below — re-inserting it mid-caption here
    would both read wrong and defeat that check.
    """
    parts = [part.strip() for part in label.split(",")]
    if concept_token:
        parts = [part for part in parts if part.lower() != concept_token.strip().lower()]
    return ", ".join(part for part in parts if part)


# A region caption long enough to be a description in its own right is never appended:
# tacking it onto the end produces a second, competing description of the same thing
# rather than a repaired caption. Those are reported instead, so the miss is visible
# without the caption paying for it.
_MAX_ENFORCED_WORDS = 6


def enforce_region_labels(
    caption: str,
    annotations: list | tuple,
    path: Path | None = None,
    *,
    concept_token: str | None = None,
) -> str:
    """Re-insert a human region label the caption genuinely dropped.

    The compose prompt declares region labels ground truth, but an instruction is
    not a guarantee — this is the check behind it. It is deliberately reluctant: a
    label is appended only when the caption does not mention the thing it names at
    all (:func:`caption_text.mentions`) *and* is short enough to read as a repair
    rather than a second description. A duplicate is worse than a paraphrase — it
    dilutes the caption for the text encoder.
    """
    labels = [
        _label_text(str(ann.get("label") or "").strip(), concept_token)
        for ann in annotations or ()
        if isinstance(ann, dict)
    ]
    labels = [label for label in labels if label]
    if not labels:
        return caption

    missing = [label for label in labels if not cap_text.mentions(caption, label)]
    appendable = [label for label in missing
                  if len(cap_text.content_words(label)) <= _MAX_ENFORCED_WORDS]

    for label in missing:
        if label not in appendable and path is not None:
            reporter.warn(
                f"Annotated region missing from caption for {path.name}, too long to "
                f"append verbatim: {label!r}"
            )
    if not appendable:
        return caption

    merged = merge_missing_phrases(caption, appendable)
    if merged != caption and path is not None:
        reporter.warn(f"Annotated region missing from caption for {path.name} — appending label.")
    return merged


def clean_caption_for_mode(
    caption: str,
    path: Path,
    concept_token: str | None,
    *,
    style_mode: bool,
    annotations: list | tuple = (),
) -> str:
    caption = cap_text.strip_boilerplate(caption)
    caption = enforce_region_labels(caption, annotations, path, concept_token=concept_token)

    if not style_mode and concept_token and not cap_text.token_present(caption, concept_token):
        reporter.warn(f"Concept token missing in caption for {path.name} — appending.")
        caption = f"{concept_token}, {caption}"

    return caption


def validate_captions(
    captions: dict[str, str],
    concept_token: str | None,
    *,
    style_mode: bool,
    enabled: set[str],
    cancel_check: CancelCheck | None,
) -> tuple[list[str], list[str], list[str]]:
    missing_token: list[str] = []
    if "validate_captions" in enabled and not style_mode and concept_token:
        missing_token = cap_text.verify_token_consistency(captions, concept_token)
        if missing_token:
            reporter.warn(f"Token '{concept_token}' missing in {len(missing_token)} captions:")
        for p in missing_token:
            check_cancel(cancel_check)
            reporter.warn(f"  {Path(p).name}")

    short = (
        [p for p, c in captions.items() if not cap_text.caption_length_ok(c, min_chars=10)]
        if "validate_captions" in enabled
        else []
    )
    long_ = (
        [p for p, c in captions.items() if not cap_text.caption_length_ok(c, max_chars=600)]
        if "validate_captions" in enabled
        else []
    )
    if short:
        reporter.warn(f"{len(short)} captions suspiciously short (< 10 chars)")
    if long_:
        reporter.warn(f"{len(long_)} captions very long (> 600 chars)")

    return missing_token, short, long_


def render_spot_check(
    captions: dict[str, str],
    spot_check_pct: float,
    *,
    enabled: set[str],
    cancel_check: CancelCheck | None,
) -> list[tuple[str, str]]:
    if "validate_captions" not in enabled or not captions:
        return []

    n_check = max(1, int(len(captions) * spot_check_pct))
    sample = random.sample(list(captions.items()), min(n_check, len(captions)))

    from rich import box
    from rich.table import Table

    t = Table(title=f"Spot-check ({n_check} / {len(captions)})", box=box.SIMPLE_HEAVY)
    t.add_column("File", style="cyan", max_width=35)
    t.add_column("Caption", style="white")
    for p, c in sample:
        check_cancel(cancel_check)
        t.add_row(Path(p).name, c[:120] + ("…" if len(c) > 120 else ""))
    reporter.console.print(t)
    return sample
