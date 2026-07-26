"""Tests for CaptionVerifierConfig validation.

``apply_overrides`` re-runs ``__post_init__`` and surfaces ``ValueError`` as the
step-config modal's inline error, so every rule here doubles as UI validation.
"""
from __future__ import annotations

import pytest

from prepare_lora_kit.pipeline.configs import CaptionVerifierConfig


def test_defaults_are_usable_without_the_config_modal():
    """The modal only appears when 'pause for config' is ticked."""
    config = CaptionVerifierConfig()

    assert config.t2i_model_id == "auto"
    assert config.vram_tier == "auto"
    assert config.write_edited_captions is True


@pytest.mark.parametrize(
    "tier,expected",
    [
        ("auto", ("auto", "bfloat16", "auto")),
        ("low", ("4bit", "bfloat16", "model")),
        ("mid", ("4bit", "bfloat16", "model")),
        ("high", ("none", "bfloat16", "model")),
        ("max", ("none", "bfloat16", "none")),
    ],
)
def test_vram_tier_properties(tier, expected):
    config = CaptionVerifierConfig(vram_tier=tier)

    assert (config.quantization, config.dtype, config.offload) == expected


def test_no_tier_requests_sequential_offload():
    """Sequential is decided at runtime from free VRAM.

    Keeping it out of the tier table is what prevents a tier from asking for the
    forbidden 4bit+sequential pair.
    """
    for tier in CaptionVerifierConfig._VRAM_TIERS:
        assert CaptionVerifierConfig(vram_tier=tier).offload != "sequential"


def test_invalid_vram_tier_raises():
    with pytest.raises(ValueError, match="vram_tier"):
        CaptionVerifierConfig(vram_tier="ludicrous")


def test_blank_model_id_becomes_auto():
    assert CaptionVerifierConfig(t2i_model_id="  ").t2i_model_id == "auto"


def test_legacy_runwayml_id_is_normalized():
    config = CaptionVerifierConfig(t2i_model_id="runwayml/stable-diffusion-v1-5")

    assert config.t2i_model_id == "stable-diffusion-v1-5/stable-diffusion-v1-5"


def test_custom_model_id_warns_but_is_accepted():
    with pytest.warns(UserWarning, match="not a known"):
        config = CaptionVerifierConfig(t2i_model_id="someone/custom-merge")

    assert config.t2i_model_id == "someone/custom-merge"


def test_catalog_model_id_does_not_warn(recwarn):
    CaptionVerifierConfig(t2i_model_id="stabilityai/stable-diffusion-xl-base-1.0")

    assert [w for w in recwarn if issubclass(w.category, UserWarning)] == []


@pytest.mark.parametrize("field", ["width", "height"])
@pytest.mark.parametrize("value", [8, 128, 5000])
def test_dimensions_outside_the_allowed_range_raise(field, value):
    with pytest.raises(ValueError, match=field):
        CaptionVerifierConfig(**{field: value})


@pytest.mark.parametrize("field", ["width", "height"])
def test_dimensions_must_be_a_multiple_of_eight(field):
    with pytest.raises(ValueError, match="multiple of 8"):
        CaptionVerifierConfig(**{field: 1001})


def test_dimensions_accept_none_for_the_model_default():
    config = CaptionVerifierConfig(width=None, height=None)

    assert config.width is None and config.height is None


@pytest.mark.parametrize("steps", [0, 151])
def test_step_count_out_of_range_raises(steps):
    with pytest.raises(ValueError, match="num_inference_steps"):
        CaptionVerifierConfig(num_inference_steps=steps)


@pytest.mark.parametrize("guidance", [-0.5, 30.5])
def test_guidance_out_of_range_raises(guidance):
    with pytest.raises(ValueError, match="guidance_scale"):
        CaptionVerifierConfig(guidance_scale=guidance)


@pytest.mark.parametrize("seed", [-1, 2 ** 32])
def test_seed_out_of_range_raises(seed):
    with pytest.raises(ValueError, match="seed"):
        CaptionVerifierConfig(seed=seed)


def test_max_images_must_be_positive():
    with pytest.raises(ValueError, match="max_images"):
        CaptionVerifierConfig(max_images=0)


def test_blank_negative_prompt_becomes_none():
    assert CaptionVerifierConfig(negative_prompt="   ").negative_prompt is None
