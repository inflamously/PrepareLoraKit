"""Shared pipeline execution API used by CLI and desktop UI."""

from prepare_lora_kit.pipeline.execution.engine import PipelineExecutor, execute_pipeline
from prepare_lora_kit.pipeline.execution.invalidation import resolve_force_invalidated_steps
from prepare_lora_kit.pipeline.execution.models import (
    ExecutionHooks,
    ExecutionResult,
    RunConfig,
)
from prepare_lora_kit.pipeline.execution.outcome import (
    SKIP_ALREADY_DONE,
    SKIP_LEGACY_IMPORT,
    StepOutcome,
    describe_skip,
    persist_step_outcome,
    records_a_run,
    step_outcome,
)
from prepare_lora_kit.pipeline.execution.selection import (
    PipelineSelectionResolver,
    resolve_selected_steps,
    resolve_selected_substeps,
)

__all__ = [
    "SKIP_ALREADY_DONE",
    "SKIP_LEGACY_IMPORT",
    "ExecutionHooks",
    "ExecutionResult",
    "PipelineExecutor",
    "PipelineSelectionResolver",
    "RunConfig",
    "StepOutcome",
    "describe_skip",
    "execute_pipeline",
    "persist_step_outcome",
    "records_a_run",
    "resolve_force_invalidated_steps",
    "resolve_selected_steps",
    "resolve_selected_substeps",
    "step_outcome",
]
