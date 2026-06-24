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


def project_payload(project: ProjectConfig, output_dir: Path | None = None) -> dict[str, Any]:
    state = RunState(output_dir) if output_dir is not None else None
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
            }
            for step in project.pipeline
        ],
    }
