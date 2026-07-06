"""Step-type and project resolution for the ``step`` command.

Maps a user-supplied step name to a canonical step type and loads the
named project config, raising click errors with actionable hints on failure.
"""
from __future__ import annotations

import click

from prepare_lora_kit.project import project_registry
from prepare_lora_kit_pipeline.configuration import step_types
from ...project.steps import step_aliases

_STEP_ALIASES = step_aliases()


def _resolve_step_type(raw: str) -> str:
    """Map a user-supplied step name/alias to a canonical step type."""
    low = raw.strip().lower()
    if low in _STEP_ALIASES:
        return _STEP_ALIASES[low]
    for t in step_types():
        if t.lower() == low:
            return t
    raise click.BadParameter(
        f"Unknown step '{raw}'.\n"
        f"  Types:   {', '.join(step_types())}",
        param_hint="--step",
    )


def _load_project(name: str):
    try:
        return project_registry.load(name)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--project")
