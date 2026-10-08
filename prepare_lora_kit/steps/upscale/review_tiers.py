"""Group upscale candidates into fixed min-side tiers for bulk review decisions."""
from __future__ import annotations

REVIEW_TIER_PX = 256


def tier_for(min_side: int | None) -> tuple[int, int] | None:
    """Return the inclusive ``(lo, hi)`` min-side range ``min_side`` falls into.

    Tiers are ``REVIEW_TIER_PX`` wide and start at 0, e.g. ``(512, 767)``.
    An unknown size has no tier.
    """
    if min_side is None:
        return None
    lo = max(0, min_side) // REVIEW_TIER_PX * REVIEW_TIER_PX
    return lo, lo + REVIEW_TIER_PX - 1
