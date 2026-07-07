"""Bucket pool dry-run step package."""
from __future__ import annotations

from typing import Any

__all__ = ["run"]


def __getattr__(name: str) -> Any:
    if name == "run":
        from prepare_lora_kit.steps.bucket_pools_check.step import run

        return run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
