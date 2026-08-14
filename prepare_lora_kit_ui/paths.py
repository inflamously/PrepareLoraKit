"""Single source of truth for filesystem locations.

Compute paths from these — never re-derive them with ``Path(__file__).parents[n]`` in
individual modules, which silently breaks when a file moves.
"""
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent   # .../prepare_lora_kit_ui
PROJECT_ROOT = PACKAGE_ROOT.parent               # repo root (holds outputs/)
