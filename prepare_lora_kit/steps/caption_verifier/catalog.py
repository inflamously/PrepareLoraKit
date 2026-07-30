"""Text-to-image model catalog owned by the Caption Verifier step.

Single source of truth for the models offered in ``CaptionVerifierStep``. Both
the UI config schema (dropdown options) and the runtime loader read from here,
so the two can never drift apart.

Kept deliberately import-light: no ``torch``/``diffusers``/``transformers`` at
module load, so importing the config schema stays cheap. Mirrors the shape of
:mod:`prepare_lora_kit.embedding.catalog`.

The ``params_b``/``text_encoder_b`` figures are **rough sizing estimates** used
only by :mod:`.plan` to pick a quantization tier. They do not need to be exact;
they need to be in the right order of magnitude.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class T2IModel:
    """Metadata for one supported text-to-image model.

    ``id`` is the stable key stored in config and used as the dropdown value —
    normally a Hugging Face repo id.

    ``pipeline_cls`` is a *hint*, not a guarantee: the loader resolves it with
    ``getattr(diffusers, pipeline_cls, None)`` and falls back to the auto
    pipeline, so a model whose class ships in a newer diffusers degrades to a
    readable "upgrade diffusers" error instead of an ImportError traceback.
    """

    id: str
    label: str
    family: str  # "sd15" | "sdxl" | "flux2" | "krea2"
    pipeline_cls: str
    params_b: float  # denoiser/transformer parameters, billions (estimate)
    text_encoder_b: float  # text encoder parameters, billions (estimate)
    min_vram_gb: float  # smallest card this is a sensible Auto pick for
    default_width: int
    default_height: int
    default_steps: int
    default_guidance: float
    supports_negative_prompt: bool
    max_prompt_tokens: int  # encoder context; terms past this are never seen
    # Pipeline sub-module names handed to diffusers' PipelineQuantizationConfig.
    # Names differ per architecture ("unet" vs "transformer"), and SDXL carries
    # two text encoders.
    quantize_components: tuple[str, ...]
    min_diffusers: str  # shown in the error when pipeline_cls is unavailable
    notes: str = ""


# --- Stable Diffusion 1.5 --------------------------------------------------
# The original runwayml repo was pulled from the Hub; see _ALIASES below.
SD15_MODELS: tuple[T2IModel, ...] = (
    T2IModel(
        "stable-diffusion-v1-5/stable-diffusion-v1-5",
        "SD 1.5 (CLIP ViT-L, 512px, fastest)",
        "sd15", "StableDiffusionPipeline",
        params_b=0.86, text_encoder_b=0.12, min_vram_gb=0.0,
        default_width=512, default_height=512,
        default_steps=30, default_guidance=7.5,
        supports_negative_prompt=True, max_prompt_tokens=77,
        quantize_components=("unet", "text_encoder"), min_diffusers="0.30",
        notes="Fastest probe, weakest signal. safety_checker is disabled so a "
              "false positive can never be misread as 'the model doesn't know "
              "this term'.",
    ),
)

# --- SDXL ------------------------------------------------------------------
SDXL_MODELS: tuple[T2IModel, ...] = (
    T2IModel(
        "stabilityai/stable-diffusion-xl-base-1.0",
        "SDXL base 1.0 (dual CLIP, 1024px)",
        "sdxl", "StableDiffusionXLPipeline",
        params_b=2.6, text_encoder_b=0.82, min_vram_gb=8.0,
        default_width=1024, default_height=1024,
        default_steps=30, default_guidance=7.0,
        supports_negative_prompt=True, max_prompt_tokens=77,
        quantize_components=("unet", "text_encoder", "text_encoder_2"),
        min_diffusers="0.30",
        notes="CLIP-L + OpenCLIP-bigG. The most representative target for the "
              "LoRA trainers this tool feeds.",
    ),
)

# --- FLUX.2 klein ----------------------------------------------------------
# Verified against diffusers 0.38: Flux2KleinPipeline.from_pretrained(
#   "black-forest-labs/FLUX.2-klein-base-9B", torch_dtype=torch.bfloat16)
# Components are (AutoencoderKLFlux2, Qwen3ForCausalLM, Qwen2TokenizerFast,
# Flux2Transformer2DModel) — the text encoder is Qwen3, not T5.
FLUX2_MODELS: tuple[T2IModel, ...] = (
    T2IModel(
        "black-forest-labs/FLUX.2-klein-base-9B",
        "FLUX.2 klein base 9B (Qwen3 text encoder)",
        "flux2", "Flux2KleinPipeline",
        params_b=9.0, text_encoder_b=8.0, min_vram_gb=16.0,
        default_width=1024, default_height=1024,
        default_steps=28, default_guidance=4.0,
        supports_negative_prompt=False, max_prompt_tokens=512,
        quantize_components=("transformer", "text_encoder"),
        min_diffusers="0.38",
        notes="Rejects negative_prompt (embeds only). 512-token context, so "
              "long captions are not truncated the way CLIP truncates them.",
    ),
)

# --- Krea 2 ----------------------------------------------------------------
# Krea2Pipeline is NOT present in diffusers 0.38 (the version installed in this
# checkout's .venv). These entries are deliberately selectable but never chosen
# by auto_select — the loader turns a missing class into an "upgrade diffusers"
# message. Sizing figures are estimates and unverified against the Hub.
KREA2_MODELS: tuple[T2IModel, ...] = (
    T2IModel(
        "krea/Krea-2-Turbo",
        "Krea 2 Turbo (8-step distilled, fastest probe)",
        "krea2", "Krea2Pipeline",
        params_b=12.0, text_encoder_b=5.0, min_vram_gb=16.0,
        default_width=1024, default_height=1024,
        default_steps=8, default_guidance=1.0,
        supports_negative_prompt=False, max_prompt_tokens=512,
        quantize_components=("transformer", "text_encoder"),
        min_diffusers="0.39",
        notes="Step-distilled: 8 steps at guidance 1.0. Needs a diffusers "
              "release that ships Krea2Pipeline.",
    ),
    T2IModel(
        "krea/Krea-2-Raw",
        "Krea 2 Raw (undistilled)",
        "krea2", "Krea2Pipeline",
        params_b=12.0, text_encoder_b=5.0, min_vram_gb=24.0,
        default_width=1024, default_height=1024,
        default_steps=28, default_guidance=4.0,
        supports_negative_prompt=False, max_prompt_tokens=512,
        quantize_components=("transformer", "text_encoder"),
        min_diffusers="0.39",
        notes="No step or guidance distillation. Needs a diffusers release "
              "that ships Krea2Pipeline.",
    ),
)

T2I_MODELS: tuple[T2IModel, ...] = (
    SD15_MODELS + SDXL_MODELS + FLUX2_MODELS + KREA2_MODELS
)

_BY_ID: dict[str, T2IModel] = {m.id: m for m in T2I_MODELS}

# Legacy/alias ids -> canonical catalog id. runwayml/stable-diffusion-v1-5 was
# removed from the Hub in 2024; using it verbatim 404s on first generate.
_ALIASES: dict[str, str] = {
    "runwayml/stable-diffusion-v1-5": "stable-diffusion-v1-5/stable-diffusion-v1-5",
    "CompVis/stable-diffusion-v1-4": "stable-diffusion-v1-5/stable-diffusion-v1-5",
    "black-forest-labs/FLUX.2-klein": "black-forest-labs/FLUX.2-klein-base-9B",
}

AUTO = "auto"
DEFAULT_MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"

__all__ = [
    "AUTO",
    "DEFAULT_MODEL_ID",
    "FLUX2_MODELS",
    "KREA2_MODELS",
    "SD15_MODELS",
    "SDXL_MODELS",
    "T2I_MODELS",
    "T2IModel",
    "auto_select",
    "get",
    "model_choices",
    "normalize_id",
    "resolve",
]


def normalize_id(model_id: str | None) -> str:
    """Map legacy/alias ids to their canonical catalog id (identity otherwise)."""
    cleaned = str(model_id or "").strip()
    if not cleaned:
        return AUTO
    return _ALIASES.get(cleaned, cleaned)


def get(model_id: str | None) -> T2IModel | None:
    """Catalog metadata for a model id, or ``None`` when it is custom/unknown."""
    return _BY_ID.get(normalize_id(model_id))


def model_choices() -> list[tuple[str, str]]:
    """``(value, label)`` pairs for the model dropdown (Auto first)."""
    return [(AUTO, "Auto (match VRAM)")] + [(m.id, m.label) for m in T2I_MODELS]


def auto_select(total_vram_gb: float) -> str:
    """Pick the best model id for the available VRAM.

    Ladder:
      * no CUDA            -> SD 1.5   (CPU fallback; slow but it runs)
      * <=16 GB            -> SDXL     (fp16, ~8 GB, seconds per image)
      * >16 GB             -> FLUX.2 klein (4-bit + model offload)

    Krea 2 is deliberately never an Auto pick: ``Krea2Pipeline`` is absent from
    diffusers 0.38, so auto-selecting it would hand users a load failure on a
    machine that is otherwise perfectly capable. It stays explicitly selectable.
    """
    gb = float(total_vram_gb or 0.0)
    if gb <= 0:
        return "stable-diffusion-v1-5/stable-diffusion-v1-5"
    if gb <= 16:
        return "stabilityai/stable-diffusion-xl-base-1.0"
    return "black-forest-labs/FLUX.2-klein-base-9B"


def resolve(model_id: str | None, total_vram_gb: float) -> tuple[str, T2IModel | None]:
    """Resolve ``"auto"`` against VRAM and return ``(id, metadata_or_None)``.

    A custom id that is not in the catalog resolves to ``(id, None)`` — the
    loader still tries it via the auto pipeline, and :mod:`.plan` falls back to
    conservative defaults.
    """
    normalized = normalize_id(model_id)
    if normalized == AUTO:
        normalized = auto_select(total_vram_gb)
    return normalized, get(normalized)
