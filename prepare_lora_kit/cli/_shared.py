"""Shared CLI group, helpers, and reusable options."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from ..paths import PROJECT_ROOT


@dataclass
class CliState:
    """Per-invocation context stored on ``ctx.obj``."""
    project: Any = None  # loaded ProjectConfig, or None; not yet applied to steps


def _default_output(input_dir: Path) -> Path:
    return PROJECT_ROOT / "outputs" / input_dir.name


# ── Shared options ────────────────────────────────────────────────────────────

cli_option_input = click.option("--input", "-i", "input_dir", required=True,
                                type=click.Path(exists=True, file_okay=False, path_type=Path),
                                help="Dataset directory")
cli_option_output = click.option("--output", "-o", "output_dir",
                                 type=click.Path(file_okay=False, path_type=Path),
                                 default=None, help="Output directory (default: <project>/outputs/<input-name>)")
cli_option_token = click.option("--token", "-t", default=None,
                                help="Concept token / trigger word. Omit for style training.")


@click.group()
@click.pass_context
def cli(ctx):
    """PrepareLoraKit — LoRA dataset preparation pipeline."""
    ctx.ensure_object(CliState)
