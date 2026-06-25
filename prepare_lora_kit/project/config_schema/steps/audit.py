"""Editable config fields for AuditStep."""
from __future__ import annotations

from ..fields import FieldSpec, _check, _number

STEP_TYPE = "AuditStep"

FIELDS: list[FieldSpec] = [
    _number("min_caption", "Min caption length", "int", minimum=0, step=1),
    _number("max_caption", "Max caption length", "int", minimum=1, step=10),
    _check("check_pairing", "Check pairing"),
    _check("check_corrupt", "Check corrupt files"),
    _check("check_caption_length", "Check caption length"),
    _check("check_resolution_gate", "Check resolution gate"),
]
