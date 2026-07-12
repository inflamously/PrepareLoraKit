"""Force-state behavior for the standalone ``plk step`` command."""
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from prepare_lora_kit.cli import cli
from prepare_lora_kit.pipeline.configs import CurateConfig, ImportConfig, QualityGateConfig
from prepare_lora_kit.project.base import PipelineStep, ProjectConfig
from prepare_lora_kit.utils.state import RunState


def test_step_force_preserves_earlier_state_and_invalidates_downstream(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (output_dir / "dataset").mkdir(parents=True)
    project = ProjectConfig(
        name="test",
        pipeline=[
            PipelineStep("ImportStep", ImportConfig()),
            PipelineStep("QualityGateStep", QualityGateConfig(auto_only=True)),
            PipelineStep("CurateStep", CurateConfig()),
        ],
    )
    state = RunState(output_dir)
    for step in project.pipeline:
        state.mark_done(step.type)
    invoke = MagicMock()

    with (
        patch(
            "prepare_lora_kit.cli.step.command._load_project",
            return_value=project,
        ),
        patch.dict(
            "prepare_lora_kit.cli.step.command.STEP_INVOKE_MAP",
            {"QualityGateStep": invoke},
            clear=True,
        ),
    ):
        result = CliRunner().invoke(
            cli,
            [
                "step",
                "--step", "QualityGateStep",
                "--project", "test",
                "--input", str(input_dir),
                "--output", str(output_dir),
                "--force",
            ],
        )

    persisted = RunState(output_dir)
    assert result.exit_code == 0, result.output
    invoke.assert_called_once()
    assert persisted.is_done("ImportStep")
    assert persisted.is_done("QualityGateStep")
    assert not persisted.is_done("CurateStep")
