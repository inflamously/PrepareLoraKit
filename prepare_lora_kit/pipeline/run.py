"""CLI compatibility wrapper around the shared pipeline execution engine."""
from __future__ import annotations

from prepare_lora_kit.pipeline.execution import (
    ExecutionHooks,
    RunConfig,
    describe_skip,
    execute_pipeline,
)
from prepare_lora_kit.project.base import PipelineStep
from prepare_lora_kit.report import reporter


class CliExecutionHooks:
    """Render shared pipeline lifecycle events for terminal users."""

    def to_execution_hooks(self) -> ExecutionHooks:
        return ExecutionHooks(
            step_skip=self.on_skip,
            post_step=self.post_step,
            complete=self.complete,
        )

    def on_skip(
            self, step: PipelineStep, _substeps: list[str], reason: str
    ) -> None:
        reporter.info(describe_skip(step.type, reason))

    def post_step(self, step: PipelineStep, result, _output_dir) -> None:
        if step.type == "AuditStep" and isinstance(result, dict) and not result.get("pass"):
            reporter.warn(
                "Integrity audit found issues — review "
                "reports/AuditStep_report.json before training."
            )

    def complete(self, _result) -> None:
        reporter.ok(
            "Pipeline complete. Review reports and export the dataset when ready."
        )


def run_all(cfg: RunConfig) -> None:
    """Run against a working copy while leaving the original dataset untouched."""

    execute_pipeline(cfg, CliExecutionHooks().to_execution_hooks())


__all__ = ["RunConfig", "run_all"]
