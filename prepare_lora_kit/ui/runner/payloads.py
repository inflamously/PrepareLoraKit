"""Payload serialization helpers for UI runner responses."""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ...paths import PROJECT_ROOT
from ...project.base import ProjectConfig
from ...project.steps import OPTIONAL_STEP_TYPES, STEP_PREREQUISITES, substep_payloads
from ...utils.state import RunState
from .recommendations import upscale_attention


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


def _image_payload(path: Path, media_base_url: str | None = None) -> dict[str, str]:
    resolved = path.resolve()
    uri = (
        f"{media_base_url}?path={quote(str(resolved), safe='')}"
        if media_base_url
        else resolved.as_uri()
    )
    return {
        "path": str(resolved),
        "name": resolved.name,
        "uri": uri,
    }


_RUNNING_JOB_STATUSES = {"queued", "running", "waiting_input", "starting"}


def project_status(
    project: ProjectConfig,
    output_dir: Path | None = None,
    live_status: str | None = None,
) -> str:
    """Derive a coarse library badge status for a project.

    Live job status (when supplied) wins; otherwise the persisted RunState is
    inspected: a project whose non-optional pipeline steps are all ``done`` is
    ``completed``, anything else is ``draft``. Persisted state has no failure
    marker, so ``failed`` is only reported from a live/terminal job this session.
    """
    if live_status:
        if live_status in _RUNNING_JOB_STATUSES:
            return "running"
        if live_status == "failed":
            return "failed"
        if live_status == "completed":
            return "completed"

    if output_dir is None:
        return "draft"

    state = RunState(output_dir)
    required = [
        step.type for step in project.pipeline if step.type not in OPTIONAL_STEP_TYPES
    ]
    if required and all(
        state.get(step_type).get("status") == "done" for step_type in required
    ):
        return "completed"
    return "draft"


def _attention_scan_dir(project: ProjectConfig, output_dir: Path | None) -> Path | None:
    """Prefer the working dataset (reflects remaining need; it shrinks/converts as
    steps run) and fall back to the untouched input folder before any run."""
    if output_dir is not None:
        working = output_dir / "dataset"
        if working.is_dir() and any(working.iterdir()):
            return working
    return Path(project.input_dir) if project.input_dir else None


def project_payload(project: ProjectConfig, output_dir: Path | None = None) -> dict[str, Any]:
    state = RunState(output_dir) if output_dir is not None else None
    scan_dir = _attention_scan_dir(project, output_dir)
    return {
        "name": project.name,
        "network": project.network,
        "network_type": project.network_type,
        "input_dir": project.input_dir,
        "steps": [
            {
                "type": step.type,
                "config": _jsonable(step.config),
                "status": state.get(step.type).get("status", "pending") if state else "pending",
                "prerequisites": STEP_PREREQUISITES.get(step.type, []),
                "optional": step.type in OPTIONAL_STEP_TYPES,
                "substeps": substep_payloads(step.type, step.substeps, state),
                **_step_attention(step, scan_dir),
            }
            for step in project.pipeline
        ],
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
