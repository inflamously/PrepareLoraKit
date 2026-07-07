"""Step package — see step.py for implementation."""
from __future__ import annotations

from typing import Any

__all__ = ["run"]


def __getattr__(name: str) -> Any:
    if name == "run":
        from prepare_lora_kit.steps.vae_gate.step import run

        return run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
