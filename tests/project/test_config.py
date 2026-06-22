import yaml

from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit.project import registry as project_registry
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
        "QualityGateStep",
        "CurateStep",
        "UpscaleStep",
        "VaeGateStep",
        "CaptionStep",
        "AuditStep",
        "ConfigGenStep",
        "BucketDryRunStep",
    ]
    upscale = next(step for step in data["pipeline"] if step["type"] == "UpscaleStep")
    caption = next(step for step in data["pipeline"] if step["type"] == "CaptionStep")
    assert upscale["upscale_target"] == 3072
    assert upscale["upscale_model"] == "seedvr"
    assert "use_seedvr" not in upscale
    assert caption["vram_tier"] == "auto"


def test_project_payload_includes_input_dir():
    cfg = ProjectConfig(name="sample", network="flux-klein-9b", input_dir="/data/images")

    payload = project_payload(cfg)

    assert payload["input_dir"] == "/data/images"
