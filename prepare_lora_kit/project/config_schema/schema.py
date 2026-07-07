"""Curated, UI-editable config field schemas keyed by pipeline step type.

Each step type maps to an ordered list of :class:`FieldSpec` describing the
user-facing tunables to surface in the frontend config strip. The schema is
intentionally *curated* — legacy, deprecated, and internal fields on the
underlying config dataclasses (``project/configs/*.py``) are omitted.

The per-step field lists live in :mod:`.steps`; this module assembles them into
``CONFIG_FIELD_SCHEMA`` in pipeline order.
"""
from __future__ import annotations


from prepare_lora_kit.project.config_schema.fields import FieldSpec
from prepare_lora_kit.project.config_schema.steps import STEP_MODULES
CONFIG_FIELD_SCHEMA: dict[str, list[FieldSpec]] = {
    module.STEP_TYPE: module.FIELDS for module in STEP_MODULES
}
