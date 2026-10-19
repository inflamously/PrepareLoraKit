"""Tests for loading a benchmark suite and its variants."""
import pytest

from prepare_lora_kit.caption_bench.suite import BenchSuite
from prepare_lora_kit.caption_bench.variants import load_variants


def test_load_reads_cases_in_declared_order(suite_dir):
    suite = BenchSuite.load(suite_dir)

    assert suite.name == "tiny"
    assert [case.name for case in suite.cases] == ["burger.png", "beach.png"]
    assert suite.cases[0].notes == "invented food item"


def test_case_token_falls_back_to_suite_token_unless_explicitly_null(suite_dir):
    burger, beach = BenchSuite.load(suite_dir).cases

    assert burger.concept_token == "krustekrabbe"
    assert beach.concept_token is None


def test_annotations_are_normalised_to_runtime_shape(suite_dir):
    burger = BenchSuite.load(suite_dir).cases[0]

    assert burger.annotations == [
        {"label": "sesame claws", "x1": 0.1, "y1": 0.1, "x2": 0.4, "y2": 0.4},
    ]


def test_without_an_image_list_every_image_in_images_dir_is_a_case(suite_dir):
    (suite_dir / "bench.yaml").write_text("name: auto\n", encoding="utf-8")

    suite = BenchSuite.load(suite_dir)

    assert sorted(case.name for case in suite.cases) == ["beach.png", "burger.png"]
    assert all(case.annotations == [] for case in suite.cases)


def test_missing_image_is_a_clear_error(suite_dir):
    (suite_dir / "bench.yaml").write_text(
        "images:\n  - path: images/nope.png\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"nope\.png"):
        BenchSuite.load(suite_dir)


def test_bad_annotation_is_a_clear_error(suite_dir):
    (suite_dir / "bench.yaml").write_text(
        "images:\n  - path: images/beach.png\n    annotations:\n      - {label: x}\n",
        encoding="utf-8")

    with pytest.raises(ValueError, match=r"beach\.png"):
        BenchSuite.load(suite_dir)


def test_missing_bench_yaml_is_a_clear_error(tmp_path):
    with pytest.raises(ValueError, match=r"bench\.yaml"):
        BenchSuite.load(tmp_path)


def test_builtin_current_variant_uses_suite_defaults(suite_dir):
    suite = BenchSuite.load(suite_dir)

    (variant,) = load_variants(suite, ["current"])

    assert variant.name == "current"
    assert variant.config.caption_model_id == "some/model"
    assert variant.config.caption_strategy == "grounded"


def test_variant_file_overrides_suite_defaults(suite_dir):
    variants = suite_dir / "variants"
    variants.mkdir()
    (variants / "single.yaml").write_text(
        "caption_strategy: single\nmax_new_tokens: 90\n", encoding="utf-8")
    suite = BenchSuite.load(suite_dir)

    (variant,) = load_variants(suite, ["single"])

    assert variant.config.caption_strategy == "single"
    assert variant.config.max_new_tokens == 90
    assert variant.config.caption_model_id == "some/model"


def test_model_override_beats_suite_and_variant(suite_dir):
    suite = BenchSuite.load(suite_dir)

    (variant,) = load_variants(suite, ["current"], model_id="other/model")

    assert variant.config.caption_model_id == "other/model"


def test_unknown_variant_lists_the_available_ones(suite_dir):
    variants = suite_dir / "variants"
    variants.mkdir()
    (variants / "single.yaml").write_text("caption_strategy: single\n", encoding="utf-8")
    suite = BenchSuite.load(suite_dir)

    with pytest.raises(ValueError, match="current, single"):
        load_variants(suite, ["nope"])


def test_invalid_variant_setting_fails_through_config_validation(suite_dir):
    variants = suite_dir / "variants"
    variants.mkdir()
    (variants / "bad.yaml").write_text("caption_strategy: telepathy\n", encoding="utf-8")
    suite = BenchSuite.load(suite_dir)

    with pytest.raises(ValueError, match="caption_strategy"):
        load_variants(suite, ["bad"])


def test_unknown_variant_key_is_rejected(suite_dir):
    variants = suite_dir / "variants"
    variants.mkdir()
    (variants / "typo.yaml").write_text("caption_stratgy: single\n", encoding="utf-8")
    suite = BenchSuite.load(suite_dir)

    with pytest.raises(ValueError, match="caption_stratgy"):
        load_variants(suite, ["typo"])
