"""Caption cleanup, validation, and spot-check display for Step 5."""
from __future__ import annotations

from pathlib import Path
import random

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.utils import caption as cap_utils
from prepare_lora_kit.report import reporter


def clean_caption_for_mode(
    caption: str,
    path: Path,
    concept_token: str | None,
    *,
    style_mode: bool,
) -> str:
    caption = cap_utils.strip_boilerplate(caption)

    if not style_mode and concept_token:
        if not cap_utils.token_present(caption, concept_token):
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
        missing_token = cap_utils.verify_token_consistency(captions, concept_token)
        if missing_token:
            reporter.warn(f"Token '{concept_token}' missing in {len(missing_token)} captions:")
        for p in missing_token:
            check_cancel(cancel_check)
            reporter.warn(f"  {Path(p).name}")

    short = (
        [p for p, c in captions.items() if not cap_utils.caption_length_ok(c, min_chars=10)]
        if "validate_captions" in enabled
        else []
    )
    long_ = (
        [p for p, c in captions.items() if not cap_utils.caption_length_ok(c, max_chars=600)]
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
