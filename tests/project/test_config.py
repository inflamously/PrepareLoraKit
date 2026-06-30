import yaml
import pytest

from prepare_lora_kit.steps.s3_upscale.seedvr2_catalog import (
    DEFAULT_SEEDVR2_DIT_MODEL,
    SUPPORTED_SEEDVR2_DIT_MODELS,
    get_seedvr2_dit_model,
    list_seedvr2_dit_models,
)
from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit.project.steps import OPTIONAL_STEP_TYPES, STEP_PREREQUISITES
from prepare_lora_kit.project import registry as project_registry
from prepare_lora_kit.project.configs import UpscaleConfig
from prepare_lora_kit.ui.runner import project_payload


def test_project_config_from_yaml_parses_input_dir(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("""\
name: sample
network: flux-klein-9b
input_dir: /data/images
pipeline: []
""")

    cfg = ProjectConfig.from_yaml(path)

    assert cfg.input_dir == "/data/images"


def test_default_project_creation_writes_input_dir_and_pipeline(tmp_path):
    input_dir = tmp_path / "images"
    path = tmp_path / "sample.yaml"

    written = project_registry.write_default_project("sample", path, input_dir)
    data = yaml.safe_load(written.read_text())

    assert data["name"] == "sample"
    assert data["network"] == "flux-klein-9b"
    assert data["input_dir"] == str(input_dir)
    assert [step["type"] for step in data["pipeline"]] == [
        "ImportStep",
        "QualityGateStep",
        "CurateStep",
        "UpscaleStep",
        "CaptionStep",
        "VaeGateStep",
        "AuditStep",
        "ConfigGenStep",
        "BucketDryRunStep",
    ]
    upscale = next(step for step in data["pipeline"] if step["type"] == "UpscaleStep")
    caption = next(step for step in data["pipeline"] if step["type"] == "CaptionStep")
    assert upscale["upscale_target"] == 3072
    assert upscale["upscale_model"] == "seedvr2"
    assert "use_seedvr" not in upscale
    assert caption["caption_model_id"] is None
    assert caption["caption_model_task"] == "auto"
    assert caption["vram_tier"] == "auto"


def test_project_config_inserts_import_step_for_legacy_quality_first_yaml(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("""\
name: sample
network: flux-klein-9b
pipeline:
  - type: QualityGateStep
""")

    cfg = ProjectConfig.from_yaml(path)

    assert [step.type for step in cfg.pipeline] == ["ImportStep", "QualityGateStep"]
    assert [substep.id for substep in cfg.pipeline[0].substeps] == ["s0_import"]
    assert [substep.id for substep in cfg.pipeline[1].substeps] == ["s1_1_score", "s1_2_decide"]


def test_project_config_parses_substep_enabled_flags(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("""\
name: sample
network: flux-klein-9b
pipeline:
  - type: ImportStep
  - type: QualityGateStep
  - type: CurateStep
    substeps:
      - {id: s2_1_dupecheck, enabled: true}
      - {id: s2_2_clipscan, enabled: false}
      - {id: s2_3_drop_images, enabled: true}
""")

    cfg = ProjectConfig.from_yaml(path)
    curate = cfg.pipeline[2]

    assert {substep.id: substep.enabled for substep in curate.substeps} == {
        "s2_1_dupecheck": True,
        "s2_2_clipscan": False,
        "s2_3_drop_images": True,
    }


def test_project_config_rejects_unknown_substep(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("""\
name: sample
network: flux-klein-9b
pipeline:
  - type: ImportStep
    substeps:
      - {id: s9_unknown, enabled: true}
""")

    with pytest.raises(ValueError, match="unknown substep"):
        ProjectConfig.from_yaml(path)


def test_project_config_maps_legacy_skip_clip_to_curate_substep(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("""\
name: sample
network: flux-klein-9b
pipeline:
  - type: ImportStep
  - type: QualityGateStep
  - type: CurateStep
    skip_clip: true
""")

    cfg = ProjectConfig.from_yaml(path)
    curate = cfg.pipeline[2]

    assert {substep.id: substep.enabled for substep in curate.substeps}["s2_2_clipscan"] is False


def test_project_config_rejects_downstream_step_without_previous_step(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("""\
name: sample
network: flux-klein-9b
pipeline:
  - type: CurateStep
""")

    with pytest.raises(ValueError, match="CurateStep.*QualityGateStep"):
        ProjectConfig.from_yaml(path)


def test_project_config_allows_omitting_optional_upscale_step(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("""\
name: sample
network: flux-klein-9b
pipeline:
  - type: ImportStep
  - type: QualityGateStep
  - type: CurateStep
  - type: CaptionStep
  - type: VaeGateStep
""")

    cfg = ProjectConfig.from_yaml(path)

    assert [step.type for step in cfg.pipeline] == [
        "ImportStep",
        "QualityGateStep",
        "CurateStep",
        "CaptionStep",
        "VaeGateStep",
    ]


def test_project_config_rejects_optional_upscale_out_of_order(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("""\
name: sample
network: flux-klein-9b
pipeline:
  - type: ImportStep
  - type: QualityGateStep
  - type: CurateStep
  - type: CaptionStep
  - type: UpscaleStep
""")

    with pytest.raises(ValueError, match="UpscaleStep.*out of order"):
        ProjectConfig.from_yaml(path)


def test_step_prerequisites_allow_optional_upscale_step():
    assert STEP_PREREQUISITES == {
        "QualityGateStep": ["ImportStep"],
        "CurateStep": ["QualityGateStep"],
        "UpscaleStep": ["CurateStep"],
        "CaptionStep": ["CurateStep"],
        "VaeGateStep": [],
        "AuditStep": ["CaptionStep"],
        "ConfigGenStep": ["AuditStep"],
        "BucketDryRunStep": ["ConfigGenStep"],
    }


def test_optional_step_types_marks_upscale_optional():
    assert OPTIONAL_STEP_TYPES == {"UpscaleStep"}


def test_upscale_config_defaults_to_seedvr2():
    cfg = UpscaleConfig()

    assert cfg.upscale_model == "seedvr2"
    assert cfg.seedvr2_submodule_dir is None
    assert cfg.seedvr2_model_dir is None
    assert cfg.seedvr2_dit_model == DEFAULT_SEEDVR2_DIT_MODEL
    assert cfg.seedvr2_batch_size == 1
    assert cfg.seedvr2_vae_tiled is True
    assert cfg.seedvr2_cache_models is True
    assert cfg.seedvr2_model_residency == "auto"
    assert cfg.seedvr2_debug is False


def test_seedvr2_catalog_lists_supported_models():
    models = list_seedvr2_dit_models()

    assert len(models) == 10
    assert DEFAULT_SEEDVR2_DIT_MODEL == "seedvr2_ema_3b_fp8_e4m3fn.safetensors"
    assert SUPPORTED_SEEDVR2_DIT_MODELS == tuple(model.name for model in models)
    assert get_seedvr2_dit_model("seedvr2_ema_7b-Q4_K_M.gguf").parameter_size == "7B"


@pytest.mark.parametrize("value", [None, ""])
def test_upscale_config_normalizes_blank_seedvr2_dit_model(value):
    cfg = UpscaleConfig(seedvr2_dit_model=value)

    assert cfg.seedvr2_dit_model == DEFAULT_SEEDVR2_DIT_MODEL


@pytest.mark.parametrize(
    "model_name",
    [
        "seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors",
        "seedvr2_ema_7b-Q4_K_M.gguf",
    ],
)
def test_upscale_config_accepts_known_seedvr2_dit_models_without_warning(model_name, recwarn):
    cfg = UpscaleConfig(seedvr2_dit_model=model_name)

    assert cfg.seedvr2_dit_model == model_name
    assert not recwarn


def test_upscale_config_warns_for_unknown_seedvr2_dit_model_but_allows_it():
    with pytest.warns(UserWarning, match="not in PrepareLoraKit's supported catalog"):
        cfg = UpscaleConfig(seedvr2_dit_model="local_seedvr2_experiment.safetensors")

    assert cfg.seedvr2_dit_model == "local_seedvr2_experiment.safetensors"


def test_upscale_config_accepts_deprecated_seedvr_alias():
    with pytest.warns(DeprecationWarning, match="upscale_model=seedvr"):
        cfg = UpscaleConfig(upscale_model="seedvr")

    assert cfg.upscale_model == "seedvr2"


def test_upscale_config_rejects_unknown_model():
    with pytest.raises(ValueError, match="seedvr2\\|lanczos\\|custom"):
        UpscaleConfig(upscale_model="nearest")


def test_project_config_from_yaml_parses_seedvr2_fields(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("""\
name: sample
network: flux-klein-9b
pipeline:
  - type: ImportStep
  - type: QualityGateStep
  - type: CurateStep
  - type: UpscaleStep
    upscale_model: seedvr2
    seedvr2_submodule_dir: /opt/seedvr2
    seedvr2_model_dir: /models/seedvr2
    seedvr2_cuda_device: "1"
    seedvr2_batch_size: 5
    seedvr2_vae_tiled: false
    seedvr2_cache_models: false
    seedvr2_model_residency: cpu
    seedvr2_debug: true
""")

    cfg = ProjectConfig.from_yaml(path)
    upscale = cfg.pipeline[3].config

    assert upscale.upscale_model == "seedvr2"
    assert upscale.seedvr2_submodule_dir == "/opt/seedvr2"
    assert upscale.seedvr2_model_dir == "/models/seedvr2"
    assert upscale.seedvr2_cuda_device == "1"
    assert upscale.seedvr2_batch_size == 5
    assert upscale.seedvr2_vae_tiled is False
    assert upscale.seedvr2_cache_models is False
    assert upscale.seedvr2_model_residency == "cpu"
    assert upscale.seedvr2_debug is True


def test_upscale_config_rejects_unknown_seedvr2_model_residency():
    with pytest.raises(ValueError, match="seedvr2_model_residency"):
        UpscaleConfig(seedvr2_model_residency="vram")


@pytest.mark.parametrize("yaml_value", ["", "null", '""'])
def test_project_config_from_yaml_normalizes_blank_seedvr2_dit_model(tmp_path, yaml_value):
    path = tmp_path / "project.yaml"
    path.write_text(f"""\
name: sample
network: flux-klein-9b
pipeline:
  - type: ImportStep
  - type: QualityGateStep
  - type: CurateStep
  - type: UpscaleStep
    upscale_model: seedvr2
    seedvr2_dit_model: {yaml_value}
""")

    cfg = ProjectConfig.from_yaml(path)
    upscale = cfg.pipeline[3].config

    assert upscale.seedvr2_dit_model == DEFAULT_SEEDVR2_DIT_MODEL


def test_project_payload_includes_input_dir():
    cfg = ProjectConfig(name="sample", network="flux-klein-9b", input_dir="/data/images")

    payload = project_payload(cfg)

    assert payload["input_dir"] == "/data/images"


def test_project_payload_marks_upscale_optional(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("""\
name: sample
network: flux-klein-9b
pipeline:
  - type: ImportStep
  - type: QualityGateStep
  - type: CurateStep
  - type: UpscaleStep
  - type: CaptionStep
  - type: VaeGateStep
""")

    payload = project_payload(ProjectConfig.from_yaml(path))

    optional = {step["type"]: step["optional"] for step in payload["steps"]}
    assert optional["UpscaleStep"] is True
    assert optional["VaeGateStep"] is False


def test_project_payload_includes_substep_metadata(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("""\
name: sample
network: flux-klein-9b
pipeline:
  - type: ImportStep
""")
    cfg = ProjectConfig.from_yaml(path)

    payload = project_payload(cfg, tmp_path / "out")
    import_step = next(step for step in payload["steps"] if step["type"] == "ImportStep")

    assert import_step["substeps"] == [
        {
            "id": "s0_import",
            "label": "Import source images",
            "enabled": True,
            "status": "pending",
            "prerequisites": [],
            "optional": False,
        }
    ]
