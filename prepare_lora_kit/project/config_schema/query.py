"""Read-only queries over the config field schema for the frontend."""
from __future__ import annotations

import dataclasses
from typing import Any


from prepare_lora_kit.project.config_schema.schema import CONFIG_FIELD_SCHEMA

def has_schema(step_type: str) -> bool:
    """Return True when the step exposes editable tunables (i.e. should pause)."""

    return bool(CONFIG_FIELD_SCHEMA.get(step_type))


def schema_payload(step_type: str) -> list[dict[str, Any]]:
    """Return the JSON-able field schema for a step type."""

    return [dataclasses.asdict(spec) for spec in CONFIG_FIELD_SCHEMA.get(step_type, ())]
