from unittest.mock import MagicMock, patch

import pytest

from prepare_lora_kit.pipeline.configs import ImportConfig
from prepare_lora_kit.pipeline.execution import RunConfig, execute_pipeline
from prepare_lora_kit.project.base import PipelineStep, ProjectConfig


def _config(tmp_path) -> RunConfig:
    return RunConfig(
        dataset_dir=tmp_path / "input",
        output_dir=tmp_path / "out",
        project=ProjectConfig(
            name="test",
            pipeline=[PipelineStep("ImportStep", ImportConfig())],
        ),
    )


def test_accelerator_memory_is_released_after_successful_step(tmp_path):
    with patch.dict(
            "prepare_lora_kit.pipeline.execution.engine.STEP_INVOKE_MAP",
            {"ImportStep": MagicMock()},
            clear=True,
    ), patch(
        "prepare_lora_kit.pipeline.execution.engine.release_accelerator_memory"
    ) as release:
        execute_pipeline(_config(tmp_path))

    release.assert_called_once_with()


def test_accelerator_memory_is_released_after_failed_step(tmp_path):
    with patch.dict(
            "prepare_lora_kit.pipeline.execution.engine.STEP_INVOKE_MAP",
            {"ImportStep": MagicMock(side_effect=RuntimeError("failed"))},
            clear=True,
    ), patch(
        "prepare_lora_kit.pipeline.execution.engine.release_accelerator_memory"
    ) as release, pytest.raises(RuntimeError, match="failed"):
        execute_pipeline(_config(tmp_path))

    release.assert_called_once_with()
