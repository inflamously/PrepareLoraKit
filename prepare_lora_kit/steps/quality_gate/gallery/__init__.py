"""tkinter gallery review — see window.py for the entry point."""
from __future__ import annotations

from typing import Any

__all__ = ["_gallery_review"]


def __getattr__(name: str) -> Any:
    if name == "_gallery_review":
        from prepare_lora_kit.steps.quality_gate.gallery.window import _gallery_review

        return _gallery_review
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
