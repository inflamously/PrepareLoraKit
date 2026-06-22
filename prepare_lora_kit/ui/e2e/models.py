"""Data models for UI end-to-end mock fixtures."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...project.base import ProjectConfig
from .constants import MOCK_TOKEN


@dataclass(frozen=True)
class MockUiFixture:
    root: Path
    input_dir: Path
    output_dir: Path
    project: ProjectConfig
    selected_steps: list[str]
    token: str = MOCK_TOKEN

    def bootstrap_payload(self) -> dict[str, Any]:
        return {
            "project": self.project.name,
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "selected_steps": list(self.selected_steps),
            "force": True,
            "token": self.token,
            "mock_runtime": True,
        }
