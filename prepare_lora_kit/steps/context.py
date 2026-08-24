"""Runtime context shared by step entry points.

Project-owned settings live in the per-step config dataclasses under
``prepare_lora_kit.pipeline.configs``.  This context holds the transient values
that belong to one execution and must never be serialized into project YAML.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from prepare_lora_kit.cancellation import CancelCheck
from prepare_lora_kit.providers.interaction import InteractionProvider


@dataclass(frozen=True, slots=True)
class StepRunContext:
    """Paths and runtime services supplied by a pipeline invocation."""

    output_dir: Path | None = None
    report_path: Path | None = None
    interaction: InteractionProvider | None = None
    enabled_substeps: Sequence[str] | None = None
    cancel_check: CancelCheck | None = None
