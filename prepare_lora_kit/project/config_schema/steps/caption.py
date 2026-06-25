"""Editable config fields for CaptionStep."""
from __future__ import annotations

from ..fields import FieldSpec, _number, _select

STEP_TYPE = "CaptionStep"

_CAPTION_MODELS = [
    ("Qwen/Qwen2.5-VL-3B-Instruct", "Qwen2.5-VL 3B"),
    ("Qwen/Qwen2.5-VL-7B-Instruct", "Qwen2.5-VL 7B"),
    ("Qwen/Qwen2-VL-7B-Instruct", "Qwen2-VL 7B"),
]

FIELDS: list[FieldSpec] = [
    _select("caption_model_id", "Caption model", _CAPTION_MODELS, allow_custom=True, nullable=True,
            placeholder="Hugging Face model id"),
    _select("caption_model_task", "Caption task", [
        ("auto", "Auto"),
        ("image-text-to-text", "Image + text to text"),
        ("image-to-text", "Image to text"),
    ]),
    _select("vram_tier", "VRAM tier", [
        ("auto", "Auto"),
        ("low", "Low (≤16 GB, 4-bit)"),
        ("mid", "Mid (≤24 GB, 8-bit)"),
        ("high", "High (≤32 GB)"),
        ("max", "Max (≥32 GB)"),
    ]),
    _number("max_new_tokens", "Max new tokens", "int", minimum=1, step=10),
    _number("spot_check_pct", "Spot check fraction", "float", minimum=0, maximum=1, step=0.05),
]
