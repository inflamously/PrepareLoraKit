"""Step-type and project resolution for the ``step`` command.

Maps a user-supplied step name to a canonical step type and loads the
named project config, raising click errors with actionable hints on failure.
"""
from __future__ import annotations

import click

from prepare_lora_kit.project import project_registry

from prepare_lora_kit.pipeline import step_slugs, step_type_for_slug, step_types


def _resolve_step_type(raw: str) -> str:
    """Map a user-supplied step name to a canonical step type.

    Accepts either the step type (``CaptionBboxStep``) or its slug
    (``caption_bbox``) — the slug being the name of the file the user most
    likely just edited.
    """
    low = raw.strip().lower()
    resolved = step_type_for_slug(low)
    if resolved is not None:
        return resolved
    for t in step_types():
        if t.lower() == low:
            return t
    raise click.BadParameter(
        f"Unknown step '{raw}'.\n"
        f"  Types:   {', '.join(step_types())}\n"
        f"  Or slug: {', '.join(step_slugs())}",
        param_hint="--step",
    )


def _load_project(name: str):
    try:
        return project_registry.load(name)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--project")
