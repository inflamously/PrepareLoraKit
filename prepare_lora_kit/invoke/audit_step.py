"""Invoke adapter for AuditStep."""
from __future__ import annotations
from pathlib import Path

from prepare_lora_kit_pipeline.configs import AuditConfig

from .working_dataset import _require_working_dataset


def _invoke_AuditStep(working_dir: Path, output_dir: Path, cfg: AuditConfig,
                      **_kw) -> dict:
    _require_working_dataset(working_dir)
    from ..steps import audit
    return audit.run(
        working_dir,
        min_resolution_side=cfg.min_resolution_side,
        caption_model_type=cfg.caption_model_type,
        report_path=output_dir / "reports" / "AuditStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )
