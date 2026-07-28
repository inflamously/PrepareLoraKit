"""pywebview bridge exposed to the frontend."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from prepare_lora_kit import caption_prompts
from prepare_lora_kit_ui.paths import PROJECT_ROOT
from prepare_lora_kit.project import project_registry, store
from prepare_lora_kit.project.base import ProjectConfig

from prepare_lora_kit_ui.runner import (
    JobManager,
    _default_output,
    output_exists,
    project_payload,
    project_status,
)

def _card_output_dir(input_dir: Any, output_dir: Any) -> Path | None:
    """Where a project's outputs land: its own setting, else derived from input."""

    if output_dir:
        return Path(str(output_dir)).expanduser()
    if input_dir:
        return _default_output(Path(str(input_dir)).expanduser())
    return None


def _initials(name: str) -> str:
    """Two-character mono badge derived from a project name."""
    parts = [p for p in name.replace("-", "_").replace(" ", "_").split("_") if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if parts:
        return parts[0][:2].upper()
    return "??"


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
        names = sorted(set(project_registry.list_projects()) | set(self._projects))
        live = self.jobs.project_statuses()
        return {"projects": [self._project_card(name, live) for name in names]}

    def _project_card(
        self, name: str, live: dict[str, str] | None = None
    ) -> dict[str, Any]:
        live = live if live is not None else self.jobs.project_statuses()
        # Identity comes from index.yaml alone — no step file is opened for it.
        # That is what lets a project with one unparseable <step>.yaml still show
        # a usable card instead of an error tile with no name or paths.
        identity, mtime = self._project_identity(name)
        card_name = identity.get("name") or name
        input_dir = identity.get("input_dir")
        out = _card_output_dir(input_dir, identity.get("output_dir"))

        card = {
            "name": card_name,
            "input_dir": input_dir,
            "output_dir": str(out) if out is not None else None,
            "initials": _initials(card_name),
            "token": None,
            "status": "draft",
            "mtime": mtime,
        }

        try:
            loaded = self._load_project(name)
        except Exception as exc:
            # Status needs the full pipeline; without it the card stays a draft.
            card["error"] = str(exc)
            return card

        card["status"] = project_status(loaded, out, live.get(loaded.name))
        return card

    def _project_identity(self, name: str) -> tuple[dict[str, Any], float]:
        """A project's name and dirs, plus the mtime the library sorts by."""

        in_memory = self._projects.get(name)
        if in_memory is not None:
            return (
                {
                    "name": in_memory.name,
                    "input_dir": in_memory.input_dir,
                    "output_dir": in_memory.output_dir,
                },
                0,
            )
        try:
            index_path = project_registry.index_path_for_name(name)
            identity = store.read_index(index_path.parent)
            return identity, index_path.stat().st_mtime
        except Exception:
            return {}, 0

    def create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_registry.create_project(
            name=str(payload.get("name", "")),
            input_dir=payload.get("input_dir") or None,
            output_dir=payload.get("output_dir") or None,
        )
        return {"project": self._project_card(str(payload["name"]).strip())}

    def update_project(self, orig_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        project_registry.update_project_meta(
            orig_name=orig_name,
            name=str(payload.get("name", "")),
            input_dir=payload.get("input_dir") or None,
            output_dir=payload.get("output_dir") or None,
        )
        return {"project": self._project_card(str(payload["name"]).strip())}

    def delete_project(self, name: str) -> dict[str, Any]:
        project_registry.delete_project(name)
        return {"deleted": True}

    def duplicate_project(self, name: str) -> dict[str, Any]:
        new_name = project_registry.duplicate_project(name)
        return {"project": self._project_card(new_name)}

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
        if out is None and loaded.output_dir:
            out = Path(loaded.output_dir).expanduser()
        if out is None and loaded.input_dir:
            out = _default_output(Path(loaded.input_dir).expanduser())
        return {
            "project": project_payload(loaded, out),
            "project_name": loaded.name,
            "input_dir": loaded.input_dir,
            "output_dir": str(out) if out is not None else None,
            "output_exists": output_exists(out),
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
            "output_exists": output_exists(out),
        }

    def start_run(self, request: dict[str, Any]) -> dict[str, Any]:
        job_id = self.jobs.start_run(request)
        return {"job_id": job_id}

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        return {"job": self.jobs.get(job_id).snapshot()}

    def active_job(self) -> dict[str, Any]:
        """Expose the in-flight job so a reloaded frontend can reconnect to it."""
        return {"active": self.jobs.active_job()}

    def submit_interaction(self, job_id: str, request_id: str, value: Any) -> dict[str, Any]:
        accepted = self.jobs.get(job_id).submit_input(request_id, value)
        return {"accepted": accepted}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        requested = self.jobs.get(job_id).cancel()
        return {"cancel_requested": requested}

    def shutdown(self, *_args) -> dict[str, Any]:
        return {"cancel_requested": self.jobs.cancel_active()}

    def list_caption_prompts(self, kind: str) -> dict[str, Any]:
        return {"prompts": [p.to_dict() for p in caption_prompts.list_prompts(kind)]}

    def save_caption_prompt(self, kind: str, name: str, text: str) -> dict[str, Any]:
        caption_prompts.save(kind, name, text)
        return {
            "saved": True,
            "prompts": [p.to_dict() for p in caption_prompts.list_prompts(kind)],
        }

    def delete_caption_prompt(self, kind: str, name: str) -> dict[str, Any]:
        caption_prompts.delete(kind, name)
        return {
            "deleted": True,
            "prompts": [p.to_dict() for p in caption_prompts.list_prompts(kind)],
        }

    # ── App-wide settings ─────────────────────────────────────────────────────
    # Global, like the caption-prompt library above: not scoped to any project or
    # job. get_settings stays cheap — no network, no torch — so the modal opens
    # instantly; everything slow sits behind its own button below.

    def get_settings(self) -> dict[str, Any]:
        from prepare_lora_kit.settings import load_settings
        from prepare_lora_kit.settings.payload import settings_payload

        return settings_payload(load_settings())

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        from prepare_lora_kit.settings import save_settings_dict
        from prepare_lora_kit.settings.payload import settings_payload

        return settings_payload(save_settings_dict(payload or {}))

    def hf_status(self) -> dict[str, Any]:
        """Hugging Face login state. Network call — only ever from a button."""
        from prepare_lora_kit.settings import hub

        return {
            "token": hub.token_status(),
            "account": hub.account(),
            "login_command": hub.login_command(),
        }

    def check_model_access(self, repo_ids: list[str] | None = None) -> dict[str, Any]:
        """Can this machine read the configured models? Network call, button-driven."""
        from prepare_lora_kit.settings import hub, load_settings
        from prepare_lora_kit.settings.payload import configured_model_ids

        ids = repo_ids if repo_ids else configured_model_ids(load_settings())
        return {"results": hub.check_repos(list(ids))}

    def detect_hardware(self) -> dict[str, Any]:
        """Probe VRAM and suggest a tier. Imports torch, so it is button-driven."""
        from prepare_lora_kit.embedding.vram import total_vram_gb

        total = float(total_vram_gb() or 0.0)
        if not total:
            suggested = None
        elif total <= 16:
            suggested = "low"
        elif total <= 24:
            suggested = "mid"
        elif total <= 32:
            suggested = "high"
        else:
            suggested = "max"
        return {"cuda": total > 0, "total_vram_gb": round(total, 1), "suggested_tier": suggested}

    def caption_region(self, job_id: str, image_path: str, box: dict[str, Any]) -> dict[str, Any]:
        provider = self.jobs.active_interaction_provider(job_id)
        if provider is None:
            raise RuntimeError("No active UI interaction provider")
        return provider.caption_region(image_path, box)

    def generate_caption_preview(
        self,
        job_id: str,
        image_path: str,
        caption: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Render one caption while the caption-verify modal is open.

        Re-roll is ``options={"reroll": true}`` rather than a second method:
        it differs only in seed policy, so one entry point keeps the bridge, the
        JSDoc and the JS call site singular.
        """
        provider = self.jobs.active_interaction_provider(job_id)
        if provider is None:
            raise RuntimeError("No active UI interaction provider")
        return provider.generate_caption_preview(image_path, caption, options or {})

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
