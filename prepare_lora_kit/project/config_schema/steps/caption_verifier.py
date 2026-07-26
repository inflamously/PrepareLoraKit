"""Config fields for CaptionVerifierStep."""
from __future__ import annotations

from prepare_lora_kit.project.config_schema.fields import (
    FieldSpec,
    _check,
    _number,
    _select,
    _text,
)
from prepare_lora_kit.steps.caption_verifier import catalog

STEP_TYPE = "CaptionVerifierStep"

_VRAM_TIERS = [
    ("auto", "Auto (match VRAM)"),
    ("low", "Low (<=16 GB, 4-bit + CPU offload)"),
    ("mid", "Mid (<=24 GB, 4-bit + CPU offload)"),
    ("high", "High (<=32 GB, CPU offload)"),
    ("max", "Max (>32 GB, fully resident)"),
]

FIELDS: list[FieldSpec] = [
    _select("t2i_model_id", "Image model", catalog.model_choices(),
            allow_custom=True,
            placeholder="Hugging Face repo id or .safetensors path",
            help="The model whose text encoder is probed. Auto picks by VRAM: "
                 "SDXL up to 16 GB, FLUX.2 klein above."),
    _select("vram_tier", "VRAM tier", _VRAM_TIERS,
            help="Quantization and CPU-offload strategy. Auto plans from free "
                 "VRAM, not total, so it survives a busy card."),
    _number("width", "Width", "int", minimum=256, maximum=4096, step=64,
            nullable=True, placeholder="model default"),
    _number("height", "Height", "int", minimum=256, maximum=4096, step=64,
            nullable=True, placeholder="model default"),
    _number("num_inference_steps", "Steps", "int", minimum=1, maximum=150, step=1,
            nullable=True, placeholder="model default"),
    _number("guidance_scale", "Guidance", "float", minimum=0, maximum=30, step=0.5,
            nullable=True, placeholder="model default"),
    _number("seed", "Seed", "int", minimum=0, step=1,
            help="Base seed. Re-roll in the modal uses a fresh random seed."),
    _number("max_images", "Max images in gallery", "int", minimum=1, step=1,
            nullable=True, placeholder="all"),
    _text("negative_prompt", "Negative prompt", nullable=True,
          placeholder="ignored by FLUX / Krea models"),
    _check("keep_previews", "Keep generated previews"),
]
