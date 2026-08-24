"""Invoke adapter for VaeGateStep."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.invoke.working_dataset import _require_working_dataset
from prepare_lora_kit.pipeline.configs import VaeGateConfig
from prepare_lora_kit.report import step_report_path
from prepare_lora_kit.steps.context import StepRunContext


def invoke_vae_gate_step(working_dir: Path, output_dir: Path, cfg: VaeGateConfig,
                         **_kw) -> dict:
    _require_working_dataset(working_dir)
    if _kw.get("mock_runtime"):
        from prepare_lora_kit.invoke.mock_vae_gate import _mock_vae_gate
        return _mock_vae_gate(
            working_dir,
            output_dir,
            interaction=_kw.get("interaction"),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
        )

    from prepare_lora_kit.steps import vae_gate
    return vae_gate.run(
        working_dir,
        cfg,
        context=StepRunContext(
            output_dir=working_dir,
            report_path=step_report_path(output_dir, "VaeGateStep"),
            interaction=_kw.get("interaction"),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
        ),
    )
