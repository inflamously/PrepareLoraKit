"""Coerce and apply UI overrides back onto step config dataclasses.

Submitted overrides are coerced to their Python types and applied via
:func:`dataclasses.replace`, which re-runs the dataclass ``__post_init__``
validation (raising ``ValueError`` on invalid input).
"""
from __future__ import annotations

import dataclasses
from typing import Any

from .fields import FieldSpec
from .schema import CONFIG_FIELD_SCHEMA


def _coerce(spec: FieldSpec, raw: Any) -> tuple[bool, Any]:
    """Coerce a raw override to its field type. Returns (apply?, value)."""

    if spec.control == "checkbox":
        return True, bool(raw)

    is_blank = raw is None or (isinstance(raw, str) and raw.strip() == "")
    if is_blank:
        # Empty input: clear nullable fields, otherwise leave the default in place.
        return (True, None) if spec.nullable else (False, None)

    if spec.control == "number":
        try:
            return (True, int(raw)) if spec.value_type == "int" else (True, float(raw))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{spec.label}: expected a number, got {raw!r}") from exc

    return True, str(raw).strip()


def apply_overrides(step_type: str, config: Any, overrides: dict[str, Any] | None) -> Any:
    """Apply UI overrides onto a step config, validating via the dataclass.

    Unknown keys (not in the curated schema) are ignored. Coerced values are
    applied with :func:`dataclasses.replace`, which re-runs ``__post_init__`` so
    invalid combinations raise ``ValueError``.
    """

    if not overrides:
        return config

    specs = {spec.name: spec for spec in CONFIG_FIELD_SCHEMA.get(step_type, ())}
    changes: dict[str, Any] = {}
    for name, raw in overrides.items():
        spec = specs.get(name)
        if spec is None:
            continue
        apply, value = _coerce(spec, raw)
        if apply:
            changes[name] = value

    if not changes:
        return config
    return dataclasses.replace(config, **changes)
