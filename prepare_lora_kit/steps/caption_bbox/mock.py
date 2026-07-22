"""Deterministic mock implementation of CaptionBboxStep (``--mock``).

Shares the whole orchestration with the real step via :class:`CaptionStep`; it only
swaps the VLM for deterministic text and skips model load and caption validation, so
the ``--mock`` fixture can never drift from the real flow.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from prepare_lora_kit.steps.caption_bbox.base import CaptionStep
from prepare_lora_kit.steps.caption_bbox.workflow import CaptionWorkflowResult


class MockCaptionStep(CaptionStep):
    """Captions with deterministic placeholder text — no model, no VRAM."""

    HEADER = "Caption — Mock Runtime"
    mock_runtime = True

    def report_model_metadata(self) -> dict[str, Any]:
        return {"model_id": "mock"}

    def validate(
            self,
            captions: dict[str, str],
    ) -> tuple[list[str], list[str], list[str], list[tuple[str, str]]]:
        # The mock produces canned captions; there is nothing meaningful to QA.
        return [], [], [], []

    def _region_caption_fn(self, crop: Any, source_path: Path) -> str:
        return f"mock region caption for {source_path.stem}"

    def caption_full_image(
            self,
            path: Path,
            annotations: list,
            *,
            images: list[Path],
            result: CaptionWorkflowResult,
            output_dir: Path,
    ) -> str:
        return f"mock caption for {path.stem}"


def _mock_caption(
        working_dir: Path,
        output_dir: Path,
        *,
        concept_token: Optional[str],
        force: bool,
        enabled_substeps: list[str] | None = None,
        cancel_check=None,
        interaction=None,
) -> dict:
    """Backwards-compatible functional entry point for the mock runtime."""
    return MockCaptionStep(
        working_dir,
        concept_token=concept_token,
        output_dir=working_dir,
        overwrite=force,
        report_path=output_dir / "reports" / "CaptionBboxStep_report.json",
        interaction=interaction,
        enabled_substeps=enabled_substeps,
        cancel_check=cancel_check,
    ).run()
