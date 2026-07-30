"""Payload serialization helpers for UI runner responses."""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any
from urllib.parse import quote

from prepare_lora_kit.pipeline import (
    is_optional_step_type,
    step_prerequisites,
)
from prepare_lora_kit.pipeline.execution.outcome import OUTCOME_SKIPPED, records_a_run
from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit.project.pipeline import substep_payloads
from prepare_lora_kit.report import REPORTS_DIR_NAME, step_report_path
from prepare_lora_kit.utils.state import RunState
from prepare_lora_kit_ui.paths import PROJECT_ROOT
from prepare_lora_kit_ui.runner.recommendations import upscale_attention


def _default_output(input_dir: Path) -> Path:
    return PROJECT_ROOT / "outputs" / input_dir.name


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


# Longest-side caps for the downscaled display variants served by the UI media endpoint.
# THUMB feeds grids / the caption thumbnail strip; VIEW feeds detail panes and the annotation
# canvas (which is viewport-bounded anyway). The full-resolution `uri` stays available as a
# fallback and for anything that genuinely needs the original.
THUMB_WIDTH = 384
VIEW_WIDTH = 2048


def _image_payload(path: Path, media_base_url: str | None = None) -> dict[str, str]:
    resolved = path.resolve()
    if media_base_url:
        base = f"{media_base_url}?path={quote(str(resolved), safe='')}"
        uri = base
        thumb_uri = f"{base}&w={THUMB_WIDTH}"
        view_uri = f"{base}&w={VIEW_WIDTH}"
    else:
        # No media server (e.g. file:// fixtures) — there is nothing to resize against, so all
        # three URLs point at the original.
        uri = thumb_uri = view_uri = resolved.as_uri()
    return {
        "path": str(resolved),
        "name": resolved.name,
        "uri": uri,
        "thumb_uri": thumb_uri,
        "view_uri": view_uri,
    }


_RUNNING_JOB_STATUSES = {"queued", "running", "waiting_input", "starting"}

# Step statuses that mean "this step has had its turn" — a plain re-run skips both.
_SATISFIED_STATUSES = {"done", "skipped"}


def project_status(
        project: ProjectConfig,
        output_dir: Path | None = None,
        live_status: str | None = None,
) -> str:
    """Derive a coarse library badge status for a project.

    Active and failed live job statuses win. A successful job may represent only
    a selected slice, so project completion is always derived from RunState: a
    project whose non-optional pipeline steps have all run is ``completed``,
    anything else is ``draft``.

    "Have all run" uses the same derivation as the step badges, so a step whose
    report has since been deleted drops the card back to ``draft`` — the run it
    claims can no longer be shown. A step that ran and reported no work still
    counts: the pipeline treats it as satisfied and will not re-run it.
    """
    if live_status:
        if live_status in _RUNNING_JOB_STATUSES:
            return "running"
        if live_status == "failed":
            return "failed"

    if output_dir is None:
        return "draft"

    state = RunState(output_dir)
    required = [
        step.type for step in project.pipeline if not is_optional_step_type(step.type)
    ]
    if required and all(
            _step_status(state, output_dir, step_type)[0] in _SATISFIED_STATUSES
            for step_type in required
    ):
        return "completed"
    return "draft"


def output_exists(output_dir: Path | None) -> bool:
    """True when the project's output folder has actually been materialized on disk.

    The resolved output path is known as soon as a project is selected, but the folder
    itself only appears once a run writes to it. The UI needs the distinction to decide
    whether opening it makes sense.
    """
    return output_dir is not None and output_dir.is_dir()


def _attention_scan_dir(project: ProjectConfig, output_dir: Path | None) -> Path | None:
    """Prefer the working dataset (reflects remaining need; it shrinks/converts as
    steps run) and fall back to the untouched input folder before any run."""
    if output_dir is not None:
        working = output_dir / "dataset"
        if working.is_dir() and any(working.iterdir()):
            return working
    return Path(project.input_dir) if project.input_dir else None


def _step_status(
        state: RunState | None, output_dir: Path | None, step_type: str,
) -> tuple[str, str]:
    """The badge status for one step, and why, from the persisted run-state.

    Two things the raw ``status`` field cannot say on its own:

    * A step whose own report said it did nothing is persisted as ``done`` —
      that is what prerequisites and resume read — with the real outcome stored
      beside it. Rendering that as "done" is what let the step list disagree
      with the ``reports/`` folder, so the outcome wins here.
    * A record is only as good as the report it points at. If that file has been
      deleted (or the whole output folder emptied) the record describes a run
      whose evidence is gone, and the honest badge is ``stale`` rather than a
      confident "done" nothing on disk backs up.
    """
    if state is None:
        return "pending", ""
    record = state.get(step_type)
    status = record.get("status", "pending")
    if status == "done" and records_a_run(record) and _report_missing(output_dir, step_type):
        return "stale", (
            f"{REPORTS_DIR_NAME}/{step_type}_report.json is missing — re-run this step"
        )
    if status == "done" and record.get("outcome") == OUTCOME_SKIPPED:
        return "skipped", str(record.get("outcome_reason") or "")
    return status, str(record.get("reason") or "")


def _report_missing(output_dir: Path | None, step_type: str) -> bool:
    return output_dir is not None and not step_report_path(output_dir, step_type).is_file()


def project_payload(project: ProjectConfig, output_dir: Path | None = None) -> dict[str, Any]:
    state = RunState(output_dir) if output_dir is not None else None
    scan_dir = _attention_scan_dir(project, output_dir)
    return {
        "name": project.name,
        "input_dir": project.input_dir,
        "steps": [
            _step_payload(step, state, output_dir, scan_dir) for step in project.pipeline
        ],
    }


def _step_payload(
        step,
        state: RunState | None,
        output_dir: Path | None,
        scan_dir: Path | None,
) -> dict[str, Any]:
    status, status_reason = _step_status(state, output_dir, step.type)
    return {
        "type": step.type,
        "config": _jsonable(step.config),
        "status": status,
        "status_reason": status_reason,
        "prerequisites": list(step_prerequisites(step.type)),
        "optional": is_optional_step_type(step.type),
        "substeps": substep_payloads(step.type, step.substeps, state),
        **_step_attention(step, scan_dir),
    }


def _step_attention(step, scan_dir: Path | None) -> dict[str, Any]:
    """Soft step-list recommendation. Only the UpscaleStep is data-driven today:
    it glows when the dataset has undersized images or JPEG artifacts."""
    if step.type != "UpscaleStep":
        return {}
    threshold = int(getattr(step.config, "upscale_highlight_threshold", 1536))
    attention = upscale_attention(scan_dir, threshold)
    return {
        "needs_attention": bool(attention and attention["recommended"]),
        "attention": attention,
    }
