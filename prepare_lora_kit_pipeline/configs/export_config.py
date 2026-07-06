"""Config schema for ExportStep."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExportConfig:
    """Config for ExportStep.

    ``target_dir`` is where the finalized image + ``.txt`` caption pairs are
    written. When ``None`` the step defaults to a sibling of the original input
    folder named ``<input>_export`` (see ``steps/export_step/step.py``), so the
    pristine source folder and the working dataset are never mutated.
    """
    target_dir: Optional[str] = None

    def __post_init__(self) -> None:
        if self.target_dir is not None:
            if not isinstance(self.target_dir, str) or not self.target_dir.strip():
                raise ValueError("ExportStep: target_dir must be a non-empty string or null")
