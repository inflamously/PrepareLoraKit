"""`enabled: false` in index.yaml — parking a step without losing its settings.

A parked step is simply absent from ``ProjectConfig.pipeline``, which is a state
the engine, the validator and the UI payload have always handled (optional steps
could always be omitted). What is new is that the step's ``<step>.yaml`` stays on
disk, so parking is reversible.
"""
import pytest
import yaml

from prepare_lora_kit.project import store
from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit.project.project_registry import default_project_data
from prepare_lora_kit_ui.runner import project_payload


def _project(yaml_text: str) -> ProjectConfig:
    return ProjectConfig.from_data(yaml.safe_load(yaml_text))


FULL_HEAD = """\
name: sample
pipeline:
  - type: ImportStep
  - type: QualityGateStep
  - type: CurateStep
"""


def test_disabled_step_is_absent_from_the_loaded_pipeline():
    cfg = _project(
        FULL_HEAD
        + """\
  - type: UpscaleStep
    enabled: false
  - type: CaptionBboxStep
"""
    )

    assert [step.type for step in cfg.pipeline] == [
        "ImportStep",
        "QualityGateStep",
        "CurateStep",
        "CaptionBboxStep",
    ]
    assert cfg.disabled_types == ("UpscaleStep",)


def test_disabled_step_config_is_not_validated():
    """A step you switched off must never be able to block a load."""
    cfg = _project(
        FULL_HEAD
        + """\
  - type: UpscaleStep
    enabled: false
    upscale_model: nonsense
"""
    )

    assert [step.type for step in cfg.pipeline] == [
        "ImportStep",
        "QualityGateStep",
        "CurateStep",
    ]


def test_disabling_an_unknown_step_type_still_raises():
    with pytest.raises(ValueError, match="Unknown step type"):
        _project(
            """\
name: sample
pipeline:
  - type: NoSuchStep
    enabled: false
"""
        )


def test_disabling_a_prerequisite_names_index_yaml_and_the_fix():
    with pytest.raises(ValueError) as excinfo:
        _project(
            """\
name: sample
pipeline:
  - type: ImportStep
  - type: QualityGateStep
    enabled: false
  - type: CurateStep
"""
        )

    message = str(excinfo.value)
    assert "disabled in index.yaml" in message
    assert "step: quality_gate, enabled: true" in message


def test_disabling_a_non_optional_leaf_step_is_allowed():
    """`optional` is a UI-default flag, not permission to omit.

    Non-optional steps are routinely absent from real pipelines, so disabling one
    that nothing depends on must load cleanly. The prerequisite graph is the only
    constraint on membership.
    """
    cfg = _project(
        FULL_HEAD
        + """\
  - type: CaptionBboxStep
  - type: VaeGateStep
  - type: AuditStep
  - type: BucketPoolsCheckStep
    enabled: false
"""
    )

    assert "BucketPoolsCheckStep" not in [step.type for step in cfg.pipeline]
    assert cfg.disabled_types == ("BucketPoolsCheckStep",)


def test_disabled_step_is_absent_from_the_ui_payload():
    cfg = _project(
        FULL_HEAD
        + """\
  - type: UpscaleStep
    enabled: false
  - type: CaptionBboxStep
"""
    )

    payload = project_payload(cfg)

    assert "UpscaleStep" not in [step["type"] for step in payload["steps"]]


def test_disabled_step_keeps_its_file_and_settings_on_disk(isolated_projects):
    data = default_project_data("demo")
    upscale = next(s for s in data["pipeline"] if s["type"] == "UpscaleStep")
    upscale["upscale_target"] = 4096
    upscale["enabled"] = False
    directory = store.project_dir_for_name("demo")
    store.write_project_folder(directory, data)

    cfg = ProjectConfig.from_dir(directory)

    assert "UpscaleStep" not in [step.type for step in cfg.pipeline]
    parked = yaml.safe_load((directory / "upscale.yaml").read_text())
    assert parked["upscale_target"] == 4096


def test_re_enabling_restores_the_step_with_its_settings(isolated_projects):
    data = default_project_data("demo")
    upscale = next(s for s in data["pipeline"] if s["type"] == "UpscaleStep")
    upscale["upscale_target"] = 4096
    upscale["enabled"] = False
    directory = store.project_dir_for_name("demo")
    store.write_project_folder(directory, data)

    index = yaml.safe_load((directory / "index.yaml").read_text())
    for entry in index["pipeline"]:
        if entry["step"] == "upscale":
            entry["enabled"] = True
    (directory / "index.yaml").write_text(yaml.safe_dump(index, sort_keys=False))

    cfg = ProjectConfig.from_dir(directory)
    restored = next(step for step in cfg.pipeline if step.type == "UpscaleStep")

    assert restored.config.upscale_target == 4096
