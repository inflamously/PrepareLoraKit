"""Invoke adapter for QualityGateStep."""
from __future__ import annotations
import dataclasses
from pathlib import Path

from prepare_lora_kit_pipeline.configs import QualityGateConfig

from .working_dataset import _require_working_dataset


def invoke_quality_gate_step(working_dir: Path, output_dir: Path, cfg: QualityGateConfig,
                             *, original_dir: Path, **_kw) -> None:
    from ..steps import quality_gate
    _require_working_dataset(working_dir)
    quality_gate.run(
        working_dir,
        working_dir,
        auto_only=cfg.auto_only,
        manual_all=cfg.manual_all,
        scorers=[dataclasses.asdict(s) for s in cfg.scorers],
        report_path=output_dir / "reports" / "QualityGateStep_report.json",
        interaction=_kw.get("interaction"),
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )
