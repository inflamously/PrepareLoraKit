"""Invoke adapter for BucketPoolsCheckStep."""
from __future__ import annotations
from pathlib import Path

from prepare_lora_kit_pipeline.configs import BucketPoolsCheckConfig

from .working_dataset import _require_working_dataset


def _invoke_BucketPoolsCheckStep(working_dir: Path, output_dir: Path, cfg: BucketPoolsCheckConfig,
                             **_kw) -> None:
    _require_working_dataset(working_dir)
    from ..steps import bucket_pools_check
    bucket_pools_check.run(
        working_dir,
        resolution_buckets=cfg.resolution_buckets,
        display_name="configured bucket pools",
        output_dir=output_dir,
        cache_mode=cfg.cache_mode,
        thin_threshold=cfg.thin_threshold,
        report_path=output_dir / "reports" / "BucketPoolsCheckStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )
