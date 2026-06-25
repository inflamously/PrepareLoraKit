from prepare_lora_kit.project.base import ProjectConfig


def test_project_yaml_can_parse_curate_skip_clip(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text(
        """\
name: mock
network: flux-klein-9b
pipeline:
  - type: ImportStep
  - type: QualityGateStep
  - type: CurateStep
    skip_clip: true
"""
    )

    project = ProjectConfig.from_yaml(path)

    assert project.pipeline[2].config.skip_clip is True
