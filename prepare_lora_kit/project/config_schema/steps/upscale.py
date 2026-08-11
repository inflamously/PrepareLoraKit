"""Editable config fields for UpscaleStep."""
from __future__ import annotations

from prepare_lora_kit.project.config_schema.fields import FieldSpec, _number, _select
from prepare_lora_kit.steps.upscale.seedvr2_adapter import downloaded_dit_models
from prepare_lora_kit.steps.upscale.seedvr2_catalog import dit_model_choices

STEP_TYPE = "UpscaleStep"

FIELDS: list[FieldSpec] = [
    _select("upscale_model", "Upscale model", [
        ("seedvr2", "SeedVR2"), ("lanczos", "Lanczos"), ("custom", "Custom"),
    ]),
    _number("upscale_target", "Target side (px)", "int", minimum=1, step=64),
    _number("upscale_highlight_threshold", "Highlight threshold (px)", "int", minimum=1, step=64),
    _number("hallucination_ssim_threshold", "Hallucination SSIM", "float",
            minimum=0, maximum=1, step=0.05),
    _select("seedvr2_dit_model", "SeedVR2 DiT model", dit_model_choices(),
            allow_custom=True, nullable=True,
            placeholder="local_checkpoint.safetensors",
            help="Auto picks the highest-quality model your VRAM can hold. Anything "
                 "not yet downloaded is fetched on first use."),
    _select("seedvr2_model_residency", "SeedVR2 residency", [
        ("auto", "Auto"), ("gpu", "GPU"), ("cpu", "CPU"),
    ]),
    _number("seedvr2_batch_size", "SeedVR2 batch size", "int", minimum=1, step=1),
]

# Which checkpoints are on disk changes between runs, so this option cannot be
# baked in at import time — see ..query.schema_payload.
OPTION_PROVIDERS = {
    "seedvr2_dit_model": lambda: dit_model_choices(downloaded_dit_models()),
}
