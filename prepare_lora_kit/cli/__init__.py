"""
PrepareLoraKit CLI — `python main.py <command> [options]`

Commands:
  run   Full pipeline
  step  Run a single pipeline step manually (dynamic, by name/alias)
  projects   List available project configs
  ui         Launch desktop webview UI, optionally with --mock STEP
"""
from __future__ import annotations

from ._shared import cli

# Import command modules for their side effect of registering on `cli`.
from . import run, step, projects, ui  # noqa: F401,E402

__all__ = ["cli"]
