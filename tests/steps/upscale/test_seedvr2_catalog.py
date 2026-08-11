"""Tests for the Upscale-step SeedVR2 DiT model catalog."""
import pytest

from prepare_lora_kit.steps.upscale import seedvr2_catalog as catalog

_3B_FP8 = "seedvr2_ema_3b_fp8_e4m3fn.safetensors"
_7B_FP8 = "seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors"
_7B_FP16 = "seedvr2_ema_7b_fp16.safetensors"


@pytest.mark.parametrize(
    ("vram_gb", "expected"),
    [
        (0, _3B_FP8),      # no CUDA -> the lowest pick, never nothing
        (8, _3B_FP8),
        (12, _3B_FP8),
        (16, _3B_FP8),
        (24, _7B_FP8),     # README's recommended 20-24 GB 7B entry point
        (32, _7B_FP8),
        (40, _7B_FP16),
        (80, _7B_FP16),
    ],
)
def test_auto_select_ladder(vram_gb, expected):
    assert catalog.auto_select(vram_gb) == expected


def test_auto_select_never_picks_a_sharp_variant():
    # Sharp is a look, not a quality tier — Auto must not silently change the style.
    picks = {catalog.auto_select(gb) for gb in (0, 8, 16, 24, 40, 80, 200)}

    assert all(catalog.get_seedvr2_dit_model(name).variant == "base" for name in picks)


def test_auto_select_handles_missing_vram_readings():
    assert catalog.auto_select(0.0) == catalog.DEFAULT_SEEDVR2_DIT_MODEL
    assert catalog.auto_select(-1.0) == catalog.DEFAULT_SEEDVR2_DIT_MODEL


def test_dit_model_choices_lists_auto_first_then_every_catalog_model():
    choices = catalog.dit_model_choices()

    assert choices[0] == (catalog.AUTO, "Auto (match VRAM)")
    assert len(choices) == 1 + len(catalog.list_seedvr2_dit_models())
    assert all(catalog.get_seedvr2_dit_model(value) for value, _ in choices[1:])


def test_catalog_is_ordered_lowest_vram_first_with_sharp_variants_last():
    models = catalog.list_seedvr2_dit_models()
    base = [m for m in models if m.variant == "base"]
    sharp = [m for m in models if m.variant == "sharp"]

    assert [m.name for m in models] == [m.name for m in base + sharp]
    for group in (base, sharp):
        vram = [m.min_gpu_residency_gb for m in group]
        assert vram == sorted(vram)


def test_default_is_the_lowest_quality_safetensors_3b_model():
    assert catalog.DEFAULT_SEEDVR2_DIT_MODEL == _3B_FP8
    assert catalog.get_seedvr2_dit_model(catalog.DEFAULT_SEEDVR2_DIT_MODEL) is not None


def test_dit_model_choices_marks_only_downloaded_models():
    downloaded = {"seedvr2_ema_3b_fp16.safetensors"}

    labels = dict(catalog.dit_model_choices(downloaded))

    assert "downloaded" in labels["seedvr2_ema_3b_fp16.safetensors"]
    assert "download" in labels[_7B_FP16]
    assert "downloaded" not in labels[_7B_FP16]
    assert "download" not in labels[catalog.AUTO]


def test_dit_model_choices_labels_carry_vram_and_size():
    labels = dict(catalog.dit_model_choices())

    assert labels[_7B_FP16].startswith("7B fp16 — 40 GB VRAM")
    assert "15.3 GB download" in labels[_7B_FP16]


@pytest.mark.parametrize("model", catalog.list_seedvr2_dit_models(), ids=lambda m: m.name)
def test_residency_thresholds_match_the_legacy_filename_heuristic(model):
    # The worker used to sniff these out of the filename. The catalog now owns the
    # numbers, so pin them to the old rule to catch silent residency drift.
    name = model.name.lower()
    pure_fp16 = "fp16" in name and "fp8" not in name
    if "7b" in name and pure_fp16:
        expected = 40.0
    elif "7b" in name or pure_fp16:
        expected = 24.0
    else:
        expected = 16.0

    assert model.min_gpu_residency_gb == expected


def test_quality_rank_orders_precision_and_parameter_size():
    by_name = {m.name: m for m in catalog.list_seedvr2_dit_models()}
    rank = {name: model.quality_rank for name, model in by_name.items()}

    assert (rank["seedvr2_ema_3b-Q4_K_M.gguf"]
            < rank["seedvr2_ema_3b-Q8_0.gguf"]
            < rank[_3B_FP8]
            < rank["seedvr2_ema_3b_fp16.safetensors"])
    assert rank["seedvr2_ema_3b_fp16.safetensors"] < rank["seedvr2_ema_7b-Q4_K_M.gguf"]
    assert rank["seedvr2_ema_7b-Q4_K_M.gguf"] < rank[_7B_FP8] < rank[_7B_FP16]
