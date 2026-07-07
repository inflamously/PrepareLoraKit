"""Report payload helpers for Step 5."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from prepare_lora_kit.report import reporter

if TYPE_CHECKING:
    from prepare_lora_kit.steps.caption_bbox.vlm import CaptionRuntime


def substep_status(enabled: set[str]) -> dict[str, dict[str, bool]]:
    return {
        "annotate_regions": {"enabled": "annotate_regions" in enabled},
        "caption_images": {"enabled": "caption_images" in enabled},
        "validate_captions": {"enabled": "validate_captions" in enabled},
    }


def build_success_report(
    *,
    images: list[Path],
    captions: dict[str, str],
    runtime: CaptionRuntime,
    skipped_annotation: list[str],
    missing_token: list[str],
    short_captions: list[str],
    long_captions: list[str],
    spot_check_sample: list[tuple[str, str]],
    enabled: set[str],
) -> dict[str, Any]:
    return {
        "total": len(images),
        "captioned": len(captions),
        "caption_model": runtime.metadata,
        "caption_status": runtime.status,
        "skipped_annotation": skipped_annotation,
        "missing_token": missing_token,
        "short_captions": short_captions,
        "long_captions": long_captions,
        "spot_check_sample": [p for p, _ in spot_check_sample] if captions else [],
        "substeps": substep_status(enabled),
    }


def save_success_report(report_data: dict[str, Any], report_path: Path | None, output_dir: Path) -> None:
    reporter.save_report(report_data, report_path or (output_dir / "step5_report.json"))


def _save_failure_report(
    report_path: Path,
    *,
    images: list[Path],
    captions: dict[str, str],
    skipped_annotation: list[str],
    runtime: CaptionRuntime,
    error: str,
    enabled: set[str],
) -> None:
    report_data = {
        "status": "failed",
        "total": len(images),
        "captioned": len(captions),
        "caption_model": runtime.metadata,
        "caption_status": runtime.status,
        "skipped_annotation": skipped_annotation,
        "error": error,
        "substeps": substep_status(enabled),
    }
    reporter.save_report(report_data, report_path)
