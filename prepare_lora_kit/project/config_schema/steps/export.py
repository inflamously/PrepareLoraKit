"""Editable config fields for ExportStep."""
from __future__ import annotations

from ..fields import FieldSpec, _text

STEP_TYPE = "ExportStep"

FIELDS: list[FieldSpec] = [
    _text(
        "target_dir",
        "Export folder",
        nullable=True,
        placeholder="<input>_export",
        help="Where finalized image + .txt pairs are written. "
             "Leave empty to use a sibling of the input folder named <input>_export.",
    ),
]
