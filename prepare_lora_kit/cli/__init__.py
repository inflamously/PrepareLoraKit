"""PrepareLoraKit CLI — ``python main.py <command> [options]``."""
from __future__ import annotations

# Import command modules for their side effect of registering on `cli`.
from . import projects, run, step, ui
from ._shared import cli

__all__ = ["cli"]
