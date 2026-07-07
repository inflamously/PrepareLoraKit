"""Public pipeline orchestration API."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prepare_lora_kit.pipeline.configuration import StepDefinition
    from prepare_lora_kit.pipeline.run import RunConfig
    from prepare_lora_kit.pipeline.validation import PipelineValidationError


def __getattr__(name: str) -> Any:
    if name in {
        "STEP_DEFINITIONS",
        "StepDefinition",
        "is_optional_step_type",
        "is_resume_aware_step_type",
        "step_config_class",
        "step_definition",
        "step_prerequisites",
        "step_types",
    }:
        from prepare_lora_kit.pipeline import configuration

        return getattr(configuration, name)
    if name in {"RunConfig", "run_all"}:
        from prepare_lora_kit.pipeline.run import RunConfig, run_all

        return {"RunConfig": RunConfig, "run_all": run_all}[name]
    if name in {"PipelineValidationError", "validate_pipeline_selection"}:
        from prepare_lora_kit.pipeline.validation import (
            PipelineValidationError,
            validate_pipeline_selection,
        )

        return {
            "PipelineValidationError": PipelineValidationError,
            "validate_pipeline_selection": validate_pipeline_selection,
        }[name]
    if name == "STEP_INVOKE_MAP":
        from prepare_lora_kit.invoke import STEP_INVOKE_MAP

        return STEP_INVOKE_MAP
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "RunConfig",
    "STEP_DEFINITIONS",
    "STEP_INVOKE_MAP",
    "PipelineValidationError",
    "StepDefinition",
    "is_optional_step_type",
    "is_resume_aware_step_type",
    "run_all",
    "step_config_class",
    "step_definition",
    "step_prerequisites",
    "step_types",
    "validate_pipeline_selection",
]
