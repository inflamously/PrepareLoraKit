"""Shared ordered pipeline execution engine."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prepare_lora_kit.cancellation import check_cancel
from prepare_lora_kit.invoke import STEP_INVOKE_MAP
from prepare_lora_kit.pipeline.configuration import is_resume_aware_step_type
from prepare_lora_kit.pipeline.execution.models import (
    ExecutionHooks,
    ExecutionResult,
    RunConfig,
)
from prepare_lora_kit.pipeline.execution.selection import (
    resolve_selected_steps,
    resolve_selected_substeps,
)
from prepare_lora_kit.pipeline.validation import validate_pipeline_selection
from prepare_lora_kit.project.base import PipelineStep
from prepare_lora_kit.project.pipeline import mark_legacy_import_satisfied
from prepare_lora_kit.utils.state import RunState


@dataclass
class _ExecutionContext:
    output_dir: Path
    working_dir: Path
    selected_steps: set[str]
    selected_substeps: dict[str, list[str]]
    state: RunState
    result: ExecutionResult
    invoke_kwargs: dict[str, Any]


class StepSkipPolicy:
    """Decide whether persisted state satisfies a selected pipeline step."""

    def __init__(self, state: RunState, output_dir: Path, force: bool) -> None:
        self._state = state
        self._output_dir = output_dir
        self._force = force

    def reason(self, step_type: str) -> str | None:
        if self._force:
            return None
        if step_type == "ImportStep" and mark_legacy_import_satisfied(
                self._state, self._output_dir
        ):
            return "legacy_import"
        if is_resume_aware_step_type(step_type):
            return None
        if self._state.is_done(step_type):
            return "already_done"
        return None


class PipelineExecutor:
    """Validate and execute one configured project pipeline in project order."""

    def __init__(
            self,
            cfg: RunConfig,
            hooks: ExecutionHooks | None = None,
    ) -> None:
        self._cfg = cfg
        self._hooks = hooks or ExecutionHooks()

    def execute(self) -> ExecutionResult:
        context = self._prepare()
        skip_policy = StepSkipPolicy(
            context.state, context.output_dir, self._cfg.force
        )
        for step in self._cfg.project.pipeline:
            if step.type in context.selected_steps:
                self._execute_step(context, skip_policy, step)
        self._finish(context.result)
        return context.result

    def _prepare(self) -> _ExecutionContext:
        output_dir = self._cfg.resolved_output_dir
        selected_steps = resolve_selected_steps(
            self._cfg.project, self._cfg.selected_steps
        )
        selected_substeps = resolve_selected_substeps(
            self._cfg.project, selected_steps, self._cfg.requested_substeps
        )
        validate_pipeline_selection(
            self._cfg.project, selected_steps, output_dir, selected_substeps
        )
        state = RunState(output_dir)
        if self._cfg.force:
            state.reset()
        return _ExecutionContext(
            output_dir=output_dir,
            working_dir=output_dir / "dataset",
            selected_steps=set(selected_steps),
            selected_substeps=selected_substeps,
            state=state,
            result=ExecutionResult(output_dir, output_dir / "reports"),
            invoke_kwargs=self._invoke_kwargs(),
        )

    def _execute_step(
            self,
            context: _ExecutionContext,
            skip_policy: StepSkipPolicy,
            step: PipelineStep,
    ) -> None:
        check_cancel(self._cfg.cancel_check)
        substeps = context.selected_substeps[step.type]
        if self._hooks.step_start is not None:
            self._hooks.step_start(step, substeps)
        reason = skip_policy.reason(step.type)
        if reason is not None:
            self._record_skip(context.result, step, substeps, reason)
            return
        step_result = self._invoke_step(context, step, substeps)
        self._run_post_step(step, step_result, context.output_dir)
        self._record_completion(context, step, substeps)

    def _invoke_step(
            self,
            context: _ExecutionContext,
            step: PipelineStep,
            substeps: list[str],
    ) -> Any:
        config = (
            self._hooks.resolve_config(step)
            if self._hooks.resolve_config is not None
            else step.config
        )
        return STEP_INVOKE_MAP[step.type](
            context.working_dir,
            context.output_dir,
            config,
            **context.invoke_kwargs,
            enabled_substeps=substeps,
        )

    def _run_post_step(
            self, step: PipelineStep, result: Any, output_dir: Path
    ) -> None:
        # Cancellation/failure must be observed before persistence marks the
        # step complete.
        check_cancel(self._cfg.cancel_check)
        if self._hooks.post_step is not None:
            self._hooks.post_step(step, result, output_dir)
        check_cancel(self._cfg.cancel_check)

    def _record_skip(
            self,
            result: ExecutionResult,
            step: PipelineStep,
            substeps: list[str],
            reason: str,
    ) -> None:
        result.skipped_steps.append(step.type)
        result.skipped_substeps[step.type] = list(substeps)
        if self._hooks.step_skip is not None:
            self._hooks.step_skip(step, substeps, reason)
        check_cancel(self._cfg.cancel_check)

    def _record_completion(
            self,
            context: _ExecutionContext,
            step: PipelineStep,
            substeps: list[str],
    ) -> None:
        # Step invokers currently run their selected substeps as one transaction.
        # Publish their individual completion only after that invocation succeeds.
        completed_substeps = context.result.completed_substeps.setdefault(step.type, [])
        for substep_id in substeps:
            context.state.mark_substep_done(step.type, substep_id)
            completed_substeps.append(substep_id)
            if self._hooks.substep_complete is not None:
                self._hooks.substep_complete(step, substep_id)
        context.state.mark_done(step.type, {"enabled_substeps": substeps})
        context.result.completed_steps.append(step.type)
        if self._hooks.step_complete is not None:
            self._hooks.step_complete(step, substeps)

    def _invoke_kwargs(self) -> dict[str, Any]:
        return {
            "concept_token": self._cfg.concept_token,
            "original_dir": self._cfg.dataset_dir,
            "force": self._cfg.force,
            **self._cfg.invoke_kwargs,
            "cancel_check": self._cfg.cancel_check,
        }

    def _finish(self, result: ExecutionResult) -> None:
        check_cancel(self._cfg.cancel_check)
        if self._hooks.complete is not None:
            self._hooks.complete(result)


def execute_pipeline(
        cfg: RunConfig,
        hooks: ExecutionHooks | None = None,
) -> ExecutionResult:
    """Compatibility function for callers of the shared execution API."""

    return PipelineExecutor(cfg, hooks).execute()
