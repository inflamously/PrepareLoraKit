"""Resolve persisted run-state invalidation for forced executions."""
from __future__ import annotations

from collections.abc import Iterable

from prepare_lora_kit.pipeline.configuration import step_definition
from prepare_lora_kit.project.base import ProjectConfig


def resolve_force_invalidated_steps(
        project: ProjectConfig,
        selected_steps: Iterable[str],
) -> list[str]:
    """Return selected and downstream steps in configured pipeline order.

    Shared pipeline runs only select configured steps, so invalidation begins at
    the earliest selected entry. The standalone step command may run a known
    step omitted from the project; in that case canonical step order supplies
    the insertion point.
    """

    selected = list(dict.fromkeys(selected_steps))
    selected_set = set(selected)
    configured = [step.type for step in project.pipeline]
    configured_positions = [
        index for index, step_type in enumerate(configured)
        if step_type in selected_set
    ]
    if configured_positions:
        return configured[min(configured_positions):]

    definitions = [step_definition(step_type) for step_type in selected]
    known_orders = [
        definition.order for definition in definitions if definition is not None
    ]
    if not known_orders:
        return []

    earliest_order = min(known_orders)
    downstream = [
        step_type for step_type in configured
        if (
            (definition := step_definition(step_type)) is not None
            and definition.order >= earliest_order
        )
    ]
    return list(dict.fromkeys([*selected, *downstream]))
