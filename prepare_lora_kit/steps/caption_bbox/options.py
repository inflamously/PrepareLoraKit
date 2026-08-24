"""Transient options for one CaptionBboxStep execution."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from prepare_lora_kit.steps.caption_bbox.vlm import _DEFAULT_MAX_PIXELS


@dataclass(frozen=True, slots=True)
class CaptionBboxRunOptions:
    """Non-project inputs that customize one captioning run."""

    concept_token: str | None = None
    overwrite: bool = False
    max_pixels: int = _DEFAULT_MAX_PIXELS
    quantization: str | None = None
    status_callback: Callable[[dict[str, Any]], None] | None = None
