"""
PrepareLoraKit CLI — `python main.py <command> [options]`

Commands:
  run   Full pipeline
  step  Run a single pipeline step manually (dynamic, by name/alias)
  projects   List available project configs
  ui         Launch desktop webview UI, optionally with --mock STEP
"""
from __future__ import annotations

# Import command modules for their side effect of registering on `cli`.
from . import projects, run, step, ui
from ._shared import cli

__all__ = ["cli"]
