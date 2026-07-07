"""Step 9 — Export finalized dataset to a training folder."""
from __future__ import annotations

from typing import Any

__all__ = ["run"]


def __getattr__(name: str) -> Any:
    if name == "run":
        from prepare_lora_kit.steps.export_step.step import run

        return run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
