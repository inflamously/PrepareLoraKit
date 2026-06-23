"""pywebview bridge exposed to the frontend."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..paths import PROJECT_ROOT
from ..project.base import ProjectConfig
from ..project import registry as project_registry
from .runner import JobManager, _default_output, project_payload


class UiBridge:
    """Synchronous API object consumed through window.pywebview.api."""

    def __init__(
        self,
        media_base_url: str | None = None,
        projects: dict[str, ProjectConfig] | None = None,
        bootstrap: dict[str, Any] | None = None,
    ) -> None:
        self._projects = projects or {}
        self._bootstrap = bootstrap
        self.jobs = JobManager(media_base_url=media_base_url, projects=self._projects)

    def app_info(self) -> dict[str, Any]:
        return {
            "project_root": str(PROJECT_ROOT),
            "default_outputs": str(PROJECT_ROOT / "outputs"),
            "bootstrap": self._bootstrap,
        }

    def list_projects(self) -> dict[str, Any]:
        projects = sorted(set(project_registry.list_projects()) | set(self._projects))
        return {"projects": projects}

    def choose_folder(self) -> dict[str, Any]:
        try:
            import webview

            window = webview.windows[0] if webview.windows else None
            if window is None:
                return {"path": None}
            selected = window.create_file_dialog(webview.FileDialog.FOLDER)
            if not selected:
                return {"path": None}
            return {"path": selected[0] if isinstance(selected, (list, tuple)) else selected}
        except Exception as exc:
            return {"path": None, "error": str(exc)}

    def default_output(self, input_dir: str) -> dict[str, Any]:
        return {"output_dir": str(_default_output(Path(input_dir).expanduser()))}

    def load_project(self, project: str, output_dir: str | None = None) -> dict[str, Any]:
        loaded = self._load_project(project)
        out = Path(output_dir).expanduser() if output_dir else None
        if out is None and loaded.input_dir:
            out = _default_output(Path(loaded.input_dir).expanduser())
        return {
            "project": project_payload(loaded, out),
            "project_name": loaded.name,
            "input_dir": loaded.input_dir,
            "output_dir": str(out) if out is not None else None,
        }

    def load_or_create_project_for_input(
        self,
        input_dir: str,
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        resolved_input = Path(input_dir).expanduser().resolve()
        loaded = project_registry.load_or_create_for_input(resolved_input)
        out = Path(output_dir).expanduser() if output_dir else _default_output(resolved_input)
        return {
            "project": project_payload(loaded, out),
            "project_name": loaded.name,
            "input_dir": str(resolved_input),
            "output_dir": str(out),
        }

    def start_run(self, request: dict[str, Any]) -> dict[str, Any]:
        job_id = self.jobs.start_run(request)
        return {"job_id": job_id}

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        return {"job": self.jobs.get(job_id).snapshot()}

    def submit_interaction(self, job_id: str, request_id: str, value: Any) -> dict[str, Any]:
        accepted = self.jobs.get(job_id).submit_input(request_id, value)
        return {"accepted": accepted}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        self.jobs.get(job_id).cancel()
        return {"cancel_requested": True}

    def shutdown(self, *_args) -> dict[str, Any]:
        return {"cancel_requested": self.jobs.cancel_active()}

    def caption_region(self, job_id: str, image_path: str, box: dict[str, Any]) -> dict[str, Any]:
        provider = self.jobs.active_interaction_provider(job_id)
        if provider is None:
            raise RuntimeError("No active UI interaction provider")
        return provider.caption_region(image_path, box)

    def open_path(self, path: str) -> dict[str, Any]:
        p = Path(path).expanduser()
        target = p if p.exists() else p.parent
        if not target.exists():
            return {"opened": False, "error": f"Path does not exist: {target}"}

        if sys.platform.startswith("win"):
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return {"opened": True}

    def _load_project(self, name: str) -> ProjectConfig:
        if name in self._projects:
            return self._projects[name]
        return project_registry.load(name)
