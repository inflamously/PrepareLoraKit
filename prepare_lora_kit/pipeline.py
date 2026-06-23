"""
Pipeline orchestrator — runs pipeline steps in the order defined by ProjectConfig.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .cancellation import CancelCheck, check_cancel
from .invoke import STEP_INVOKE_MAP
from .paths import PROJECT_ROOT
from .project.base import ProjectConfig
from .project.steps import enabled_substep_ids, mark_legacy_import_satisfied
from .utils import report as rpt
from .utils.state import RunState


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
    from .networks import registry as net_registry
    network = net_registry.load(cfg.project.network)

    original_dir = cfg.dataset_dir
    output_dir = cfg.resolved_output_dir
    working_dir = output_dir / "dataset"
    force = cfg.force
    state = RunState(output_dir)

    def _skip(key: str) -> bool:
        if force:
            return False
        if key == "ImportStep" and mark_legacy_import_satisfied(state, output_dir):
            rpt.info("ImportStep satisfied by existing working dataset.")
            return True
        if state.is_done(key):
            rpt.info(f"{key} already done — skipping (use --force to re-run).")
            return True
        return False

    shared_kw = dict(
        network=network,
        concept_token=cfg.concept_token,
        original_dir=original_dir,
        network_type=cfg.project.network_type,
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
            rpt.warn("Integrity audit found issues — review reports/AuditStep_report.json before training.")
        for substep_id in enabled_substeps:
            state.mark_substep_done(step.type, substep_id)
        state.mark_done(step.type, {"enabled_substeps": enabled_substeps})

    rpt.ok("Pipeline complete. Review reports and run_config.yaml before training.")
