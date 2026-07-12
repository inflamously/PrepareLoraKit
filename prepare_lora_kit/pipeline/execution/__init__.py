"""Shared pipeline execution API used by CLI and desktop UI."""

from prepare_lora_kit.pipeline.execution.engine import PipelineExecutor, execute_pipeline
from prepare_lora_kit.pipeline.execution.invalidation import resolve_force_invalidated_steps
from prepare_lora_kit.pipeline.execution.models import (
    ExecutionHooks,
    ExecutionResult,
    RunConfig,
)
from prepare_lora_kit.pipeline.execution.selection import (
    PipelineSelectionResolver,
    resolve_selected_steps,
    resolve_selected_substeps,
)

__all__ = [
    "ExecutionHooks",
    "ExecutionResult",
    "PipelineExecutor",
    "PipelineSelectionResolver",
    "RunConfig",
    "execute_pipeline",
    "resolve_selected_steps",
    "resolve_selected_substeps",
    "resolve_force_invalidated_steps",
]
