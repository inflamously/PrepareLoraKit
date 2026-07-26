import dataclasses

import pytest
import yaml

from prepare_lora_kit import settings
from prepare_lora_kit.pipeline.configuration import step_config_class
from prepare_lora_kit.project import project_registry
from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit.settings.model import AppSettings
from prepare_lora_kit.settings.seeding import _SEEDS, apply_settings_to_pipeline


def _step(pipeline, step_type):
    return next(step for step in pipeline if step["type"] == step_type)


def test_every_seed_targets_a_real_step_field():
    """Guards against the seed table drifting from the config dataclasses."""
    for step_type, field, group_name, group_field in _SEEDS:
        config_cls = step_config_class(step_type)
        names = {f.name for f in dataclasses.fields(config_cls)}
        assert field in names, f"{step_type} has no field '{field}'"

        group = getattr(AppSettings(), group_name)
        assert hasattr(group, group_field), f"settings.{group_name} has no '{group_field}'"


def test_default_settings_reproduce_todays_pipeline_exactly():
    """With nothing configured the feature must be a complete no-op."""
    raw = project_registry._default_pipeline()

    assert apply_settings_to_pipeline(raw, AppSettings()) == project_registry._default_pipeline()


def test_configured_defaults_are_seeded_into_a_new_project(tmp_path):
    settings.save_settings_dict(
        {
            "hardware": {"vram_tier": "low"},
            "project_defaults": {
                "caption_model_id": "Qwen/Qwen3-VL-4B-Instruct",
                "vae_model_id": "stabilityai/sdxl-vae",
                "coverage_embedding_model": "ViT-B-32",
                "caption_model_type": "clip",
            },
        }
    )

    path = project_registry.write_default_project("seeded", tmp_path / "seeded.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert _step(data["pipeline"], "CaptionBboxStep")["caption_model_id"] == "Qwen/Qwen3-VL-4B-Instruct"
    assert _step(data["pipeline"], "CaptionBboxStep")["vram_tier"] == "low"
    assert _step(data["pipeline"], "CaptionVerifierStep")["vram_tier"] == "low"
    assert _step(data["pipeline"], "VaeGateStep")["vae_model_id"] == "stabilityai/sdxl-vae"
    assert _step(data["pipeline"], "CurateStep")["coverage_embedding_model"] == "ViT-B-32"
    assert _step(data["pipeline"], "AuditStep")["caption_model_type"] == "clip"


def test_a_seeded_project_still_loads_and_validates(tmp_path):
    settings.save_settings_dict(
        {"project_defaults": {"caption_model_id": "Qwen/Qwen3-VL-8B-Instruct"}}
    )
    path = project_registry.write_default_project("seeded", tmp_path / "seeded.yaml")

    config = ProjectConfig.from_yaml(path)

    caption = next(s for s in config.pipeline if s.type == "CaptionBboxStep")
    assert caption.config.caption_model_id == "Qwen/Qwen3-VL-8B-Instruct"


def test_existing_project_yaml_is_untouched_by_settings(tmp_path):
    """The precedence promise: globals seed creation only, never a live override."""
    path = project_registry.write_default_project("existing", tmp_path / "existing.yaml")
    before = path.read_bytes()

    settings.save_settings_dict(
        {
            "hardware": {"vram_tier": "max"},
            "project_defaults": {
                "caption_model_id": "some/other-model",
                "vae_model_id": "some/other-vae",
                "t2i_model_id": "some/other-t2i",
            },
        }
    )
    config = ProjectConfig.from_yaml(path)

    assert path.read_bytes() == before
    caption = next(s for s in config.pipeline if s.type == "CaptionBboxStep")
    assert caption.config.caption_model_id is None
    assert caption.config.vram_tier == "auto"


def test_apply_does_not_mutate_the_input_list():
    raw = project_registry._default_pipeline()
    snapshot = [dict(step) for step in raw]

    apply_settings_to_pipeline(raw, AppSettings.from_dict({"hardware": {"vram_tier": "high"}}))

    assert raw == snapshot


@pytest.mark.parametrize("tier", ["low", "mid", "high", "max"])
def test_seeded_vram_tier_is_accepted_by_both_step_configs(tier, tmp_path):
    settings.save_settings_dict({"hardware": {"vram_tier": tier}})
    path = project_registry.write_default_project("tiered", tmp_path / "tiered.yaml")

    config = ProjectConfig.from_yaml(path)

    tiers = {s.type: getattr(s.config, "vram_tier", None) for s in config.pipeline}
    assert tiers["CaptionBboxStep"] == tier
    assert tiers["CaptionVerifierStep"] == tier
