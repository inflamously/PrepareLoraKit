"""Step-type and project resolution for the ``step`` command.

Maps a user-supplied step name/alias to a canonical step type and loads the
named project config, raising click errors with actionable hints on failure.
"""
from __future__ import annotations

import click

from prepare_lora_kit.project import project_registry
from ...project.base import STEP_TYPE_MAP
from ...project.steps import step_aliases

# Short aliases (sN / bare index) → canonical step type, preserving s1..s8.
_STEP_ALIASES = step_aliases()


def _resolve_step_type(raw: str) -> str:
    """Map a user-supplied step name/alias to a canonical step type."""
    low = raw.strip().lower()
    if low in _STEP_ALIASES:
        return _STEP_ALIASES[low]
    for t in STEP_TYPE_MAP:
        if t.lower() == low:
            return t
    raise click.BadParameter(
        f"Unknown step '{raw}'.\n"
        f"  Types:   {', '.join(STEP_TYPE_MAP)}\n"
        f"  Aliases: {', '.join(sorted(_STEP_ALIASES))}",
        param_hint="--step",
    )


def _load_project(name: str):
    try:
        return project_registry.load(name)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--project")
