"""Pipeline run-state manifest (JSON) for step tracking and resume."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
import time


@dataclass
class StepState:
    """State of a single pipeline step."""

    status: str
    completed_at: str | None = None
    reason: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.completed_at is not None:
            d["completed_at"] = self.completed_at
        if self.reason is not None:
            d["reason"] = self.reason
        d.update(self.meta)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StepState:
        known = {"status", "completed_at", "reason"}
        return cls(
            status=d.get("status", ""),
            completed_at=d.get("completed_at"),
            reason=d.get("reason"),
            meta={k: v for k, v in d.items() if k not in known},
        )


@dataclass
class StateData:
    """Full run-state manifest."""

    steps: dict[str, StepState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"steps": {k: v.to_dict() for k, v in self.steps.items()}}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StateData:
        steps = {k: StepState.from_dict(v) for k, v in d.get("steps", {}).items()}
        return cls(steps=steps)


class RunState:
    """Tracks which steps completed and stores their output metadata."""

    def __init__(self, dataset_dir: Path):
        self._path = dataset_dir / ".plk_state.json"
        self._data: StateData = self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> StateData:
        if self._path.exists():
            with open(self._path) as f:
                return StateData.from_dict(json.load(f))
        return StateData()

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data.to_dict(), f, indent=2, default=str)

    # ── step API ──────────────────────────────────────────────────────────────

    def is_done(self, step: str) -> bool:
        s = self._data.steps.get(step)
        return s is not None and s.status == "done"

    def mark_done(self, step: str, meta: dict | None = None) -> None:
        self._data.steps[step] = StepState(
            status="done",
            completed_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            meta=meta or {},
        )
        self.save()

    def mark_skipped(self, step: str, reason: str = "") -> None:
        self._data.steps[step] = StepState(status="skipped", reason=reason)
        self.save()

    def get(self, step: str) -> dict:
        s = self._data.steps.get(step)
        return s.to_dict() if s is not None else {}

    def reset(self, step: str | None = None) -> None:
        if step:
            self._data.steps.pop(step, None)
        else:
            self._data.steps = {}
        self.save()
