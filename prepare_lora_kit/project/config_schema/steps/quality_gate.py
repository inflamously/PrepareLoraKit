"""Editable config fields for QualityGateStep."""
from __future__ import annotations

from ..fields import FieldSpec, _check

STEP_TYPE = "QualityGateStep"

FIELDS: list[FieldSpec] = [
    _check("manual_review", "Manual review"),
    _check("auto_only", "Auto only (skip manual review)"),
    _check("manual_all", "Review every image"),
]
