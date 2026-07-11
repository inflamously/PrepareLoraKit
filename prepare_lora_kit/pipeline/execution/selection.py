"""Resolve requested pipeline steps and substeps in project order."""
from __future__ import annotations

from prepare_lora_kit.project.base import PipelineStep, ProjectConfig
from prepare_lora_kit.project.pipeline import (
    SUBSTEP_REGISTRY,
    enabled_substep_ids,
    normalize_substeps,
)


class PipelineSelectionResolver:
    """Normalize requested steps and substeps against one project pipeline."""

    def __init__(self, project: ProjectConfig) -> None:
        self._project = project

    def resolve_steps(self, requested_steps: list[str] | None) -> list[str]:
        if requested_steps is None:
            return [step.type for step in self._project.pipeline]
        requested = set(requested_steps)
        ordered = [
            step.type for step in self._project.pipeline if step.type in requested
        ]
        # Retain unknown names so validation reports them instead of silently
        # reducing the selection to known project steps.
        ordered.extend(
            step_type for step_type in requested_steps if step_type not in ordered
        )
        return ordered

    def resolve_substeps(
            self,
            selected_steps: list[str],
            requested_substeps: dict[str, list[str]] | None = None,
    ) -> dict[str, list[str]]:
        requested_substeps = requested_substeps or {}
        selected = set(selected_steps)
        return {
            step.type: self._resolve_step_substeps(
                step, requested_substeps.get(step.type)
            )
            for step in self._project.pipeline
            if step.type in selected
        }

    @staticmethod
    def _resolve_step_substeps(
            step: PipelineStep, requested: list[str] | None
    ) -> list[str]:
        if requested is None:
            return enabled_substep_ids(step.type, step.substeps)
        definitions = SUBSTEP_REGISTRY.get(step.type, ())
        known = {definition.id for definition in definitions}
        unknown = [substep_id for substep_id in requested if substep_id not in known]
        if unknown:
            raise ValueError(
                f"Selected substep is not in {step.type}: {', '.join(unknown)}"
            )
        enabled = set(requested)
        substeps = normalize_substeps(
            step.type,
            [
                {"id": definition.id, "enabled": definition.id in enabled}
                for definition in definitions
            ],
            step.config,
        )
        return enabled_substep_ids(step.type, substeps)


def resolve_selected_steps(
        project: ProjectConfig,
        requested_steps: list[str] | None,
) -> list[str]:
    """Compatibility function returning selected steps in project order."""

    return PipelineSelectionResolver(project).resolve_steps(requested_steps)


def resolve_selected_substeps(
        project: ProjectConfig,
        selected_steps: list[str],
        requested_substeps: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Compatibility function returning canonical selected substeps."""

    return PipelineSelectionResolver(project).resolve_substeps(
        selected_steps, requested_substeps
    )
