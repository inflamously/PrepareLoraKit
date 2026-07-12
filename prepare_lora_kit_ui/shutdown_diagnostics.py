"""Persistent shutdown timing and thread diagnostics for the desktop app."""
from __future__ import annotations

import atexit
from datetime import datetime
import os
from pathlib import Path
import platform
import sys
import threading
from time import perf_counter
import traceback
from typing import Any


class ShutdownDiagnostics:
    """Write a shutdown timeline that survives the webview disappearing."""

    def __init__(
            self,
            path: Path,
            *,
            watchdog_interval: float = 5.0,
            register_atexit: bool = True,
    ) -> None:
        self.path = path
        self._started_at = perf_counter()
        self._shutdown_started_at: float | None = None
        self._watchdog_interval = watchdog_interval
        self._write_lock = threading.Lock()
        self._watchdog_stop = threading.Event()
        self._watchdog_started = False
        self._register_atexit = register_atexit
        self._early_atexit_registered = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        self.mark(
            "diagnostics started",
            pid=os.getpid(),
            python=sys.version.replace("\n", " "),
            platform=platform.platform(),
        )
        if register_atexit:
            # Registered before pipeline ML imports. Exit handlers registered by
            # those libraries later in the run execute before this late marker.
            atexit.register(self._at_exit_late)

    def mark(self, event: str, **details: Any) -> None:
        """Append one timestamped event to the diagnostic log."""
        elapsed = perf_counter() - self._started_at
        shutdown_elapsed = (
            perf_counter() - self._shutdown_started_at
            if self._shutdown_started_at is not None
            else None
        )
        detail_text = " ".join(
            f"{key}={value!r}" for key, value in sorted(details.items())
        )
        shutdown_text = (
            f" shutdown=+{shutdown_elapsed:.3f}s" if shutdown_elapsed is not None else ""
        )
        suffix = f" {detail_text}" if detail_text else ""
        self._append(
            f"[{datetime.now().astimezone().isoformat()} +{elapsed:.3f}s"
            f"{shutdown_text}] {event}{suffix}\n"
        )

    def begin_shutdown(self, event: str) -> None:
        """Start the shutdown clock and a periodic thread-dump watchdog once."""
        if self._shutdown_started_at is None:
            self._shutdown_started_at = perf_counter()
            self.mark(event)
            self.runtime_snapshot("shutdown start")
            self.dump_threads("shutdown start")
        if self._register_atexit and not self._early_atexit_registered:
            # Registered at close, so this runs before handlers registered while
            # the app was open and brackets their teardown with _at_exit_late.
            atexit.register(self._at_exit_early)
            self._early_atexit_registered = True
        if not self._watchdog_started and self._watchdog_interval > 0:
            self._watchdog_started = True
            threading.Thread(
                target=self._watchdog,
                name="plk-shutdown-watchdog",
                daemon=True,
            ).start()

    def runtime_snapshot(self, label: str) -> None:
        """Record Python threads, PyTorch CUDA state, memory, and child processes."""
        threads = threading.enumerate()
        details: dict[str, Any] = {
            "threads": len(threads),
            "non_daemon": [thread.name for thread in threads if not thread.daemon],
            "torch_loaded": "torch" in sys.modules,
        }

        torch = sys.modules.get("torch")
        cuda = getattr(torch, "cuda", None) if torch is not None else None
        if cuda is not None:
            try:
                details["cuda_initialized"] = bool(cuda.is_initialized())
            except Exception as exc:
                details["cuda_initialized_error"] = repr(exc)
            if details.get("cuda_initialized"):
                for name in ("memory_allocated", "memory_reserved"):
                    try:
                        details[f"cuda_{name}"] = int(getattr(cuda, name)())
                    except Exception as exc:
                        details[f"cuda_{name}_error"] = repr(exc)

        try:
            import psutil

            process = psutil.Process()
            details["rss"] = process.memory_info().rss
            details["native_threads"] = process.num_threads()
            details["children"] = [
                {"pid": child.pid, "name": child.name(), "status": child.status()}
                for child in process.children(recursive=True)
            ]
        except Exception as exc:
            details["process_snapshot_error"] = repr(exc)

        self.mark(f"runtime snapshot: {label}", **details)

    def dump_threads(self, label: str) -> None:
        """Append Python stacks for all currently visible threads."""
        frames = sys._current_frames()
        chunks = [f"--- thread dump: {label} ---\n"]
        for thread in threading.enumerate():
            chunks.append(
                f"thread name={thread.name!r} ident={thread.ident} "
                f"daemon={thread.daemon} alive={thread.is_alive()}\n"
            )
            frame = frames.get(thread.ident) if thread.ident is not None else None
            if frame is None:
                chunks.append("  <no Python frame>\n")
            else:
                chunks.extend(traceback.format_stack(frame))
        chunks.append("--- end thread dump ---\n")
        self._append("".join(chunks))

    def _watchdog(self) -> None:
        sequence = 0
        while not self._watchdog_stop.wait(self._watchdog_interval):
            sequence += 1
            self.runtime_snapshot(f"watchdog {sequence}")
            self.dump_threads(f"watchdog {sequence}")

    def _at_exit_early(self) -> None:
        try:
            self.mark("atexit phase entered")
            self.runtime_snapshot("atexit early")
            self.dump_threads("atexit early")
        except Exception:
            pass

    def _at_exit_late(self) -> None:
        self._watchdog_stop.set()
        try:
            self.mark("atexit late marker reached")
            self.runtime_snapshot("atexit late")
            self.dump_threads("atexit late")
        except Exception:
            pass

    def _append(self, text: str) -> None:
        acquired = False
        try:
            acquired = self._write_lock.acquire(timeout=0.5)
            if not acquired:
                return
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
        except Exception:
            # Diagnostics must never obstruct application shutdown.
            pass
        finally:
            if acquired:
                self._write_lock.release()
