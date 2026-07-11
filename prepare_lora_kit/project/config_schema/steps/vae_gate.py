"""Editable config fields for VaeGateStep."""
from __future__ import annotations


from prepare_lora_kit.project.config_schema.fields import FieldSpec, _check, _number, _text
STEP_TYPE = "VaeGateStep"

FIELDS: list[FieldSpec] = [
    _text("vae_model_id", "VAE model id"),
    _text("vae_config_id", "VAE config id", nullable=True),
    _number("diff_amplification", "Diff amplification", "float", minimum=0, step=0.5),
    _number("gaussian_blur_sigma", "Gaussian blur sigma", "float", minimum=0, step=0.1),
    _number("gaussian_blur_kernel", "Gaussian blur kernel (odd)", "int", minimum=1, step=2),
    _check("otsu_enabled", "Otsu thresholding"),
    _number("outlier_sigma", "Outlier sigma", "float", minimum=0, step=0.1),
    _number("hf_cutoff_fraction", "HF cutoff fraction", "float", minimum=0.01, maximum=0.49, step=0.01),
    _number("max_side", "Max side (px)", "int", minimum=8, step=64, nullable=True,
            placeholder="no size cap"),
    _number("seed", "Seed", "int", step=1),
]
