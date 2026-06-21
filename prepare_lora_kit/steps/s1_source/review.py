from __future__ import annotations
from pathlib import Path

from ...utils import report as rpt
from .gallery import _gallery_review


def _manual_review(path: Path, score_info: dict) -> str:
    """Show image + scores; return 'keep', 'reject', or 'flag'."""
    try:
        import easygui
        from PIL import Image as PILImage

        PILImage.open(path).show()

        lines = [f"File: {path.name}\n"]
        for k, v in score_info["scores"].items():
            val_str = f"{v}" if v is not None else "n/a"
            lines.append(f"  {k:<14}: {val_str}")

        msg = "\n".join(lines)
        if score_info["auto_reasons"]:
            msg += f"\n\nAuto-flags: {', '.join(score_info['auto_reasons'])}"

        choice = easygui.buttonbox(msg, title="Step 1 — Review Image",
                                   choices=["Keep", "Reject", "Flag for later"])
        if choice == "Keep":
            return "keep"
        if choice == "Reject":
            return "reject"
        return "flag"

    except ImportError:
        rpt.warn(f"easygui not available. Terminal fallback: {path.name}")
        print(f"\n  {path}")
        _show_scores_terminal(score_info)
        ans = input("  [k]eep / [r]eject / [f]lag? ").strip().lower()
        return {"k": "keep", "r": "reject", "f": "flag"}.get(ans[0] if ans else "k", "keep")


def _show_scores_terminal(score_info: dict) -> None:
    parts = [f"{k}={v}" for k, v in score_info["scores"].items() if v is not None]
    print(f"    {' '.join(parts)}")


def _review_gallery_or_fallback(scored: list[tuple[Path, dict]]) -> dict[str, str]:
    """Try the tkinter gallery; on any failure fall back to per-image review."""
    if not scored:
        return {}
    try:
        return _gallery_review(scored)
    except Exception as exc:
        rpt.warn(f"Gallery unavailable ({exc}); falling back to one-by-one review.")

    decisions: dict[str, str] = {}
    for path, info in scored:
        decisions[str(path)] = _manual_review(path, info)
    return decisions
