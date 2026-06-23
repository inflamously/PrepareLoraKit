"""Cooperative cancellation helpers for long-running pipeline work."""
from __future__ import annotations

from typing import Protocol


class CancelledRun(RuntimeError):
    """Raised when a pipeline run is cancelled cooperatively."""


class CancelCheck(Protocol):
    """Callable that raises :class:`CancelledRun` when cancellation is requested."""

    def __call__(self) -> None:
        """Raise if the active run should stop."""


def noop_cancel_check() -> None:
    """Default cancellation check for non-UI callers."""


def check_cancel(cancel_check: CancelCheck | None) -> None:
    """Run an optional cancellation check."""

    if cancel_check is not None:
        cancel_check()
