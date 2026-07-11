"""Typed parsing of frontend pipeline run requests."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from prepare_lora_kit.pipeline.execution import RunConfig
from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit_ui.paths import PROJECT_ROOT

if TYPE_CHECKING:
    from prepare_lora_kit_ui.runner.job import PipelineJob


@dataclass(frozen=True)
class UiRunRequest:
    """Normalized values accepted from the pywebview run payload."""

    input_dir: Path
    output_dir: Path
    project_name: str
    token: str | None
    force: bool
    pause_for_config: bool
    selected_steps: list[str]
    requested_substeps: dict[str, list[str]]
    caption_runtime: dict[str, str | None]
    mock_runtime: bool
    mock_curate_coverage: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "UiRunRequest":
        input_dir = Path(str(payload["input_dir"])).expanduser()
        output_dir = cls._output_dir(payload.get("output_dir"), input_dir)
        return cls(
            input_dir=input_dir,
            output_dir=output_dir,
            project_name=str(payload["project"]),
            token=payload.get("token") or None,
            force=bool(payload.get("force", False)),
            pause_for_config=bool(payload.get("pause_for_config", False)),
            selected_steps=[str(step) for step in payload.get("steps", [])],
            requested_substeps=cls._substeps(payload.get("substeps")),
            caption_runtime={
                "model_id": payload.get("caption_model_id") or None,
                "vram_mode": payload.get("caption_vram_mode") or None,
                "task": payload.get("caption_model_task") or None,
            },
            mock_runtime=bool(payload.get("mock_runtime", False)),
            mock_curate_coverage=str(payload.get("mock_curate_coverage") or "auto"),
        )

    def to_run_config(
            self,
            project: ProjectConfig,
            interaction: Any,
            job: "PipelineJob",
    ) -> RunConfig:
        return RunConfig(
            dataset_dir=self.input_dir,
            project=project,
            concept_token=self.token,
            output_dir=self.output_dir,
            force=self.force,
            cancel_check=job.raise_if_cancelled,
            selected_steps=self.selected_steps,
            requested_substeps=self.requested_substeps,
            invoke_kwargs={
                "interaction": interaction,
                "caption_runtime": self.caption_runtime,
                "caption_status_callback": job.set_caption_status,
                "mock_runtime": self.mock_runtime,
                "mock_curate_coverage": self.mock_curate_coverage,
            },
        )

    @staticmethod
    def _output_dir(value: Any, input_dir: Path) -> Path:
        if value:
            return Path(str(value)).expanduser()
        return PROJECT_ROOT / "outputs" / input_dir.name

    @staticmethod
    def _substeps(value: Any) -> dict[str, list[str]]:
        return {
            str(step_type): [str(substep_id) for substep_id in substeps]
            for step_type, substeps in (value or {}).items()
            if isinstance(substeps, list)
        }
