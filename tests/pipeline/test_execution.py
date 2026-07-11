from unittest.mock import MagicMock, patch

import pytest

from prepare_lora_kit.pipeline.configs import CurateConfig, ImportConfig, QualityGateConfig
from prepare_lora_kit.pipeline.execution import RunConfig, execute_pipeline
from prepare_lora_kit.project.base import PipelineStep, ProjectConfig
from prepare_lora_kit.utils.state import RunState


def _project() -> ProjectConfig:
    return ProjectConfig(
        name="test",
        pipeline=[
            PipelineStep("ImportStep", ImportConfig()),
            PipelineStep("QualityGateStep", QualityGateConfig(auto_only=True)),
            PipelineStep("CurateStep", CurateConfig()),
        ],
    )


def test_selected_execution_uses_project_order_and_collects_result(tmp_path):
    calls: list[str] = []
    invoke_map = {
        step_type: MagicMock(
            side_effect=lambda *_args, _step=step_type, **_kwargs: calls.append(_step)
        )
        for step_type in ("ImportStep", "QualityGateStep", "CurateStep")
    }
    cfg = RunConfig(
        dataset_dir=tmp_path / "input",
        output_dir=tmp_path / "out",
        project=_project(),
        selected_steps=["CurateStep", "ImportStep", "QualityGateStep"],
    )

    with patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", invoke_map, clear=True):
        result = execute_pipeline(cfg)

    assert calls == ["ImportStep", "QualityGateStep", "CurateStep"]
    assert result.completed_steps == calls
    assert result.skipped_steps == []
    assert result.output_dir == tmp_path / "out"
    assert result.reports_dir == tmp_path / "out" / "reports"


def test_requested_substeps_are_resolved_before_validation(tmp_path):
    cfg = RunConfig(
        dataset_dir=tmp_path / "input",
        output_dir=tmp_path / "out",
        project=_project(),
        selected_steps=["ImportStep", "QualityGateStep"],
        requested_substeps={"QualityGateStep": ["review_decisions"]},
    )

    with pytest.raises(ValueError, match="review_decisions requires enabled substep score_images"):
        execute_pipeline(cfg)


def test_unknown_requested_substep_is_rejected(tmp_path):
    cfg = RunConfig(
        dataset_dir=tmp_path / "input",
        output_dir=tmp_path / "out",
        project=_project(),
        selected_steps=["ImportStep"],
        requested_substeps={"ImportStep": ["not_a_substep"]},
    )

    with pytest.raises(ValueError, match="Selected substep is not in ImportStep"):
        execute_pipeline(cfg)


def test_failed_step_is_not_persisted_as_done(tmp_path):
    output_dir = tmp_path / "out"
    cfg = RunConfig(
        dataset_dir=tmp_path / "input",
        output_dir=output_dir,
        project=ProjectConfig(
            name="test",
            pipeline=[PipelineStep("ImportStep", ImportConfig())],
        ),
    )
    invoke = MagicMock(side_effect=RuntimeError("import failed"))

    with patch.dict(
            "prepare_lora_kit.pipeline.STEP_INVOKE_MAP",
            {"ImportStep": invoke},
            clear=True,
    ), pytest.raises(RuntimeError, match="import failed"):
        execute_pipeline(cfg)

    assert not RunState(output_dir).is_done("ImportStep")
