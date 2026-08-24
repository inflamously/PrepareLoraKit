"""Invoke adapter for CurateStep."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.invoke.working_dataset import _require_working_dataset
from prepare_lora_kit.pipeline.configs import CurateConfig
from prepare_lora_kit.report import step_report_path
from prepare_lora_kit.steps.context import StepRunContext


def invoke_curate_step(working_dir: Path, output_dir: Path, cfg: CurateConfig,
                       **_kw) -> None:
    _require_working_dataset(working_dir)
    if _kw.get("mock_runtime"):
        from prepare_lora_kit.invoke.mock_curate import _mock_curate
        return _mock_curate(
                working_dir,
                output_dir,
                cfg,
                coverage_mode=str(_kw.get("mock_curate_coverage") or "auto"),
                enabled_substeps=_kw.get("enabled_substeps"),
                cancel_check=_kw.get("cancel_check"),
            )

    from prepare_lora_kit.steps import curate
    return curate.run(
        working_dir,
        cfg,
        context=StepRunContext(
            output_dir=working_dir,
            report_path=step_report_path(output_dir, "CurateStep"),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
        ),
    )
