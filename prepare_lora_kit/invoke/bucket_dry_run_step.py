"""Invoke adapter for BucketDryRunStep."""
from __future__ import annotations
from pathlib import Path

from prepare_lora_kit_pipeline.configs import BucketDryRunConfig

from .working_dataset import _require_working_dataset


def _invoke_BucketDryRunStep(working_dir: Path, output_dir: Path, cfg: BucketDryRunConfig,
                             *, network, **_kw) -> None:
    _require_working_dataset(working_dir)
    from ..steps import s8_bucket
    s8_bucket.run(
        working_dir,
        network=network,
        output_dir=output_dir,
        cache_mode=cfg.cache_mode,
        thin_threshold=cfg.thin_threshold,
        report_path=output_dir / "reports" / "BucketDryRunStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )
