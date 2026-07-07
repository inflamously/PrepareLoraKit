"""UI end-to-end mock fixture helpers."""
from __future__ import annotations

from typing import Any

from prepare_lora_kit_ui.e2e.constants import MOCK_PROJECT_NAME, MOCK_TOKEN


def __getattr__(name: str) -> Any:
    if name == "create_mock_ui_fixture":
        from prepare_lora_kit_ui.e2e.fixture import create_mock_ui_fixture

        return create_mock_ui_fixture
    if name == "MockUiFixture":
        from prepare_lora_kit_ui.e2e.models import MockUiFixture

        return MockUiFixture
    if name == "resolve_mock_steps":
        from prepare_lora_kit_ui.e2e.steps import resolve_mock_steps

        return resolve_mock_steps
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MOCK_PROJECT_NAME",
    "MOCK_TOKEN",
    "MockUiFixture",
    "create_mock_ui_fixture",
    "resolve_mock_steps",
]
