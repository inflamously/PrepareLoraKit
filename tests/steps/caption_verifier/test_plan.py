"""Contract tests for the Caption Verifier VRAM planner.

``plan.resolve_plan`` is pure: no torch, no diffusers, no GPU. Every capability
it needs is passed in, which makes the whole quantization/offload ladder
testable without mocking a model.
"""
from __future__ import annotations

import pytest

from prepare_lora_kit.steps.caption_verifier import catalog, plan

SDXL = catalog.get("stabilityai/stable-diffusion-xl-base-1.0")
KLEIN = catalog.get("black-forest-labs/FLUX.2-klein-base-9B")
SD15 = catalog.get("stable-diffusion-v1-5/stable-diffusion-v1-5")


def _resolve(model=SDXL, **kw):
    """resolve_plan with cuda+bitsandbytes present and a roomy card by default."""
    params = {
        "model_id": model.id if model else "custom/model",
        "quantization": "auto",
        "dtype": "bfloat16",
        "offload": "auto",
        "total_vram_gb": 48.0,
        "free_vram_gb": 46.0,
        "has_cuda": True,
        "has_bitsandbytes": True,
    }
    params.update(kw)
    return plan.resolve_plan(model, **params)


# --- explicit quantization: hard errors, never silent degradation ----------

@pytest.mark.parametrize("quant", ["4bit", "8bit"])
def test_explicit_quantization_without_cuda_raises(quant):
    with pytest.raises(RuntimeError, match="CUDA"):
        _resolve(quantization=quant, has_cuda=False)


@pytest.mark.parametrize("quant", ["4bit", "8bit"])
def test_explicit_quantization_without_bitsandbytes_raises(quant):
    with pytest.raises(RuntimeError, match="bitsandbytes"):
        _resolve(quantization=quant, has_bitsandbytes=False)


def test_unsupported_quantization_raises():
    with pytest.raises(ValueError, match="quantization"):
        _resolve(quantization="3bit")


# --- auto quantization ladder ---------------------------------------------

def test_auto_keeps_sdxl_resident_on_a_large_card():
    result = _resolve(model=SDXL, total_vram_gb=48.0, free_vram_gb=46.0)
    assert result.quantization == "none"
    assert result.offload == "none"


def test_auto_quantizes_klein_at_16gb():
    result = _resolve(model=KLEIN, total_vram_gb=16.0, free_vram_gb=15.0)
    assert result.quantization == "4bit"
    assert result.offload == "model"


def test_auto_without_bitsandbytes_degrades_to_none_and_escalates_offload():
    result = _resolve(model=KLEIN, total_vram_gb=16.0, free_vram_gb=15.0,
                      has_bitsandbytes=False)
    assert result.quantization == "none"
    assert result.offload in {"model", "sequential"}


def test_auto_plans_from_free_vram_not_total():
    """A card whose VRAM is already occupied must plan conservatively.

    This is what makes the step survive running right after CaptionBboxStep in
    the same process, where the total is large but almost nothing is free.
    """
    roomy = _resolve(model=KLEIN, total_vram_gb=48.0, free_vram_gb=46.0)
    crowded = _resolve(model=KLEIN, total_vram_gb=48.0, free_vram_gb=6.0)
    assert crowded.offload == "sequential"
    assert roomy.offload != "sequential"


# --- device / dtype fallbacks ---------------------------------------------

def test_without_cuda_falls_back_to_cpu_float32():
    result = _resolve(has_cuda=False, total_vram_gb=0.0, free_vram_gb=0.0)
    assert result.device == "cpu"
    assert result.dtype == "float32"
    assert result.quantization == "none"
    assert result.offload == "none"


# --- the bitsandbytes invariant -------------------------------------------

@pytest.mark.parametrize("model", list(catalog.T2I_MODELS), ids=lambda m: m.family)
@pytest.mark.parametrize(("total", "free"), [(8, 7), (16, 15), (24, 23), (32, 30), (48, 46)])
@pytest.mark.parametrize("quantization", ["auto", "none", "4bit"])
@pytest.mark.parametrize("offload", ["auto", "none", "model", "sequential"])
def test_never_combines_4bit_with_sequential_offload(
    model, total, free, quantization, offload,
):
    """bitsandbytes 4-bit weights cannot round-trip to CPU.

    Emitting ("4bit", "sequential") produces a runtime crash deep inside
    accelerate's offload hooks, so the planner must collapse that combination.
    """
    result = _resolve(model=model, quantization=quantization, offload=offload,
                      total_vram_gb=total, free_vram_gb=free)
    assert not (result.quantization == "4bit" and result.offload == "sequential")


def test_explicit_4bit_with_sequential_offload_drops_the_quantization():
    result = _resolve(model=KLEIN, quantization="4bit", offload="sequential",
                      total_vram_gb=16.0, free_vram_gb=15.0)
    assert result.offload == "sequential"
    assert result.quantization == "none"


# --- dimensions and family defaults ---------------------------------------

def test_dimensions_default_to_the_family_values():
    result = _resolve(model=SD15)
    assert (result.width, result.height) == (SD15.default_width, SD15.default_height)
    assert result.steps == SD15.default_steps
    assert result.guidance == pytest.approx(SD15.default_guidance)


def test_dimension_overrides_snap_down_to_a_multiple_of_64():
    result = _resolve(width=1000, height=700)
    assert result.width == 960
    assert result.height == 640


def test_dimensions_never_snap_below_the_floor():
    result = _resolve(width=8, height=8)
    assert result.width >= 256
    assert result.height >= 256


def test_step_and_guidance_overrides_win():
    result = _resolve(steps=7, guidance=2.5)
    assert result.steps == 7
    assert result.guidance == pytest.approx(2.5)


# --- unknown/custom models ------------------------------------------------

def test_custom_model_without_catalog_metadata_still_plans():
    result = plan.resolve_plan(
        None, model_id="someone/custom-sdxl-merge", quantization="auto",
        dtype="bfloat16", offload="auto", total_vram_gb=24.0, free_vram_gb=23.0,
        has_cuda=True, has_bitsandbytes=True,
    )
    assert result.model_id == "someone/custom-sdxl-merge"
    assert result.family == "unknown"
    assert result.width >= 256
    assert result.height >= 256
    assert result.steps >= 1


def test_negative_prompt_support_follows_the_catalog():
    assert _resolve(model=SDXL).supports_negative_prompt is True
    # Verified against diffusers 0.38: Flux2KleinPipeline takes no negative_prompt.
    assert _resolve(model=KLEIN).supports_negative_prompt is False
