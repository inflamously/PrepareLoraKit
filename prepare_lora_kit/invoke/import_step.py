"""Invoke adapter for ImportStep."""
from __future__ import annotations

import shutil
from pathlib import Path

from prepare_lora_kit.cancellation import check_cancel
from prepare_lora_kit.pipeline.configs import ImportConfig
from prepare_lora_kit.report import step_report_path


def invoke_import_step(working_dir: Path, output_dir: Path, cfg: ImportConfig,
                       *, original_dir: Path, **_kw) -> dict:
    from prepare_lora_kit.steps import import_step
    if working_dir.exists():
        shutil.rmtree(working_dir)
    check_cancel(_kw.get("cancel_check"))
    return import_step.run(
        original_dir,
        working_dir,
        report_path=step_report_path(output_dir, "ImportStep"),
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )
