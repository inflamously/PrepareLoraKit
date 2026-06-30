"""Editable config fields for UpscaleStep."""
from __future__ import annotations

from ..fields import FieldSpec, _number, _select, _text

STEP_TYPE = "UpscaleStep"

FIELDS: list[FieldSpec] = [
    _select("upscale_model", "Upscale model", [
        ("seedvr2", "SeedVR2"), ("lanczos", "Lanczos"), ("custom", "Custom"),
    ]),
    _number("upscale_target", "Target side (px)", "int", minimum=1, step=64),
    _number("upscale_highlight_threshold", "Highlight threshold (px)", "int", minimum=1, step=64),
    _number("hallucination_ssim_threshold", "Hallucination SSIM", "float", minimum=0, maximum=1, step=0.05),
    _text("seedvr2_dit_model", "SeedVR2 DiT model", nullable=True,
          placeholder="seedvr2_ema_3b_fp8_e4m3fn.safetensors"),
    _select("seedvr2_model_residency", "SeedVR2 residency", [
        ("auto", "Auto"), ("gpu", "GPU"), ("cpu", "CPU"),
    ]),
    _number("seedvr2_batch_size", "SeedVR2 batch size", "int", minimum=1, step=1),
]
