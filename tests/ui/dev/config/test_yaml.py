from prepare_lora_kit.project.base import ProjectConfig


def test_project_config_can_parse_curate_skip_clip():
    project = ProjectConfig.from_data(
        {
            "name": "mock",
            "pipeline": [
                {"type": "ImportStep"},
                {"type": "QualityGateStep"},
                {"type": "CurateStep", "skip_clip": True},
            ],
        }
    )

    assert project.pipeline[2].config.skip_clip is True
