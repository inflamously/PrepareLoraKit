"""Thread-safe pipeline job state."""
from __future__ import annotations

import threading
import uuid
from typing import Any

from prepare_lora_kit.cancellation import CancelledRun

from prepare_lora_kit_ui.runner.constants import TERMINAL_STATUSES

class PipelineJob:
    """Mutable job state guarded by a condition variable."""

    def __init__(self, manager, job_id: str) -> None:
        self.manager = manager
        self.id = job_id
        self.status = "queued"
        self.current_step: str | None = None
        self.current_substep: str | None = None
        self.completed_steps: list[str] = []
        self.invalidated_steps: list[str] = []
        self.skipped_steps: list[str] = []
        self.completed_substeps: dict[str, list[str]] = {}
        self.skipped_substeps: dict[str, list[str]] = {}
        self.error: str | None = None
        self.result: dict[str, Any] | None = None
        self.logs: list[str] = []
        self.caption_status: dict[str, Any] | None = None
        self.pending_input: dict[str, Any] | None = None
        self._pending_answer: Any = None
        self._has_answer = False
        self.cancel_requested = False
        self._condition = threading.Condition()
        self._thread: threading.Thread | None = None

    def start(self, target, *args) -> None:
        self._thread = threading.Thread(
            target=target,
            args=args,
            name=f"plk-pipeline-{self.id[:8]}",
            daemon=True,
        )
        self._thread.start()

    def add_log(self, line: str) -> None:
        with self._condition:
            self.logs.append(line)
            if len(self.logs) > 1000:
                self.logs = self.logs[-1000:]
            self._condition.notify_all()

    def set_caption_status(self, status: dict[str, Any] | None) -> None:
        with self._condition:
            self.caption_status = dict(status) if status is not None else None
            self._condition.notify_all()

    def set_invalidated_steps(self, steps: list[str]) -> None:
        with self._condition:
            self.invalidated_steps = list(steps)
            self._condition.notify_all()

    def set_status(
            self,
            status: str,
            *,
            current_step: str | None = None,
            current_substep: str | None = None,
    ) -> None:
        with self._condition:
            self.status = status
            self.current_step = current_step
            self.current_substep = current_substep
            self._condition.notify_all()

    def request_input(self, kind: str, payload: dict[str, Any]) -> Any:
        request_id = uuid.uuid4().hex
        with self._condition:
            self.status = "waiting_input"
            self.pending_input = {
                "id": request_id,
                "kind": kind,
                "payload": payload,
            }
            self._pending_answer = None
            self._has_answer = False
            self._condition.notify_all()
            while not self._has_answer and not self.cancel_requested:
                self._condition.wait(timeout=0.25)
            if self.cancel_requested:
                self.pending_input = None
                self._pending_answer = None
                self._has_answer = False
                raise CancelledRun("Run cancelled")
            answer = self._pending_answer
            self.pending_input = None
            self._pending_answer = None
            self._has_answer = False
            self.status = "running"
            self._condition.notify_all()
            return answer

    def submit_input(self, request_id: str, value: Any) -> bool:
        with self._condition:
            if not self.pending_input or self.pending_input.get("id") != request_id:
                return False
            self._pending_answer = value
            self._has_answer = True
            self._condition.notify_all()
            return True

    def cancel(self) -> bool:
        with self._condition:
            if self.status in TERMINAL_STATUSES:
                return False
            self.cancel_requested = True
            self.status = "cancelling"
            self._condition.notify_all()
            return True

    def raise_if_cancelled(self) -> None:
        with self._condition:
            if self.cancel_requested:
                raise CancelledRun("Run cancelled")

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            return {
                "id": self.id,
                "status": self.status,
                "current_step": self.current_step,
                "current_substep": self.current_substep,
                "completed_steps": list(self.completed_steps),
                "invalidated_steps": list(self.invalidated_steps),
                "skipped_steps": list(self.skipped_steps),
                "completed_substeps": {
                    step: list(substeps)
                    for step, substeps in self.completed_substeps.items()
                },
                "skipped_substeps": {
                    step: list(substeps)
                    for step, substeps in self.skipped_substeps.items()
                },
                "error": self.error,
                "result": self.result,
                "logs": list(self.logs),
                "caption_status": dict(self.caption_status) if self.caption_status is not None else None,
                "pending_input": self.pending_input,
                "cancel_requested": self.cancel_requested,
            }
