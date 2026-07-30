"""Live progress for the model load that blocks the first caption preview.

``loader.load_pipeline`` is one opaque call. For a 9B FLUX.2 klein it can take
ten minutes — download, shard reads, 4-bit quantization, offload wiring — and it
returns nothing at all until it is finished. The review modal polls the job
every 800 ms, so unless something emits *during* that call the UI shows one
frozen line, which is indistinguishable from a hang.

Three signals, one context manager:

* a **heartbeat**, so the elapsed counter keeps moving even while the load has
  nothing to say. This is the part that makes "slow" readable as slow;
* a **tqdm tap**, because a tqdm bar is the only progress Hugging Face exposes;
* the **weights loaded so far**, when the caller passes a tracker to convert
  those bars into bytes (:mod:`.weights`). A bar says "3/6 shards of whichever
  component this is"; bytes say how much of the checkpoint is in.

The tap patches ``tqdm.std.tqdm`` rather than ``tqdm.auto.tqdm`` on purpose:
diffusers, transformers and huggingface_hub each did ``from tqdm.auto import
tqdm`` at import time, so their module-level names are already bound and
rebinding ``tqdm.auto.tqdm`` now would reach none of them. Every one of those
bindings is a *subclass* of ``tqdm.std.tqdm`` that inherits ``update`` and calls
``super().__init__``, so wrapping the base class's methods catches all of them.

All of it is best effort: a tqdm that cannot be patched costs the detail line,
never the load.
"""
from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any, Protocol

_UNITS = ("B", "KB", "MB", "GB", "TB")

# Held for the whole load, and acquired **non-blocking**: if something else is
# already tapping tqdm we skip the tap rather than restore another watcher's
# methods out of order (or park this thread for ten minutes).
_TAP_LOCK = threading.Lock()


@dataclass(frozen=True)
class LoadProgress:
    """What to say about a load in flight, if anything.

    ``weights`` is ``(loaded_bytes, total_bytes)`` and only ever set by the
    watcher — :func:`describe_bar` reads one bar, which cannot know what the
    rest of the checkpoint weighs.
    """

    detail: str | None = None
    fraction: float | None = None
    weights: tuple[int, int] | None = None


ProgressCallback = Callable[[LoadProgress], None]


class WeightTracker(Protocol):
    """The slice of :class:`weights.WeightProgress` the watcher drives."""

    def note(self, bar: Any) -> None: ...

    def snapshot(self) -> tuple[int, int] | None: ...


@contextmanager
def watch(
    callback: ProgressCallback,
    *,
    interval: float = 1.0,
    weights: WeightTracker | None = None,
) -> Iterator[None]:
    """Call ``callback`` every ``interval`` seconds while the block runs.

    The callback always receives the most recent progress seen, so a caller can
    stamp its own elapsed time onto every tick without the load cooperating.

    ``weights`` also receives every bar, and is sampled onto each tick. It is
    fed here rather than by the caller because the bars only exist inside the
    tap, and it is sampled on the tick rather than on the bar because a shard
    bar can fire hundreds of times a second on a thread pool.
    """
    watcher = _Watcher(callback, interval, weights)
    watcher.start()
    try:
        with _tqdm_tap(watcher.note):
            yield
    finally:
        watcher.stop()


class _Watcher:
    """Timer thread plus the last tqdm bar it was told about."""

    def __init__(
        self,
        callback: ProgressCallback,
        interval: float,
        weights: WeightTracker | None = None,
    ) -> None:
        self._callback = callback
        self._interval = max(0.1, float(interval))
        self._weights = weights
        self._lock = threading.Lock()
        self._progress = LoadProgress()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._pump, name="plk-t2i-load-progress", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2.0)

    def note(self, bar: Any) -> None:
        """Record a tqdm bar. Runs on whichever thread drives the bar."""
        if self._weights is not None:
            _safe(self._weights.note, bar)
        progress = describe_bar(bar)
        if progress is None:
            return
        with self._lock:
            self._progress = progress

    def _pump(self) -> None:
        # wait() returning False means "timed out", i.e. still loading.
        while not self._stop.wait(self._interval):
            with self._lock:
                progress = self._progress
            # Progress is best effort: a broken callback must not stop the pump.
            with contextlib.suppress(Exception):  # pragma: no cover
                self._callback(self._weigh(progress))

    def _weigh(self, progress: LoadProgress) -> LoadProgress:
        """Stamp the current weight total onto a tick, if there is one."""
        if self._weights is None:
            return progress
        try:
            sampled = self._weights.snapshot()
        except Exception:  # pragma: no cover - progress is best effort
            return progress
        return replace(progress, weights=sampled) if sampled else progress


@contextmanager
def _tqdm_tap(note: Callable[[Any], None]) -> Iterator[None]:
    """Report every tqdm bar created or advanced inside the block."""
    try:
        from tqdm.std import tqdm as tqdm_cls
    except Exception:  # pragma: no cover - tqdm ships with huggingface_hub
        yield
        return

    if not _TAP_LOCK.acquire(blocking=False):
        yield
        return

    original_init = tqdm_cls.__init__
    original_update = tqdm_cls.update

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _safe(note, self)

    def patched_update(self, n=1):
        result = original_update(self, n)
        _safe(note, self)
        return result

    tqdm_cls.__init__ = patched_init
    tqdm_cls.update = patched_update
    try:
        yield
    finally:
        tqdm_cls.__init__ = original_init
        tqdm_cls.update = original_update
        _TAP_LOCK.release()


def describe_bar(bar: Any) -> LoadProgress | None:
    """Turn a tqdm bar into one line of text plus a fraction.

    ``None`` when the bar says nothing usable — the caller then keeps whatever
    it was already showing rather than blanking a line that was informative.
    """
    total = _number(getattr(bar, "total", None))
    current = _number(getattr(bar, "n", None))
    description = str(getattr(bar, "desc", "") or "").strip().rstrip(":")
    unit = str(getattr(bar, "unit", "") or "")

    amount = _amount(current, total, unit)
    if not description and not amount:
        return None

    fraction = None
    if total and total > 0 and current is not None:
        fraction = min(1.0, max(0.0, current / total))

    detail = " · ".join(part for part in (description or None, amount) if part)
    return LoadProgress(detail=detail or None, fraction=fraction)


def _amount(current: float | None, total: float | None, unit: str) -> str | None:
    if current is None:
        return None
    if unit == "B":
        # Downloads are the long pole and the only bar whose absolute size means
        # anything to a person waiting on it.
        return f"{_bytes(current)} / {_bytes(total)}" if total else _bytes(current)
    if total:
        return f"{int(current)}/{int(total)}"
    return None


def _bytes(value: float | None) -> str:
    size = float(value or 0)
    for unit in _UNITS:
        if size < 1024 or unit == _UNITS[-1]:
            precision = 0 if unit in ("B", "KB") else 1
            return f"{size:.{precision}f} {unit}"
        size /= 1024
    return f"{size:.1f} {_UNITS[-1]}"  # pragma: no cover - loop always returns


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _safe(note: Callable[[Any], None], bar: Any) -> None:
    """A broken progress line must never take the load down with it."""
    with contextlib.suppress(Exception):  # pragma: no cover
        note(bar)


def format_elapsed(seconds: float | int | None) -> str:
    """``"48s"`` / ``"10m 12s"`` — the same shape the UI prints."""
    if seconds is None:
        return ""
    total = max(0, int(seconds))
    if total < 60:
        return f"{total}s"
    return f"{total // 60}m {total % 60:02d}s"
