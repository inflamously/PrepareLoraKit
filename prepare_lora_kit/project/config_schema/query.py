"""Read-only queries over the config field schema for the frontend."""
from __future__ import annotations

import dataclasses
from typing import Any

from prepare_lora_kit.project.config_schema.schema import (
    CONFIG_FIELD_OPTIONS,
    CONFIG_FIELD_SCHEMA,
)


def has_schema(step_type: str) -> bool:
    """Return True when the step exposes editable tunables (i.e. should pause)."""

    return bool(CONFIG_FIELD_SCHEMA.get(step_type))


def schema_payload(step_type: str) -> list[dict[str, Any]]:
    """Return the JSON-able field schema for a step type.

    Fields with a registered option provider get their choices recomputed here so
    machine-dependent lists (e.g. which model checkpoints are downloaded) are
    current for this request.
    """

    providers = CONFIG_FIELD_OPTIONS.get(step_type, {})
    payload = []
    for spec in CONFIG_FIELD_SCHEMA.get(step_type, ()):
        field = dataclasses.asdict(spec)
        provider = providers.get(spec.name)
        if provider is not None:
            field["options"] = _provided_options(provider, field["options"])
        payload.append(field)
    return payload


def _provided_options(provider, fallback: list[dict[str, str]]) -> list[dict[str, str]]:
    """Fresh options from a provider, falling back to the declared ones.

    A provider touches the filesystem or hardware, so it is never allowed to take
    the config modal down with it.
    """

    try:
        return [{"value": value, "label": label} for value, label in provider()]
    except Exception:
        return fallback
