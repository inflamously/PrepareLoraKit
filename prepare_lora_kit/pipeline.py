"""
Pipeline orchestrator — runs pipeline steps in the order defined by ProjectConfig.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.invoke import STEP_INVOKE_MAP
from prepare_lora_kit.paths import PROJECT_ROOT
from prepare_lora_kit_pipeline.configuration import is_resume_aware_step_type
from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit.project.pipeline import (
    enabled_substep_ids,
    mark_legacy_import_satisfied,
)
from prepare_lora_kit.pipeline_validation import validate_pipeline_selection
from prepare_lora_kit.utils import report
from prepare_lora_kit.utils.state import RunState


@dataclass
class RunConfig:
    """All inputs to :func:`run_all`, bundled so call sites pass one object."""
    dataset_dir: Path
    project: ProjectConfig
    concept_token: Optional[str] = None
    output_dir: Optional[Path] = None
    force: bool = False
    cancel_check: CancelCheck | None = None

    @property
    def resolved_output_dir(self) -> Path:
        return self.output_dir or (PROJECT_ROOT / "outputs" / self.dataset_dir.name)


def run_all(cfg: RunConfig) -> None:
    """
    cfg.dataset_dir (original) stays untouched. ImportStep seeds a single
    working dir (output_dir/dataset) from it - the only image copy the pipeline
    makes. Subsequent steps mutate that working dir in place. Every step's JSON
    report lands in output_dir/reports/. Re-run from original any time with --force.
    """
    original_dir = cfg.dataset_dir
    output_dir = cfg.resolved_output_dir
    working_dir = output_dir / "dataset"
    force = cfg.force
    validate_pipeline_selection(
        cfg.project,
        [step.type for step in cfg.project.pipeline],
        output_dir,
    )
    state = RunState(output_dir)
    if force:
        # --force is a full reset: clear the manifest so every step re-runs,
        # including ImportStep, which re-seeds the working dataset from the
        # original (discarding any prior working dataset and its bbox sidecars).
        state.reset()

    def _skip(key: str) -> bool:
        if force:
            return False
        # Without --force, honor an existing working dataset that predates the
        # ImportStep so a plain re-run never rmtree's the dataset (and the
        # hand-drawn boxes in it) by re-importing.
        if key == "ImportStep" and mark_legacy_import_satisfied(state, output_dir):
            report.info("ImportStep satisfied by existing working dataset.")
            return True
        # Resume-aware steps self-determine pending work each run, so they are never
        # skipped on is_done — that is what lets CaptionBboxStep resume without --force.
        if is_resume_aware_step_type(key):
            return False
        if state.is_done(key):
            report.info(f"{key} already done — skipping (use --force to re-run).")
            return True
        return False

    shared_kw = dict(
        concept_token=cfg.concept_token,
        original_dir=original_dir,
        force=force,
    )

    for step in cfg.project.pipeline:
        check_cancel(cfg.cancel_check)
        if _skip(step.type):
            continue
        enabled_substeps = enabled_substep_ids(step.type, step.substeps)
        invoke = STEP_INVOKE_MAP[step.type]
        result = invoke(
            working_dir,
            output_dir,
            step.config,
            **shared_kw,
            enabled_substeps=enabled_substeps,
            cancel_check=cfg.cancel_check,
        )
        check_cancel(cfg.cancel_check)
        if step.type == "AuditStep" and isinstance(result, dict) and not result.get("pass"):
            report.warn("Integrity audit found issues — review reports/AuditStep_report.json before training.")
        for substep_id in enabled_substeps:
            state.mark_substep_done(step.type, substep_id)
        state.mark_done(step.type, {"enabled_substeps": enabled_substeps})

    report.ok("Pipeline complete. Review reports and export the dataset when ready.")
