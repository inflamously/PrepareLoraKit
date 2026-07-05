"""Invoke adapter for ExportStep."""
from __future__ import annotations
from pathlib import Path

from prepare_lora_kit_pipeline.configs import ExportConfig

from .working_dataset import _require_working_dataset


def _invoke_ExportStep(working_dir: Path, output_dir: Path, cfg: ExportConfig,
                       *, original_dir: Path | None = None, **_kw) -> dict:
    _require_working_dataset(working_dir)
    from ..steps import s9_export
    return s9_export.run(
        working_dir,
        original_dir=original_dir,
        target_dir=cfg.target_dir,
        output_dir=output_dir,
        interaction=_kw.get("interaction"),
        report_path=output_dir / "reports" / "ExportStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )
