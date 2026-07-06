"""Invoke adapter for ImportStep."""
from __future__ import annotations
import shutil
from pathlib import Path

from prepare_lora_kit.cancellation import check_cancel
from prepare_lora_kit_pipeline.configs import ImportConfig


def invoke_import_step(working_dir: Path, output_dir: Path, cfg: ImportConfig,
                       *, original_dir: Path, **_kw) -> dict:
    from import_step import run
    if working_dir.exists():
        shutil.rmtree(working_dir)
    check_cancel(_kw.get("cancel_check"))
    return run(
        original_dir,
        working_dir,
        report_path=output_dir / "reports" / "ImportStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )
