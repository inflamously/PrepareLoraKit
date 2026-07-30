"""VRAM planning for the Caption Verifier text-to-image runtime.

Pure and side-effect free: every capability (CUDA, bitsandbytes, VRAM figures)
is passed in, and warnings are *returned* as ``GenerationPlan.notes`` rather
than printed, so the whole quantization/offload ladder is testable without a
GPU. :mod:`.t2i` is responsible for probing the environment and emitting the
notes through ``reporter``.

No ``torch`` or ``diffusers`` import at module scope — ``tests/steps/
test_imports.py`` imports every module under ``steps/``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from prepare_lora_kit.steps.caption_verifier.catalog import T2IModel

QUANTIZATIONS = ("auto", "none", "4bit", "8bit")
OFFLOADS = ("auto", "none", "model", "sequential")

# Bytes-per-parameter divisors relative to a 16-bit baseline. Approximate on
# purpose: they only steer a tier choice, they are not an allocator.
_QUANT_DIVISOR = {"none": 1.0, "8bit": 1.9, "4bit": 3.6}

# Headroom multiplier over raw weight size, covering activations and latents.
_OVERHEAD = 1.15
# Below this fraction of the budget we do not bother installing offload hooks.
_RESIDENT_FRACTION = 0.75
_DIMENSION_FLOOR = 256
_DIMENSION_MULTIPLE = 64

# Fallbacks for a custom model id that carries no catalog metadata.
_UNKNOWN_PARAMS_B = 3.0
_UNKNOWN_TEXT_ENCODER_B = 1.0
_UNKNOWN_WIDTH = 1024
_UNKNOWN_HEIGHT = 1024
_UNKNOWN_STEPS = 30
_UNKNOWN_GUIDANCE = 7.0
_UNKNOWN_MAX_TOKENS = 77


@dataclass(frozen=True)
class GenerationPlan:
    """A fully resolved, executable description of one text-to-image setup."""

    model_id: str
    family: str
    pipeline_cls: str
    min_diffusers: str
    quantization: str  # "none" | "4bit" | "8bit"
    dtype: str  # "bfloat16" | "float16" | "float32"
    offload: str  # "none" | "model" | "sequential"
    device: str  # "cuda" | "cpu"
    quantize_components: tuple[str, ...]
    width: int
    height: int
    steps: int
    guidance: float
    supports_negative_prompt: bool
    max_prompt_tokens: int
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        """JSON-able summary for the step report's ``model`` block."""
        return {
            "model_id": self.model_id,
            "family": self.family,
            "pipeline_cls": self.pipeline_cls,
            "quantization": self.quantization,
            "dtype": self.dtype,
            "offload": self.offload,
            "device": self.device,
            "quantize_components": list(self.quantize_components),
        }


def bitsandbytes_available() -> bool:
    """Whether bitsandbytes can be imported (mirrors ``vlm._bitsandbytes_available``)."""
    try:
        import bitsandbytes  # noqa: F401

        return True
    except Exception:
        return False


def resolve_plan(
    model: T2IModel | None,
    *,
    model_id: str,
    quantization: str = "auto",
    dtype: str = "bfloat16",
    offload: str = "auto",
    total_vram_gb: float = 0.0,
    free_vram_gb: float = 0.0,
    has_cuda: bool = False,
    has_bitsandbytes: bool = False,
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    guidance: float | None = None,
) -> GenerationPlan:
    """Resolve config + environment into an executable :class:`GenerationPlan`.

    Explicit ``4bit``/``8bit`` requests are hard errors when they cannot be
    honoured — silently degrading an explicit choice hides the reason a probe
    is slow or an image looks wrong. ``auto`` degrades with a note instead.
    """
    quantization = _normalize(quantization, QUANTIZATIONS, "quantization")
    offload = _normalize(offload, OFFLOADS, "offload")
    notes: list[str] = []

    if quantization in {"4bit", "8bit"}:
        if not has_cuda:
            raise RuntimeError(
                f"{quantization} text-to-image loading requires CUDA; "
                "choose Auto or the Max VRAM tier for a CPU run."
            )
        if not has_bitsandbytes:
            raise RuntimeError(
                f"{quantization} text-to-image loading requires bitsandbytes; "
                "install/fix bitsandbytes or choose Auto/Max."
            )

    if not has_cuda:
        return _build(
            model, model_id, quantization="none", dtype="float32",
            offload="none", device="cpu", width=width, height=height,
            steps=steps, guidance=guidance,
            notes=(*notes, "No CUDA device; running on CPU in float32 (slow)."),
        )

    budget = _budget(total_vram_gb, free_vram_gb)
    need = _weight_gb(model)

    if quantization == "auto":
        quantization, auto_notes = _auto_quantization(
            need, budget, has_bitsandbytes,
        )
        notes.extend(auto_notes)

    if offload == "auto":
        offload = _auto_offload(need, budget, quantization)

    # bitsandbytes 4-bit weights cannot be moved back to CPU, so accelerate's
    # sequential (submodule-level) offload cannot drive a 4-bit model. Prefer
    # keeping the offload — it is what makes an oversized model run at all —
    # and drop the quantization instead.
    if quantization == "4bit" and offload == "sequential":
        quantization = "none"
        notes.append(
            "4-bit weights cannot be sequentially offloaded to CPU; "
            "using unquantized weights with sequential offload instead."
        )

    return _build(
        model, model_id, quantization=quantization, dtype=dtype,
        offload=offload, device="cuda", width=width, height=height,
        steps=steps, guidance=guidance, notes=tuple(notes),
    )


# --- internals -------------------------------------------------------------

def _normalize(value: str, allowed: tuple[str, ...], label: str) -> str:
    cleaned = str(value or "auto").strip().lower()
    if cleaned not in allowed:
        raise ValueError(
            f"CaptionVerifierStep: {label} must be one of {list(allowed)}, "
            f"got '{value}'"
        )
    return cleaned


def _budget(total_vram_gb: float, free_vram_gb: float) -> float:
    """Usable VRAM in GiB.

    Planning off *free* VRAM, not total, is what lets this step run in the same
    process right after CaptionBboxStep without OOMing on a card whose total
    looks ample but whose memory is still held.
    """
    total = max(float(total_vram_gb or 0.0), 0.0)
    free = max(float(free_vram_gb or 0.0), 0.0)
    if not free:
        return total * 0.85
    return min(total * 0.85, max(free - 1.0, 0.0))


def _weight_gb(model: T2IModel | None) -> float:
    params = model.params_b if model else _UNKNOWN_PARAMS_B
    text = model.text_encoder_b if model else _UNKNOWN_TEXT_ENCODER_B
    return (params + text) * 2.0 * _OVERHEAD


def _auto_quantization(
    need: float, budget: float, has_bitsandbytes: bool,
) -> tuple[str, list[str]]:
    if not has_bitsandbytes:
        return "none", [
            ("bitsandbytes unavailable; auto text-to-image quantization "
            "selecting unquantized load.")
        ]
    if not budget or need <= budget:
        return "none", []
    if need / _QUANT_DIVISOR["4bit"] <= budget:
        return "4bit", []
    # Too large even at 4-bit; ask for 4-bit and let the sequential-offload
    # escalation in resolve_plan decide how to reconcile the two.
    return "4bit", []


def _auto_offload(need: float, budget: float, quantization: str) -> str:
    if not budget:
        return "model"
    effective = need / _QUANT_DIVISOR.get(quantization, 1.0)
    if effective <= budget * _RESIDENT_FRACTION:
        return "none"
    if effective <= budget:
        return "model"
    return "sequential"


def _snap(value: int | None, fallback: int) -> int:
    if value is None:
        return int(fallback)
    snapped = (int(value) // _DIMENSION_MULTIPLE) * _DIMENSION_MULTIPLE
    return max(_DIMENSION_FLOOR, snapped)


def _build(
    model: T2IModel | None,
    model_id: str,
    *,
    quantization: str,
    dtype: str,
    offload: str,
    device: str,
    width: int | None,
    height: int | None,
    steps: int | None,
    guidance: float | None,
    notes: tuple[str, ...] = (),
) -> GenerationPlan:
    resolved_width = _snap(width, model.default_width if model else _UNKNOWN_WIDTH)
    resolved_height = _snap(height, model.default_height if model else _UNKNOWN_HEIGHT)
    extra: list[str] = list(notes)
    if width is not None and resolved_width != int(width):
        extra.append(f"Width snapped from {int(width)} to {resolved_width}.")
    if height is not None and resolved_height != int(height):
        extra.append(f"Height snapped from {int(height)} to {resolved_height}.")

    return GenerationPlan(
        model_id=model_id,
        family=model.family if model else "unknown",
        pipeline_cls=model.pipeline_cls if model else "AutoPipelineForText2Image",
        min_diffusers=model.min_diffusers if model else "0.30",
        quantization=quantization,
        dtype=dtype if device == "cuda" else "float32",
        offload=offload,
        device=device,
        quantize_components=tuple(model.quantize_components) if model else (),
        width=resolved_width,
        height=resolved_height,
        steps=int(steps) if steps else (model.default_steps if model else _UNKNOWN_STEPS),
        guidance=float(guidance) if guidance is not None
        else (model.default_guidance if model else _UNKNOWN_GUIDANCE),
        supports_negative_prompt=(
            bool(model.supports_negative_prompt) if model else True
        ),
        max_prompt_tokens=(
            int(model.max_prompt_tokens) if model else _UNKNOWN_MAX_TOKENS
        ),
        notes=tuple(extra),
    )
