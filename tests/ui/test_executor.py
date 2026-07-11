from unittest.mock import MagicMock, patch

from prepare_lora_kit.pipeline.configs import ImportConfig, QualityGateConfig
from prepare_lora_kit.project.base import PipelineStep, ProjectConfig
from prepare_lora_kit_ui.runner import JobManager, PipelineJob, UiPipelineExecutor


def _project() -> ProjectConfig:
    return ProjectConfig(
        name="test",
        pipeline=[
            PipelineStep("ImportStep", ImportConfig()),
            PipelineStep("QualityGateStep", QualityGateConfig(auto_only=False)),
        ],
    )


def test_executor_maps_engine_result_and_runtime_options_to_job(tmp_path):
    captured: dict[str, object] = {}

    class Interaction:
        def __init__(self, job, media_base_url=None):
            captured["job"] = job
            captured["media_base_url"] = media_base_url

    def invoke(*_args, **kwargs):
        captured.update(kwargs)

    manager = JobManager()
    job = PipelineJob(manager, "test-job")
    executor = UiPipelineExecutor(
        media_base_url="http://localhost/media",
        projects={"test": _project()},
        interaction_provider_cls=Interaction,
    )
    request = {
        "input_dir": str(tmp_path / "input"),
        "output_dir": str(tmp_path / "out"),
        "project": "test",
        "steps": ["ImportStep"],
        "caption_model_id": "model/id",
        "caption_vram_mode": "low",
        "caption_model_task": "caption",
    }

    with patch.dict(
            "prepare_lora_kit_ui.runner.STEP_INVOKE_MAP",
            {"ImportStep": MagicMock(side_effect=invoke)},
            clear=True,
    ):
        executor.execute(job, request)

    snapshot = job.snapshot()
    assert snapshot["status"] == "completed"
    assert snapshot["completed_steps"] == ["ImportStep"]
    assert snapshot["completed_substeps"] == {"ImportStep": ["import_images"]}
    assert snapshot["result"] == {
        "output_dir": str(tmp_path / "out"),
        "reports_dir": str(tmp_path / "out" / "reports"),
    }
    assert captured["caption_runtime"] == {
        "model_id": "model/id",
        "vram_mode": "low",
        "task": "caption",
    }
    assert captured["interaction"] is job.interaction_provider


def test_invalid_config_override_reprompts_with_error():
    project = _project()
    step = project.pipeline[1]
    manager = JobManager()
    job = PipelineJob(manager, "test-job")
    executor = UiPipelineExecutor()

    class Interaction:
        def __init__(self):
            self.errors: list[str | None] = []

        def step_config(self, _step_type, _config, error=None):
            self.errors.append(error)
            if error is None:
                return {"auto_only": True, "manual_all": True}
            return {"auto_only": True, "manual_all": False}

    interaction = Interaction()
    resolved = executor.resolve_step_config(job, interaction, step)

    assert resolved.auto_only is True
    assert resolved.manual_all is False
    assert interaction.errors[0] is None
    assert "mutually exclusive" in interaction.errors[1]
    assert any("config rejected" in line for line in job.snapshot()["logs"])
