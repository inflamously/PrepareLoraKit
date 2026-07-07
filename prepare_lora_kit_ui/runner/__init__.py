"""Background runner package for the webview app."""
from __future__ import annotations

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "STEP_INVOKE_MAP":
        from prepare_lora_kit.invoke import STEP_INVOKE_MAP

        return STEP_INVOKE_MAP
    if name == "TERMINAL_STATUSES":
        from prepare_lora_kit_ui.runner.constants import TERMINAL_STATUSES

        return TERMINAL_STATUSES
    if name == "UiInteractionProvider":
        from prepare_lora_kit_ui.runner.interactions import UiInteractionProvider

        return UiInteractionProvider
    if name == "PipelineJob":
        from prepare_lora_kit_ui.runner.job import PipelineJob

        return PipelineJob
    if name == "_LogStream":
        from prepare_lora_kit_ui.runner.logging import _LogStream

        return _LogStream
    if name == "JobManager":
        from prepare_lora_kit_ui.runner.manager import JobManager

        return JobManager
    if name in {"_default_output", "_image_payload", "_jsonable", "project_payload", "project_status"}:
        from prepare_lora_kit_ui.runner import payloads

        return getattr(payloads, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "JobManager",
    "PipelineJob",
    "UiInteractionProvider",
    "STEP_INVOKE_MAP",
    "TERMINAL_STATUSES",
    "_LogStream",
    "_default_output",
    "_image_payload",
    "_jsonable",
    "project_payload",
    "project_status",
]
