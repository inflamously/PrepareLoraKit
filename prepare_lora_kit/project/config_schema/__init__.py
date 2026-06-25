"""Curated, UI-editable config field schemas for pipeline steps.

Each step type maps to an ordered list of :class:`FieldSpec` describing the
user-facing tunables to surface in the frontend config strip. The schema is
intentionally *curated* — legacy, deprecated, and internal fields on the
underlying config dataclasses (``project/configs/*.py``) are omitted.

The frontend renders one control per :class:`FieldSpec`; submitted overrides are
applied back onto the step's config via :func:`apply_overrides`, which coerces
values to their Python types and re-runs the dataclass ``__post_init__``
validation (raising ``ValueError`` on invalid input).

This package is sliced by responsibility:

* :mod:`.fields` — :class:`FieldSpec` and its builder helpers
* :mod:`.schema` — the curated ``CONFIG_FIELD_SCHEMA`` data
* :mod:`.query` — :func:`has_schema` / :func:`schema_payload`
* :mod:`.overrides` — :func:`apply_overrides`
"""
from __future__ import annotations

from .fields import FieldSpec
from .overrides import apply_overrides
from .query import has_schema, schema_payload
from .schema import CONFIG_FIELD_SCHEMA

__all__ = [
    "FieldSpec",
    "CONFIG_FIELD_SCHEMA",
    "has_schema",
    "schema_payload",
    "apply_overrides",
]
