"""Pipeline execution hooks that project engine events onto a UI job."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from prepare_lora_kit.pipeline.execution import ExecutionHooks, ExecutionResult
from prepare_lora_kit.project.base import PipelineStep
from prepare_lora_kit.project.config_schema import apply_overrides, has_schema
from prepare_lora_kit_ui.runner.job import PipelineJob


class StepConfigResolver:
    """Prompt until frontend step overrides produce a valid configuration."""

    def __init__(self, job: PipelineJob, interaction: Any) -> None:
        self._job = job
        self._interaction = interaction

    def resolve(self, step: PipelineStep) -> Any:
        error: str | None = None
        while True:
            overrides = self._interaction.step_config(
                step.type, step.config, error=error
            )
            try:
                return apply_overrides(step.type, step.config, overrides)
            except ValueError as exc:
                error = str(exc)
                self._job.add_log(f"{step.type} config rejected: {exc}")


class UiJobHooks:
    """Handle shared execution lifecycle events for one desktop UI job."""

    def __init__(
            self,
            job: PipelineJob,
            interaction: Any,
            pause_for_config: bool,
    ) -> None:
        self._job = job
        self._interaction = interaction
        self._pause_for_config = pause_for_config
        self._config_resolver = StepConfigResolver(job, interaction)

    def to_execution_hooks(self) -> ExecutionHooks:
        return ExecutionHooks(
            step_start=self.step_start,
            step_skip=self.step_skip,
            resolve_config=self.resolve_config,
            post_step=self.post_step,
            step_complete=self.step_complete,
            complete=self.complete,
        )

    def step_start(self, step: PipelineStep, substeps: list[str]) -> None:
        self._job.set_status(
            "running",
            current_step=step.type,
            current_substep=substeps[0] if substeps else None,
        )

    def step_skip(
            self, step: PipelineStep, substeps: list[str], reason: str
    ) -> None:
        self._job.skipped_steps.append(step.type)
        self._job.skipped_substeps[step.type] = list(substeps)
        if reason == "legacy_import":
            self._job.add_log("ImportStep satisfied by existing working dataset")
        else:
            self._job.add_log(f"{step.type} already done; skipping")

    def resolve_config(self, step: PipelineStep) -> Any:
        if not self._pause_for_config or not has_schema(step.type):
            return step.config
        return self._config_resolver.resolve(step)

    def post_step(
            self, step: PipelineStep, result: Any, output_dir: Path
    ) -> None:
        if step.type == "AuditStep" and isinstance(result, dict) and not result.get("pass"):
            self._job.add_log(
                "AuditStep found issues; review reports/AuditStep_report.json"
            )
        if step.type == "CurateStep" and isinstance(result, dict):
            self._interaction.curate_details(
                result, output_dir / "reports" / "CurateStep_report.json"
            )

    def step_complete(self, step: PipelineStep, substeps: list[str]) -> None:
        self._job.completed_steps.append(step.type)
        self._job.completed_substeps[step.type] = list(substeps)

    def complete(self, result: ExecutionResult) -> None:
        self._job.result = {
            "output_dir": str(result.output_dir),
            "reports_dir": str(result.reports_dir),
        }
        self._job.set_status("completed", current_step=None, current_substep=None)
