"""Cooperative cancellation helpers for long-running pipeline work."""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Protocol, TypeVar

T = TypeVar("T")


class CancelledRun(RuntimeError):
    """Raised when a pipeline run is cancelled cooperatively."""


class CancelCheck(Protocol):
    """Callable that raises :class:`CancelledRun` when cancellation is requested."""

    def __call__(self) -> None:
        """Raise if the active run should stop."""


def noop_cancel_check() -> None:
    """Default cancellation check for non-UI callers."""


def cancellable(items: Iterable[T], cancel_check: CancelCheck) -> Iterator[T]:
    """Yield ``items``, running ``cancel_check`` before handing out each one."""

    for item in items:
        cancel_check()
        yield item
