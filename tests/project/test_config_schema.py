import json

import pytest

from prepare_lora_kit.pipeline import step_types
from prepare_lora_kit.pipeline.configs import (
    AuditConfig,
    CaptionBboxConfig,
    UpscaleConfig,
    VaeGateConfig,
)
from prepare_lora_kit.project.config_schema import (
    apply_overrides,
    has_schema,
    query,
    schema_payload,
)
from prepare_lora_kit.steps.upscale.seedvr2_catalog import AUTO as SEEDVR2_DIT_MODEL_AUTO


def _field(step_type: str, name: str) -> dict:
    return next(f for f in schema_payload(step_type) if f["name"] == name)


def test_schema_payload_is_json_able_for_every_step():
    for step_type in step_types():
        json.dumps(schema_payload(step_type))


def test_import_step_has_no_schema_other_steps_do():
    assert has_schema("ImportStep") is False
    assert has_schema("CaptionBboxStep") is True


def test_apply_overrides_coerces_and_validates_caption():
    cfg = CaptionBboxConfig()
    result = apply_overrides(
        "CaptionBboxStep",
        cfg,
        {
            "caption_model_id": "Qwen/Qwen2-VL-7B-Instruct",
            "vram_tier": "low",
            "max_new_tokens": "150",  # string from the form
            "spot_check_pct": "0.2",
        },
    )
    assert result.caption_model_id == "Qwen/Qwen2-VL-7B-Instruct"
    assert result.vram_tier == "low"
    assert result.max_new_tokens == 150
    assert result.spot_check_pct == pytest.approx(0.2)
    assert result.quantization == "4bit"  # derived from vram_tier
    assert cfg.max_new_tokens == 200  # original untouched


def test_apply_overrides_ignores_unknown_keys():
    cfg = CaptionBboxConfig()
    assert apply_overrides("CaptionBboxStep", cfg, {"not_a_field": 1}) is cfg


def test_apply_overrides_clears_nullable_field_on_blank():
    cfg = CaptionBboxConfig(caption_model_id="Qwen/Qwen2-VL-7B-Instruct")
    result = apply_overrides("CaptionBboxStep", cfg, {"caption_model_id": ""})
    assert result.caption_model_id is None


def test_apply_overrides_keeps_default_for_blank_non_nullable():
    cfg = CaptionBboxConfig()
    result = apply_overrides("CaptionBboxStep", cfg, {"max_new_tokens": ""})
    assert result.max_new_tokens == 200


def test_apply_overrides_rejects_invalid_value():
    with pytest.raises(ValueError):
        apply_overrides("CaptionBboxStep", CaptionBboxConfig(), {"spot_check_pct": "2"})


def test_apply_overrides_runs_dataclass_validation():
    with pytest.raises(ValueError):
        apply_overrides("VaeGateStep", VaeGateConfig(), {"gaussian_blur_kernel": "20"})


def test_apply_overrides_handles_bool_checkbox():
    result = apply_overrides(
        "AuditStep", AuditConfig(), {"check_pairing": False, "min_caption": "3"}
    )
    assert result.check_pairing is False
    assert result.min_caption == 3


def test_seedvr2_dit_model_is_a_catalog_backed_select():
    field = _field("UpscaleStep", "seedvr2_dit_model")

    assert field["control"] == "select"
    assert field["allow_custom"] is True  # local checkpoints stay reachable
    assert field["options"][0]["value"] == SEEDVR2_DIT_MODEL_AUTO
    assert len(field["options"]) > 1


def test_apply_overrides_accepts_catalog_and_custom_seedvr2_dit_models():
    catalog_pick = apply_overrides(
        "UpscaleStep", UpscaleConfig(),
        {"seedvr2_dit_model": "seedvr2_ema_7b_fp16.safetensors"},
    )
    assert catalog_pick.seedvr2_dit_model == "seedvr2_ema_7b_fp16.safetensors"

    with pytest.warns(UserWarning, match="not in PrepareLoraKit's supported catalog"):
        custom = apply_overrides(
            "UpscaleStep", UpscaleConfig(), {"seedvr2_dit_model": "my_local.safetensors"}
        )
    assert custom.seedvr2_dit_model == "my_local.safetensors"


def test_apply_overrides_clears_seedvr2_dit_model_back_to_auto():
    cfg = UpscaleConfig(seedvr2_dit_model="seedvr2_ema_7b_fp16.safetensors")

    result = apply_overrides("UpscaleStep", cfg, {"seedvr2_dit_model": ""})

    assert result.seedvr2_dit_model == SEEDVR2_DIT_MODEL_AUTO


def test_schema_payload_refreshes_provided_options_per_call(monkeypatch):
    monkeypatch.setitem(
        query.CONFIG_FIELD_OPTIONS["UpscaleStep"],
        "seedvr2_dit_model",
        lambda: [("only", "Only one")],
    )

    assert _field("UpscaleStep", "seedvr2_dit_model")["options"] == [
        {"value": "only", "label": "Only one"}
    ]


def test_schema_payload_falls_back_to_declared_options_when_a_provider_fails(monkeypatch):
    def boom():
        raise OSError("model cache is unreadable")

    monkeypatch.setitem(
        query.CONFIG_FIELD_OPTIONS["UpscaleStep"], "seedvr2_dit_model", boom
    )

    # A broken disk scan must degrade to the static catalog, not break the modal.
    options = _field("UpscaleStep", "seedvr2_dit_model")["options"]
    assert options[0]["value"] == SEEDVR2_DIT_MODEL_AUTO
