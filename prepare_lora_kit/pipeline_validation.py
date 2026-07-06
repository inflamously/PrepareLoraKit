"""Shared runtime validation for pipeline step selections."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit_pipeline.configuration import step_prerequisites

from .project.base import ProjectConfig
from .project.pipeline import (
    SUBSTEP_REGISTRY,
    enabled_substep_ids,
    is_step_satisfied,
)
from .utils.state import RunState


class PipelineValidationError(ValueError):
    """Raised when a requested pipeline selection cannot run safely."""


def validate_pipeline_selection(
        project: ProjectConfig,
        selected_steps: list[str],
        output_dir: Path,
        selected_substeps: dict[str, list[str]] | None = None,
) -> None:
    """Validate selected steps and substeps before invoking any pipeline work."""

    known = [step.type for step in project.pipeline]
    unknown = [step_type for step_type in selected_steps if step_type not in known]
    if unknown:
        raise PipelineValidationError(
            f"Selected step is not in project pipeline: {', '.join(unknown)}"
        )
    if not selected_steps:
        raise PipelineValidationError("Select at least one pipeline step")

    state = RunState(output_dir)
    selected = set(selected_steps)
    for step_type in selected_steps:
        enabled_substeps = _enabled_substeps(project, step_type, selected_substeps)
        if enabled_substeps == []:
            raise PipelineValidationError(f"{step_type} has no enabled substeps")
        _validate_substep_prerequisites(step_type, enabled_substeps)

        for req in step_prerequisites(step_type):
            if req not in selected and not is_step_satisfied(req, state, output_dir):
                raise PipelineValidationError(
                    f"{step_type} requires completed or selected prerequisite {req}"
                )

    needs_working_dataset = any(step_type != "ImportStep" for step_type in selected)
    if (
            needs_working_dataset
            and "ImportStep" not in selected
            and not (output_dir / "dataset").exists()
    ):
        raise PipelineValidationError(
            "The working dataset does not exist. Select ImportStep first or choose an existing output."
        )


def _enabled_substeps(
        project: ProjectConfig,
        step_type: str,
        selected_substeps: dict[str, list[str]] | None,
) -> list[str]:
    if selected_substeps is not None and step_type in selected_substeps:
        return selected_substeps[step_type]
    match = next((step for step in project.pipeline if step.type == step_type), None)
    if match is None:
        return []
    return enabled_substep_ids(step_type, match.substeps)


def _validate_substep_prerequisites(step_type: str, enabled_substeps: list[str]) -> None:
    enabled = set(enabled_substeps)
    for definition in SUBSTEP_REGISTRY.get(step_type, ()):
        if definition.id not in enabled:
            continue
        missing = [req for req in definition.prerequisites if req not in enabled]
        if missing:
            raise PipelineValidationError(
                f"{definition.id} requires enabled substep {', '.join(missing)}"
            )
