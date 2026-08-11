"""SeedVR2 DiT model catalog owned by PrepareLoraKit.

This module is the single source of truth for the SeedVR2 checkpoints PLK offers.
The step-config dropdown, the Settings modal, the ``auto`` model pick and the
worker's residency heuristic all read from here so they cannot drift apart.

Kept deliberately import-light: stdlib only, no ``torch`` and no settings access,
so importing the config schema stays cheap. VRAM detection lives in
:mod:`prepare_lora_kit.embedding.vram`; the on-disk scan lives in
:mod:`prepare_lora_kit.steps.upscale.seedvr2_adapter`.
"""
from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

AUTO = "auto"


@dataclass(frozen=True)
class SeedVR2DitModel:
    """Metadata for a supported SeedVR2 DiT checkpoint.

    ``min_gpu_residency_gb`` is the VRAM needed to keep the model resident on the
    GPU; below it the worker falls back to CPU offload. It doubles as the ladder
    :func:`auto_select` walks. ``approx_download_gb`` is only ever shown to the
    user, never compared against — see the note on ``_DOWNLOAD_GB`` below.
    """

    name: str
    parameter_size: str
    precision_quantization: str
    file_format: str
    variant: str
    suitability_label: str
    min_gpu_residency_gb: float
    quality_rank: int
    approx_download_gb: float


# Download sizes are APPROXIMATE and for display only. The 3B fp8 and 7B fp16
# figures are exact (observed in a SeedVR2 validation cache); the rest are
# parameter-count x bytes-per-parameter estimates. SeedVR2 verifies the real
# files by sha256 at download time, so a wrong figure here misinforms but cannot
# corrupt a run. To refresh them:
#   curl -sIL https://huggingface.co/<repo>/resolve/main/<file>   # x-linked-size
# with <repo> from third_party/seedvr2/src/utils/model_registry.py.
_SEEDVR2_DIT_MODEL_CATALOG: tuple[SeedVR2DitModel, ...] = (
    # --- base variants, lowest VRAM first ---------------------------------
    SeedVR2DitModel(
        name="seedvr2_ema_3b-Q4_K_M.gguf",
        parameter_size="3B",
        precision_quantization="Q4_K_M",
        file_format="gguf",
        variant="base",
        suitability_label="lowest VRAM",
        min_gpu_residency_gb=16.0,
        quality_rank=1,
        approx_download_gb=1.8,
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_3b-Q8_0.gguf",
        parameter_size="3B",
        precision_quantization="Q8_0",
        file_format="gguf",
        variant="base",
        suitability_label="balanced GGUF",
        min_gpu_residency_gb=16.0,
        quality_rank=2,
        approx_download_gb=3.4,
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_3b_fp8_e4m3fn.safetensors",
        parameter_size="3B",
        precision_quantization="fp8 e4m3fn",
        file_format="safetensors",
        variant="base",
        suitability_label="default",
        min_gpu_residency_gb=16.0,
        quality_rank=3,
        approx_download_gb=3.2,
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_3b_fp16.safetensors",
        parameter_size="3B",
        precision_quantization="fp16",
        file_format="safetensors",
        variant="base",
        suitability_label="best 3B",
        min_gpu_residency_gb=24.0,
        quality_rank=4,
        approx_download_gb=6.3,
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_7b-Q4_K_M.gguf",
        parameter_size="7B",
        precision_quantization="Q4_K_M",
        file_format="gguf",
        variant="base",
        suitability_label="lower VRAM",
        min_gpu_residency_gb=24.0,
        quality_rank=5,
        approx_download_gb=4.3,
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors",
        parameter_size="7B",
        precision_quantization="fp8 e4m3fn mixed block35 fp16",
        file_format="safetensors",
        variant="base",
        suitability_label="higher quality",
        min_gpu_residency_gb=24.0,
        quality_rank=6,
        approx_download_gb=7.7,
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_7b_fp16.safetensors",
        parameter_size="7B",
        precision_quantization="fp16",
        file_format="safetensors",
        variant="base",
        suitability_label="highest quality",
        min_gpu_residency_gb=40.0,
        quality_rank=7,
        approx_download_gb=15.3,
    ),
    # --- sharp variants ----------------------------------------------------
    # A look (enhanced detail), not a quality tier, so auto_select skips them.
    SeedVR2DitModel(
        name="seedvr2_ema_7b_sharp-Q4_K_M.gguf",
        parameter_size="7B",
        precision_quantization="Q4_K_M",
        file_format="gguf",
        variant="sharp",
        suitability_label="lower VRAM",
        min_gpu_residency_gb=24.0,
        quality_rank=5,
        approx_download_gb=4.3,
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_7b_sharp_fp8_e4m3fn_mixed_block35_fp16.safetensors",
        parameter_size="7B",
        precision_quantization="fp8 e4m3fn mixed block35 fp16",
        file_format="safetensors",
        variant="sharp",
        suitability_label="higher quality",
        min_gpu_residency_gb=24.0,
        quality_rank=6,
        approx_download_gb=7.7,
    ),
    SeedVR2DitModel(
        name="seedvr2_ema_7b_sharp_fp16.safetensors",
        parameter_size="7B",
        precision_quantization="fp16",
        file_format="safetensors",
        variant="sharp",
        suitability_label="highest quality",
        min_gpu_residency_gb=40.0,
        quality_rank=7,
        approx_download_gb=15.3,
    ),
)

