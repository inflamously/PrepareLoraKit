"""Tests for the Caption Verifier text-to-image model catalog."""
from __future__ import annotations

import subprocess
import sys

import pytest

from prepare_lora_kit.steps.caption_verifier import catalog


def test_model_choices_lists_auto_first():
    choices = catalog.model_choices()
    assert choices[0][0] == catalog.AUTO
    assert len(choices) == 1 + len(catalog.T2I_MODELS)


def test_every_model_id_is_unique_and_round_trips():
    ids = [m.id for m in catalog.T2I_MODELS]
    assert len(ids) == len(set(ids))
    for model in catalog.T2I_MODELS:
        assert catalog.get(model.id) is model


def test_catalog_covers_the_requested_families():
    families = {m.family for m in catalog.T2I_MODELS}
    assert families == {"sd15", "sdxl", "flux2", "krea2"}


def test_normalize_id_maps_the_removed_runwayml_repo():
    # runwayml/stable-diffusion-v1-5 was pulled from the Hub; a verbatim id 404s.
    assert catalog.normalize_id("runwayml/stable-diffusion-v1-5") == (
        "stable-diffusion-v1-5/stable-diffusion-v1-5"
    )


def test_normalize_id_defaults_blank_to_auto():
    assert catalog.normalize_id("") == catalog.AUTO
    assert catalog.normalize_id(None) == catalog.AUTO
    assert catalog.normalize_id("  ") == catalog.AUTO


def test_get_returns_none_for_a_custom_id():
    assert catalog.get("someone/custom-merge") is None


@pytest.mark.parametrize(
    ("total_gb", "expected_family"),
    [(0, "sd15"), (8, "sdxl"), (16, "sdxl"), (16.1, "flux2"), (24, "flux2"), (48, "flux2")],
)
def test_auto_select_ladder(total_gb, expected_family):
    model = catalog.get(catalog.auto_select(total_gb))
    assert model is not None
    assert model.family == expected_family


def test_auto_select_never_picks_krea2():
    """Krea2Pipeline is absent from diffusers 0.38.

    Auto-selecting it would hand users a load failure on a machine that is
    otherwise perfectly capable, so Krea 2 stays explicitly selectable only.
    """
    for gb in (0, 8, 12, 16, 24, 32, 48, 80):
        assert catalog.get(catalog.auto_select(gb)).family != "krea2"


def test_resolve_expands_auto_against_vram():
    model_id, model = catalog.resolve("auto", 48.0)
    assert model is not None
    assert model.family == "flux2"
    assert model_id == model.id


def test_resolve_passes_custom_ids_through_without_metadata():
    model_id, model = catalog.resolve("someone/custom-merge", 24.0)
    assert model_id == "someone/custom-merge"
    assert model is None


def test_flux2_klein_matches_the_installed_diffusers_contract():
    """Verified against diffusers 0.38's Flux2KleinPipeline docstring + signature."""
    klein = catalog.get("black-forest-labs/FLUX.2-klein-base-9B")
    assert klein.pipeline_cls == "Flux2KleinPipeline"
    # Flux2KleinPipeline.__call__ takes negative_prompt_embeds, not negative_prompt.
    assert klein.supports_negative_prompt is False
    # max_sequence_length defaults to 512, unlike CLIP's 77.
    assert klein.max_prompt_tokens == 512


def test_clip_families_declare_the_77_token_limit():
    for family in ("sd15", "sdxl"):
        models = [m for m in catalog.T2I_MODELS if m.family == family]
        assert models
        assert all(m.max_prompt_tokens == 77 for m in models)


def test_catalog_imports_without_torch_or_diffusers():
    """The config schema imports this module; it must stay cheap."""
    code = (
        "import sys;"
        "import prepare_lora_kit.steps.caption_verifier.catalog;"
        "import prepare_lora_kit.steps.caption_verifier.plan;"
        "assert 'torch' not in sys.modules, 'torch was imported';"
        "assert 'diffusers' not in sys.modules, 'diffusers was imported'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
