import json

import pytest

from prepare_lora_kit.project.config_schema import (
    apply_overrides,
    has_schema,
    schema_payload,
)
from prepare_lora_kit_pipeline.configs import (
    AuditConfig,
    CaptionConfig,
    VaeGateConfig,
)
from prepare_lora_kit_pipeline.configuration import STEP_TYPE_MAP


def test_schema_payload_is_json_able_for_every_step():
    for step_type in STEP_TYPE_MAP:
        json.dumps(schema_payload(step_type))


def test_import_step_has_no_schema_other_steps_do():
    assert has_schema("ImportStep") is False
    assert has_schema("CaptionStep") is True


def test_apply_overrides_coerces_and_validates_caption():
    cfg = CaptionConfig()
    result = apply_overrides(
        "CaptionStep",
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
    cfg = CaptionConfig()
    assert apply_overrides("CaptionStep", cfg, {"not_a_field": 1}) is cfg


def test_apply_overrides_clears_nullable_field_on_blank():
    cfg = CaptionConfig(caption_model_id="Qwen/Qwen2-VL-7B-Instruct")
    result = apply_overrides("CaptionStep", cfg, {"caption_model_id": ""})
    assert result.caption_model_id is None


def test_apply_overrides_keeps_default_for_blank_non_nullable():
    cfg = CaptionConfig()
    result = apply_overrides("CaptionStep", cfg, {"max_new_tokens": ""})
    assert result.max_new_tokens == 200


def test_apply_overrides_rejects_invalid_value():
    with pytest.raises(ValueError):
        apply_overrides("CaptionStep", CaptionConfig(), {"spot_check_pct": "2"})


def test_apply_overrides_runs_dataclass_validation():
    with pytest.raises(ValueError):
        apply_overrides("VaeGateStep", VaeGateConfig(), {"gaussian_blur_kernel": "20"})


def test_apply_overrides_handles_bool_checkbox():
    result = apply_overrides(
        "AuditStep", AuditConfig(), {"check_pairing": False, "min_caption": "3"}
    )
    assert result.check_pairing is False
    assert result.min_caption == 3
