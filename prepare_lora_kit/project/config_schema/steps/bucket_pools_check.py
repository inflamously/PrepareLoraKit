"""Editable config fields for BucketPoolsCheckStep."""
from __future__ import annotations

from ..fields import FieldSpec, _check, _number

STEP_TYPE = "BucketPoolsCheckStep"

FIELDS: list[FieldSpec] = [
    _number("thin_threshold", "Thin bucket threshold", "int", minimum=0, step=1),
    _check("cache_mode", "Write cache_info.json"),
]
