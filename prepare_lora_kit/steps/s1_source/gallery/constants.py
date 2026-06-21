from __future__ import annotations

# ── tkinter gallery review: shared constants ────────────────────────────────────

_THUMB = 200  # thumbnail edge in px
_PREVIEW = 720  # full-image hover preview edge in px
_COLS = 4  # grid columns
_PASS = "#2e7d32"  # green border = keep
_FAIL = "#c62828"  # red border = reject

HOVER_TIMEOUT = 500  # milliseconds


def _quality_color(q: float) -> str:
    """Green→amber→red gradient for the overall quality number."""
    if q >= 66:
        return "#2e7d32"
    if q >= 40:
        return "#f9a825"
    return "#c62828"
