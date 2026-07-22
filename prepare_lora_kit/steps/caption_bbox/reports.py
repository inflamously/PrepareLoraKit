"""Report payload helpers for CaptionBboxStep."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from prepare_lora_kit.project.pipeline.substeps import substep_ids_for
from prepare_lora_kit.report import reporter

_REPORT_NAME = "CaptionBboxStep_report.json"


def substep_status(enabled: set[str]) -> dict[str, dict[str, bool]]:
    return {
        substep_id: {"enabled": substep_id in enabled}
        for substep_id in substep_ids_for("CaptionBboxStep")
    }


def build_success_report(
    *,
    images: list[Path],
    captions: dict[str, str],
    caption_model: dict[str, Any],
    caption_status: dict[str, Any],
    skipped_annotation: list[str],
    missing_token: list[str],
    short_captions: list[str],
    long_captions: list[str],
    spot_check_sample: list[tuple[str, str]],
    enabled: set[str],
    mock_runtime: bool = False,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "total": len(images),
        "captioned": len(captions),
        "caption_model": caption_model,
        "caption_status": caption_status,
        "skipped_annotation": skipped_annotation,
        "missing_token": missing_token,
        "short_captions": short_captions,
        "long_captions": long_captions,
        "spot_check_sample": [p for p, _ in spot_check_sample] if captions else [],
        "substeps": substep_status(enabled),
    }
    if mock_runtime:
        report["mock_runtime"] = True
    return report


def save_success_report(report_data: dict[str, Any], report_path: Path | None, output_dir: Path) -> None:
    reporter.save_report(report_data, report_path or (output_dir / _REPORT_NAME))


def _save_failure_report(
    report_path: Path,
    *,
    images: list[Path],
    captions: dict[str, str],
    skipped_annotation: list[str],
    caption_model: dict[str, Any],
    caption_status: dict[str, Any],
    error: str,
    enabled: set[str],
) -> None:
    report_data = {
        "status": "failed",
        "total": len(images),
        "captioned": len(captions),
        "caption_model": caption_model,
        "caption_status": caption_status,
        "skipped_annotation": skipped_annotation,
        "error": error,
        "substeps": substep_status(enabled),
    }
    reporter.save_report(report_data, report_path)
