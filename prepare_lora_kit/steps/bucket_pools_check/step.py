"""
Step 8 — Bucket Dry-run

Simulates ai-toolkit's multi-resolution bucketing without actually training.
Assigns each image to its closest bucket by aspect-ratio distance, then flags
thin buckets (≤ 2 images) and suggests fixes (crop or repeats).

Optional --cache-mode: writes a cache_info.json compatible with ai-toolkit's
cache_latents_to_disk path structure for re-use on the real run.
"""
from __future__ import annotations
from pathlib import Path

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.utils import image as img_utils
from prepare_lora_kit.report import reporter
from prepare_lora_kit.steps.bucket_pools_check.assignment import assign_bucket_pools
from prepare_lora_kit.steps.bucket_pools_check.cache import write_cache_info
from prepare_lora_kit.steps.bucket_pools_check.presentation import (
    print_bucket_table,
    print_thin_bucket_summary,
)
from prepare_lora_kit.steps.bucket_pools_check.reports import (
    build_skipped_report,
    build_success_report,
)
from prepare_lora_kit.steps.bucket_pools_check.thin_buckets import collect_thin_buckets


THIN_BUCKET_THRESHOLD = 2
DEFAULT_SUBSTEPS = ["assign_bucket_pools", "report_thin_buckets"]
__all__ = ["run", "THIN_BUCKET_THRESHOLD"]


def run(
    dataset_dir: Path,
    resolution_buckets: list[tuple[int, int]],
    display_name: str = "configured bucket pools",
    output_dir: Path | None = None,
    cache_mode: bool = False,
    thin_threshold: int = THIN_BUCKET_THRESHOLD,
    report_path: Path | None = None,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    reporter.step_header("Bucket Dry-run")
    enabled = set(enabled_substeps or DEFAULT_SUBSTEPS)

    output_dir = output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    images = img_utils.iter_images(dataset_dir)
    if not images:
        reporter.warn(f"No images in {dataset_dir}")
        return {}

    if "assign_bucket_pools" not in enabled:
        report_data = build_skipped_report(enabled, thin_threshold=thin_threshold)
        reporter.save_report(report_data, report_path or (output_dir / "step8_report.json"))
        return report_data

    bucket_map = assign_bucket_pools(images, resolution_buckets, cancel_check=cancel_check)
    thin_buckets = (
        collect_thin_buckets(bucket_map, thin_threshold=thin_threshold, cancel_check=cancel_check)
        if "report_thin_buckets" in enabled
        else []
    )
    print_bucket_table(
        bucket_map,
        display_name=display_name,
        thin_buckets=thin_buckets,
        cancel_check=cancel_check,
    )
    print_thin_bucket_summary(thin_buckets, thin_threshold=thin_threshold, cancel_check=cancel_check)

    if cache_mode and "write_cache_info" in enabled:
        write_cache_info(output_dir, bucket_map, display_name=display_name, cancel_check=cancel_check)

    report_data = build_success_report(
        bucket_map,
        thin_buckets=thin_buckets,
        thin_threshold=thin_threshold,
        cache_mode=cache_mode,
        enabled=enabled,
    )
    check_cancel(cancel_check)
    reporter.save_report(report_data, report_path or (output_dir / "step8_report.json"))
    return report_data
