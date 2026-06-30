"""Tests for the Curate-step embedding model catalog."""
import pytest

from prepare_lora_kit.embedding import catalog


@pytest.mark.parametrize(
    ("vram_gb", "expected"),
    [
        (0, "ViT-B-32"),
        (8, "ViT-B-32"),
        (16, "ViT-B-32"),
        (24, "facebook/dinov2-base"),
        (32, "Qwen/Qwen3-VL-Embedding-2B"),
        (48, "Qwen/Qwen3-VL-Embedding-8B"),
    ],
)
def test_auto_select_ladder(vram_gb, expected):
    assert catalog.auto_select(vram_gb) == expected


def test_coverage_choices_lists_auto_first_and_all_families():
    choices = catalog.coverage_choices()

    assert choices[0] == ("auto", "Auto (match VRAM)")
    assert len(choices) == 1 + len(catalog.COVERAGE_MODELS)
    families = {catalog.get(v).family for v, _ in choices[1:]}
    assert families == {"clip", "dinov2", "qwen"}


def test_normalize_id_maps_legacy_hf_repo_to_open_clip_name():
    assert catalog.normalize_id("openai/clip-vit-base-patch32") == "ViT-B-32"
    assert catalog.normalize_id("openai/clip-vit-large-patch14") == "ViT-L-14"


def test_normalize_id_defaults_blank_to_default_clip():
    assert catalog.normalize_id(None) == catalog.DEFAULT_CLIP_ID
    assert catalog.normalize_id("") == catalog.DEFAULT_CLIP_ID


def test_normalize_id_passes_through_unknown_ids():
    assert catalog.normalize_id("ViT-L-14") == "ViT-L-14"
    assert catalog.normalize_id("some/custom-model") == "some/custom-model"


def test_get_resolves_aliases_and_returns_none_for_custom():
    assert catalog.get("openai/clip-vit-base-patch32").id == "ViT-B-32"
    assert catalog.get("facebook/dinov2-base").dim == 768
    assert catalog.get("totally-custom-id") is None


def test_arch_overrides_for_shared_architecture_variants():
    # DataComp/378px variants reuse a base open_clip arch with different weights.
    assert catalog.get("ViT-L-14-datacomp").arch == "ViT-L-14"
    assert catalog.get("ViT-L-14-datacomp").open_clip_pretrained == "datacomp_xl_s13b_b90k"
    assert catalog.get("ViT-H-14-378").arch == "ViT-H-14-378-quickgelu"


def test_clip_arch_defaults_to_id():
    assert catalog.get("ViT-B-32").arch == "ViT-B-32"
