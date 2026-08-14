"""One-shot relocation of pipeline entries written under an older canonical order.

A list is repaired only when it is valid under a layout this app actually shipped —
hence a lookup table of past layouts rather than a sort, which would also silently
"fix" a hand-shuffled list instead of raising.
"""
from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

from prepare_lora_kit.pipeline.configuration import step_slugs

#: Canonical slug orders this app has shipped, newest first. Add a full layout
#: here — not a diff — whenever ``StepDefinition.order`` changes, so a project
#: written by the previous release keeps loading. Entries are never removed
#: until we are willing to abandon projects that old.
LEGACY_SLUG_ORDERS: tuple[tuple[str, ...], ...] = (
    # Until upscale moved to second: it ran after quality_gate and curate, so
    # the only images it could rescue were ones they had already thrown away.
    (
        "import",
        "quality_gate",
        "curate",
        "upscale",
        "caption_bbox",
        "caption_verifier",
        "vae_gate",
        "audit",
        "bucket_pools_check",
        "export",
    ),
)

Entry = tuple[str, bool]


def _is_ordered(slugs: Sequence[str], layout: Sequence[str]) -> bool:
    """Whether ``slugs`` is strictly increasing under ``layout``.

    An unknown or duplicated slug fails here rather than being papered over, so
    the caller's own error — "Unknown step", "Duplicate step type" — is the one
    the user sees.
    """
    positions: list[int] = []
    for slug in slugs:
        if slug not in layout:
            return False
        positions.append(layout.index(slug))
    return all(before < after for before, after in pairwise(positions))


def relocate_legacy_entries(entries: Sequence[Entry]) -> tuple[list[Entry], str | None]:
    """Return ``(slug, enabled)`` entries in canonical order, plus a note if moved.

    The note is ``None`` when nothing needed moving — including when the list is
    one we decline to touch, which is the case that goes on to raise.
    """
    canonical = step_slugs()
    slugs = [slug for slug, _enabled in entries]
    if _is_ordered(slugs, canonical):
        return list(entries), None

    for layout in LEGACY_SLUG_ORDERS:
        if not _is_ordered(slugs, layout):
            continue
        ordered = sorted(entries, key=lambda entry: canonical.index(entry[0]))
        return ordered, _relocation_note(slugs, [slug for slug, _enabled in ordered])

    return list(entries), None


def _relocation_note(before: Sequence[str], after: Sequence[str]) -> str:
    """Name the steps that jumped earlier — the ones a user would notice moving."""

    moved = [slug for slug in before if after.index(slug) < before.index(slug)]
    return (
        f"index.yaml used an older pipeline order — moved {', '.join(moved)} "
        f"to match this version and rewrote the file. No step was added, "
        f"removed, parked, or re-tuned."
    )


__all__ = ["LEGACY_SLUG_ORDERS", "relocate_legacy_entries"]
