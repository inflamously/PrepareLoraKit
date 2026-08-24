"""BucketPoolsCheckStep — simulate ai-toolkit's bucketing and flag thin buckets."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.cancellation import check_cancel
from prepare_lora_kit.pipeline.configs import BucketPoolsCheckConfig
from prepare_lora_kit.report import reporter, step_report_path
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
from prepare_lora_kit.steps.context import StepRunContext
from prepare_lora_kit.utils import image as img_utils

THIN_BUCKET_THRESHOLD = 2
DEFAULT_SUBSTEPS = ["assign_bucket_pools", "report_thin_buckets"]
__all__ = ["THIN_BUCKET_THRESHOLD", "run"]


def run(
    dataset_dir: Path,
    config: BucketPoolsCheckConfig,
    *,
    context: StepRunContext | None = None,
    display_name: str = "configured bucket pools",
) -> dict:
    context = context or StepRunContext()
    reporter.step_header("Bucket Dry-run")
    enabled = set(context.enabled_substeps or DEFAULT_SUBSTEPS)

    output_dir = context.output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    target_report = context.report_path or step_report_path(
        output_dir, "BucketPoolsCheckStep"
    )

    images = img_utils.iter_images(dataset_dir)
    if not images:
        reporter.warn(f"No images in {dataset_dir}")
        report_data = build_skipped_report(
            enabled, thin_threshold=config.thin_threshold, reason="no images"
        )
        reporter.save_report(report_data, target_report)
        return report_data

    if "assign_bucket_pools" not in enabled:
        report_data = build_skipped_report(
            enabled, thin_threshold=config.thin_threshold
        )
        reporter.save_report(report_data, target_report)
        return report_data

    bucket_map = assign_bucket_pools(
        images,
        config.resolution_buckets,
        cancel_check=context.cancel_check,
    )
    thin_buckets = (
        collect_thin_buckets(
            bucket_map,
            thin_threshold=config.thin_threshold,
            cancel_check=context.cancel_check,
        )
        if "report_thin_buckets" in enabled
        else []
    )
    print_bucket_table(
        bucket_map,
        display_name=display_name,
        thin_buckets=thin_buckets,
        cancel_check=context.cancel_check,
    )
    print_thin_bucket_summary(
        thin_buckets,
        thin_threshold=config.thin_threshold,
        cancel_check=context.cancel_check,
    )

    if config.cache_mode and "write_cache_info" in enabled:
        write_cache_info(
            output_dir,
            bucket_map,
            display_name=display_name,
            cancel_check=context.cancel_check,
        )

    report_data = build_success_report(
        bucket_map,
        thin_buckets=thin_buckets,
        thin_threshold=config.thin_threshold,
        cache_mode=config.cache_mode,
        enabled=enabled,
    )
    check_cancel(context.cancel_check)
    reporter.save_report(report_data, target_report)
    return report_data
