"""SeedVR2 DiT model catalog owned by PrepareLoraKit."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedVR2DitModel:
    """Metadata for a supported SeedVR2 DiT checkpoint."""

    name: str
    parameter_size: str
    precision_quantization: str
    file_format: str
    variant: str
    suitability_label: str


_SEEDVR2_DIT_MODEL_CATALOG: tuple[SeedVR2DitModel, ...] = (
    SeedVR2DitModel(
        name="seedvr2_ema_3b_fp8_e4m3fn.safetensors",
        parameter_size="3B",
        precision_quantization="fp8 e4m3fn",
        file_format="safetensors",
        variant="base",
        suitability_label="default",
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_3b_fp16.safetensors",
        parameter_size="3B",
        precision_quantization="fp16",
        file_format="safetensors",
        variant="base",
        suitability_label="3B quality",
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_3b-Q4_K_M.gguf",
        parameter_size="3B",
        precision_quantization="Q4_K_M",
        file_format="gguf",
        variant="base",
        suitability_label="lower VRAM",
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_3b-Q8_0.gguf",
        parameter_size="3B",
        precision_quantization="Q8_0",
        file_format="gguf",
        variant="base",
        suitability_label="balanced GGUF",
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors",
        parameter_size="7B",
        precision_quantization="fp8 e4m3fn mixed block35 fp16",
        file_format="safetensors",
        variant="base",
        suitability_label="higher quality",
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_7b_fp16.safetensors",
        parameter_size="7B",
        precision_quantization="fp16",
        file_format="safetensors",
        variant="base",
        suitability_label="highest quality",
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_7b-Q4_K_M.gguf",
        parameter_size="7B",
        precision_quantization="Q4_K_M",
        file_format="gguf",
        variant="base",
        suitability_label="lower VRAM 7B",
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_7b_sharp_fp8_e4m3fn_mixed_block35_fp16.safetensors",
        parameter_size="7B",
        precision_quantization="fp8 e4m3fn mixed block35 fp16",
        file_format="safetensors",
        variant="sharp",
        suitability_label="sharp",
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_7b_sharp_fp16.safetensors",
        parameter_size="7B",
        precision_quantization="fp16",
        file_format="safetensors",
        variant="sharp",
        suitability_label="sharp highest quality",
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_7b_sharp-Q4_K_M.gguf",
        parameter_size="7B",
        precision_quantization="Q4_K_M",
        file_format="gguf",
        variant="sharp",
        suitability_label="sharp lower VRAM",
    ),
)

DEFAULT_SEEDVR2_DIT_MODEL = _SEEDVR2_DIT_MODEL_CATALOG[0].name
SUPPORTED_SEEDVR2_DIT_MODELS = tuple(model.name for model in _SEEDVR2_DIT_MODEL_CATALOG)
_SEEDVR2_DIT_MODELS_BY_NAME = {model.name: model for model in _SEEDVR2_DIT_MODEL_CATALOG}


def get_seedvr2_dit_model(name: str) -> SeedVR2DitModel | None:
    """Return catalog metadata for a supported SeedVR2 DiT model name."""

    return _SEEDVR2_DIT_MODELS_BY_NAME.get(name)


def list_seedvr2_dit_models() -> tuple[SeedVR2DitModel, ...]:
    """Return supported SeedVR2 DiT models in display order."""

    return _SEEDVR2_DIT_MODEL_CATALOG


__all__ = [
    "DEFAULT_SEEDVR2_DIT_MODEL",
    "SUPPORTED_SEEDVR2_DIT_MODELS",
    "SeedVR2DitModel",
    "get_seedvr2_dit_model",
    "list_seedvr2_dit_models",
]
