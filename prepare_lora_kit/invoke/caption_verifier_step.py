"""Invoke adapter for CaptionVerifierStep."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.invoke.working_dataset import _require_working_dataset
from prepare_lora_kit.pipeline.configs import CaptionVerifierConfig
from prepare_lora_kit.report import step_report_path
from prepare_lora_kit.steps.context import StepRunContext


def invoke_caption_verifier_step(working_dir: Path, output_dir: Path,
                                 cfg: CaptionVerifierConfig, **_kw) -> dict:
    _require_working_dataset(working_dir)
    if _kw.get("mock_runtime"):
        from prepare_lora_kit.invoke.mock_caption_verifier import _mock_caption_verifier
        return _mock_caption_verifier(
            working_dir,
            output_dir,
            interaction=_kw.get("interaction"),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
        )

    from prepare_lora_kit.steps import caption_verifier
    return caption_verifier.run(
        working_dir,
        cfg,
        context=StepRunContext(
            output_dir=working_dir,
            report_path=step_report_path(output_dir, "CaptionVerifierStep"),
            interaction=_kw.get("interaction"),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
        ),
        status_callback=_kw.get("caption_status_callback"),
    )