# Spelled out rather than derived from catalog position: display order is sorted
# by VRAM, and the default must not move when a cheaper model is added.
DEFAULT_SEEDVR2_DIT_MODEL = "seedvr2_ema_3b_fp8_e4m3fn.safetensors"
SUPPORTED_SEEDVR2_DIT_MODELS = tuple(model.name for model in _SEEDVR2_DIT_MODEL_CATALOG)
_SEEDVR2_DIT_MODELS_BY_NAME = {model.name: model for model in _SEEDVR2_DIT_MODEL_CATALOG}


def get_seedvr2_dit_model(name: str) -> SeedVR2DitModel | None:
    """Return catalog metadata for a supported SeedVR2 DiT model name."""

    return _SEEDVR2_DIT_MODELS_BY_NAME.get(name)


def list_seedvr2_dit_models() -> tuple[SeedVR2DitModel, ...]:
    """Return supported SeedVR2 DiT models in display order (lowest VRAM first)."""

    return _SEEDVR2_DIT_MODEL_CATALOG


def dit_model_choices(downloaded: Collection[str] = ()) -> list[tuple[str, str]]:
    """``(value, label)`` pairs for the DiT dropdown (Auto first).

    ``downloaded`` is the set of checkpoint filenames already on disk; entries in
    it are labelled as cached, the rest advertise their download size so picking
    a 7B model is not a surprise multi-GB fetch mid-run.
    """

    return [(AUTO, "Auto (match VRAM)")] + [
        (model.name, _label(model, model.name in downloaded))
        for model in _SEEDVR2_DIT_MODEL_CATALOG
    ]


def auto_select(total_vram_gb: float) -> str:
    """Pick the best SeedVR2 DiT checkpoint for the available VRAM.

    Returns the highest-quality *base* model that still fits on the GPU, so the
    ladder is 3B fp8 (no CUDA / small cards) -> 7B fp8 mixed (24 GB) -> 7B fp16
    (40 GB). Sharp variants are a deliberate style choice and are never picked
    automatically. Falls back to :data:`DEFAULT_SEEDVR2_DIT_MODEL` when nothing
    fits, which keeps "lowest first" true on cards below the 16 GB rung.
    """

    gb = float(total_vram_gb or 0.0)
    fitting = [
        model for model in _SEEDVR2_DIT_MODEL_CATALOG
        if model.variant == "base" and model.min_gpu_residency_gb <= gb
    ]
    if not fitting:
        return DEFAULT_SEEDVR2_DIT_MODEL
    return max(fitting, key=lambda model: model.quality_rank).name


def _label(model: SeedVR2DitModel, is_downloaded: bool) -> str:
    """One dropdown label: what it is, what it needs, what it costs to get."""

    state = ("downloaded" if is_downloaded
             else f"~{model.approx_download_gb:.1f} GB download")
    # The variant is part of the name, not a footnote: a "sharp" entry otherwise
    # reads identically to its base twin apart from the suitability wording.
    variant = "" if model.variant == "base" else f" {model.variant}"
    return (
        f"{model.parameter_size}{variant} {model.precision_quantization} "
        f"— {model.min_gpu_residency_gb:.0f} GB VRAM, {model.suitability_label} "
        f"· {state}"
    )


__all__ = [
    "AUTO",
    "DEFAULT_SEEDVR2_DIT_MODEL",
    "SUPPORTED_SEEDVR2_DIT_MODELS",
    "SeedVR2DitModel",
    "auto_select",
    "dit_model_choices",
    "get_seedvr2_dit_model",
    "list_seedvr2_dit_models",
]
