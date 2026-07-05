"""Shared working-dataset precondition check for invoke adapters."""
from __future__ import annotations
from pathlib import Path


def _require_working_dataset(working_dir: Path) -> None:
    if not working_dir.exists():
        raise FileNotFoundError(f"Working dataset does not exist at {working_dir}. Run ImportStep first.")
