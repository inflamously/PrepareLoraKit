"""Pipeline run-state manifest (JSON) for step tracking and resume."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import time


class RunState:
    """Tracks which steps completed and stores their output metadata."""

    def __init__(self, dataset_dir: Path):
        self._path = dataset_dir / ".plk_state.json"
        self._data: dict[str, Any] = self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self._path.exists():
            with open(self._path) as f:
                return json.load(f)
        return {"steps": {}}

    def save(self) -> None:
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2, default=str)

    # ── step API ──────────────────────────────────────────────────────────────

    def is_done(self, step: str) -> bool:
        return self._data["steps"].get(step, {}).get("status") == "done"

    def mark_done(self, step: str, meta: dict | None = None) -> None:
        self._data["steps"][step] = {
            "status": "done",
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            **(meta or {}),
        }
        self.save()

    def mark_skipped(self, step: str, reason: str = "") -> None:
        self._data["steps"][step] = {"status": "skipped", "reason": reason}
        self.save()

    def get(self, step: str) -> dict:
        return self._data["steps"].get(step, {})

    def reset(self, step: str | None = None) -> None:
        if step:
            self._data["steps"].pop(step, None)
        else:
            self._data["steps"] = {}
        self.save()
