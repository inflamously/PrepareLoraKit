"""Editable config fields for ConfigGenStep."""
from __future__ import annotations

from ..fields import FieldSpec, _text

STEP_TYPE = "ConfigGenStep"

FIELDS: list[FieldSpec] = [
    _text("base_template_path", "Base template path", nullable=True,
          placeholder="configs/templates/flux_base.yaml"),
]
