"""Background runner and UI interaction provider for the webview app."""
from __future__ import annotations

import contextlib
import dataclasses
import io
import re
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from rich.console import Console

from ..interaction import InteractionProvider, RegionCaptioner
from ..invoke import STEP_INVOKE_MAP
from ..paths import PROJECT_ROOT
from ..pipeline import RunConfig
from ..project.base import STEP_PREREQUISITES, ProjectConfig
from ..project import registry as project_registry
from ..utils.state import RunState


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ANSI_ESCAPE_RE = re.compile(
    r"""
    \x1B
    (?:
        \][^\x07]*(?:\x07|\x1B\\)      # OSC: ESC ] ... BEL/ST
        |
        [@-Z\\-_]                       # 7-bit C1 Fe
        |
        \[[0-?]*[ -/]*[@-~]             # CSI
    )
    """,
    re.VERBOSE,
)


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


def _plain_log_line(line: str) -> str:
    return ANSI_ESCAPE_RE.sub("", line)


class _LogStream(io.TextIOBase):
    encoding = "utf-8"
    errors = "replace"

    def __init__(self, job: "PipelineJob") -> None:
        self._job = job
        self._buf = ""

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            clean = _plain_log_line(line.rstrip())
            if clean.strip():
                self._job.add_log(clean)
        return len(text)

    def flush(self) -> None:
        clean = _plain_log_line(self._buf.rstrip())
        if clean.strip():
            self._job.add_log(clean)
        self._buf = ""


class PipelineJob:
    """Mutable job state guarded by a condition variable."""

    def __init__(self, manager: "JobManager", job_id: str) -> None:
        self.manager = manager
        self.id = job_id
        self.status = "queued"
        self.current_step: str | None = None
        self.completed_steps: list[str] = []
        self.skipped_steps: list[str] = []
        self.error: str | None = None
        self.result: dict[str, Any] | None = None
        self.logs: list[str] = []
        self.pending_input: dict[str, Any] | None = None
        self._pending_answer: Any = None
        self._has_answer = False
        self.cancel_requested = False
        self._condition = threading.Condition()
        self._thread: threading.Thread | None = None

    def start(self, target, *args) -> None:
        self._thread = threading.Thread(target=target, args=args, daemon=True)
        self._thread.start()

    def add_log(self, line: str) -> None:
        with self._condition:
            self.logs.append(line)
            if len(self.logs) > 1000:
                self.logs = self.logs[-1000:]
            self._condition.notify_all()

    def set_status(self, status: str, *, current_step: str | None = None) -> None:
        with self._condition:
            self.status = status
            self.current_step = current_step
            self._condition.notify_all()

    def request_input(self, kind: str, payload: dict[str, Any]) -> Any:
        request_id = uuid.uuid4().hex
        with self._condition:
            self.status = "waiting_input"
            self.pending_input = {
                "id": request_id,
                "kind": kind,
                "payload": payload,
            }
            self._pending_answer = None
            self._has_answer = False
            self._condition.notify_all()
            while not self._has_answer and not self.cancel_requested:
                self._condition.wait(timeout=0.25)
            if self.cancel_requested:
                raise RuntimeError("Run cancelled")
            answer = self._pending_answer
            self.pending_input = None
            self._pending_answer = None
            self._has_answer = False
            self.status = "running"
            self._condition.notify_all()
            return answer

    def submit_input(self, request_id: str, value: Any) -> bool:
        with self._condition:
            if not self.pending_input or self.pending_input.get("id") != request_id:
                return False
            self._pending_answer = value
            self._has_answer = True
            self._condition.notify_all()
            return True

    def cancel(self) -> None:
        with self._condition:
            self.cancel_requested = True
            if self.status not in TERMINAL_STATUSES:
                self.status = "cancelling"
            self._condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            return {
                "id": self.id,
                "status": self.status,
                "current_step": self.current_step,
                "completed_steps": list(self.completed_steps),
                "skipped_steps": list(self.skipped_steps),
                "error": self.error,
                "result": self.result,
                "logs": list(self.logs),
                "pending_input": self.pending_input,
                "cancel_requested": self.cancel_requested,
            }


class UiInteractionProvider(InteractionProvider):
    """Provider that pauses a job and waits for frontend responses."""

    def __init__(self, job: PipelineJob, media_base_url: str | None = None) -> None:
        self._job = job
        self._media_base_url = media_base_url
        self._caption_lock = threading.Lock()
        self._captioner: RegionCaptioner | None = None
        self._caption_image: Path | None = None

    def source_review(self, scored: list[tuple[Path, dict]]) -> dict[str, str]:
        items = []
        for path, info in scored:
            item = _image_payload(path, self._media_base_url)
            item.update({
                "scores": _jsonable(info.get("scores", {})),
                "quality": info.get("quality"),
                "auto_reject": bool(info.get("auto_reject")),
                "auto_reasons": _jsonable(info.get("auto_reasons", [])),
                "initial_decision": "reject" if info.get("auto_reject") else "keep",
            })
            items.append(item)

        answer = self._job.request_input("source_review", {"items": items})
        decisions = answer.get("decisions", {}) if isinstance(answer, dict) else {}
        return {str(k): str(v) for k, v in decisions.items()}

    def annotate_image(
        self,
        path: Path,
        *,
        captioner: RegionCaptioner | None = None,
    ) -> tuple[list[dict], bool, bool]:
        with self._caption_lock:
            self._captioner = captioner
            self._caption_image = path
        try:
            payload = _image_payload(path, self._media_base_url)
            answer = self._job.request_input("bbox_annotation", payload)
        finally:
            with self._caption_lock:
                self._captioner = None
                self._caption_image = None

        if not isinstance(answer, dict):
            return [], True, False
        annotations = answer.get("annotations", [])
        if not isinstance(annotations, list):
            annotations = []
        return (
            annotations,
            bool(answer.get("skipped", False)),
            bool(answer.get("skip_all", False)),
        )

    def vae_review(self, items: list[dict]) -> dict[str, str]:
        payload_items = []
        for item in items:
            views = item.get("views", {}) if isinstance(item.get("views"), dict) else {}
            view_payloads = {
                name: _image_payload(Path(path), self._media_base_url)
                for name, path in views.items()
                if path
            }
            original_path = Path(str(item.get("path")))
            payload_items.append({
                "path": str(original_path.resolve()),
                "name": str(item.get("name") or original_path.name),
                "width": item.get("width"),
                "height": item.get("height"),
                "hf_loss": item.get("hf_loss"),
                "threshold": item.get("threshold"),
                "diff_threshold": item.get("diff_threshold"),
                "flagged": bool(item.get("flagged")),
                "initial_decision": str(item.get("initial_decision") or "keep"),
                "views": view_payloads,
            })

        answer = self._job.request_input("vae_review", {"items": payload_items})
        decisions = answer.get("decisions", {}) if isinstance(answer, dict) else {}
        return {str(k): str(v) for k, v in decisions.items()}

    def curate_details(self, report: dict[str, Any], report_path: Path) -> bool:
        coverage_path = report.get("coverage_image")
        coverage_image = None
        if coverage_path:
            path = Path(str(coverage_path))
            if path.is_file():
                coverage_image = _image_payload(path, self._media_base_url)

        coverage = report.get("coverage") if isinstance(report.get("coverage"), dict) else {}
        payload = {
            "report_path": str(report_path.resolve()),
            "coverage_image": coverage_image,
            "coverage_method": coverage.get("method"),
            "coverage": _jsonable(coverage),
            "summary": {
                "kept_images": len(report.get("kept_images") or []),
                "duplicate_pairs": len(report.get("duplicate_pairs") or []),
                "dropped_duplicates": len(report.get("dropped_duplicates") or []),
                "occluded_flagged": len(report.get("occluded_flagged") or []),
            },
        }
        answer = self._job.request_input("curate_details", payload)
        return bool(answer.get("confirmed", False)) if isinstance(answer, dict) else False

    def caption_region(self, image_path: str, box: dict[str, Any]) -> dict[str, Any]:
        with self._caption_lock:
            captioner = self._captioner
            active = self._caption_image
        if captioner is None or active is None:
            raise RuntimeError("No active caption annotation request")
        requested = Path(image_path).resolve()
        if requested != active.resolve():
            raise RuntimeError("Requested image is not the active annotation image")

        from PIL import Image

        with Image.open(active).convert("RGB") as img:
            w, h = img.size
            l = int(float(box["x1"]) * w)
            t = int(float(box["y1"]) * h)
            r = int(float(box["x2"]) * w)
            b = int(float(box["y2"]) * h)
            crop = img.crop((l, t, max(l + 1, r), max(t + 1, b)))
        result = captioner(crop, {"source_path": str(active), "box": box})
        if isinstance(result, dict):
            result["caption"] = str(result.get("caption") or "").strip()
            return result
        return {"caption": str(result or "").strip()}


class JobManager:
    """Starts and tracks one pipeline job at a time."""

    def __init__(
        self,
        media_base_url: str | None = None,
        projects: dict[str, ProjectConfig] | None = None,
    ) -> None:
        self._jobs: dict[str, PipelineJob] = {}
        self._active_job_id: str | None = None
        self._media_base_url = media_base_url
        self._projects = projects or {}
        self._lock = threading.Lock()

    def start_run(self, request: dict[str, Any]) -> str:
        with self._lock:
            if self._active_job_id:
                active = self._jobs.get(self._active_job_id)
                if active and active.snapshot()["status"] not in TERMINAL_STATUSES:
                    raise RuntimeError("A pipeline run is already active")
            job_id = uuid.uuid4().hex
            job = PipelineJob(self, job_id)
            self._jobs[job_id] = job
            self._active_job_id = job_id
        job.start(self._run_job, job, request)
        return job_id

    def get(self, job_id: str) -> PipelineJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise ValueError(f"Unknown job id: {job_id}") from exc

    def active_interaction_provider(self, job_id: str) -> UiInteractionProvider | None:
        job = self.get(job_id)
        provider = getattr(job, "interaction_provider", None)
        return provider

    def _run_job(self, job: PipelineJob, request: dict[str, Any]) -> None:
        stream = _LogStream(job)
        from ..utils import report as rpt

        old_console = rpt.console
        try:
            rpt.console = Console(
                file=stream,
                force_terminal=False,
                no_color=True,
                color_system=None,
                highlight=False,
                width=120,
            )
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                self._execute(job, request)
        except Exception as exc:
            job.error = str(exc)
            job.add_log(traceback.format_exc())
            job.set_status("cancelled" if job.cancel_requested else "failed")
        finally:
            stream.flush()
            rpt.console = old_console

    def _execute(self, job: PipelineJob, request: dict[str, Any]) -> None:
        job.set_status("running")

        input_dir = Path(str(request["input_dir"])).expanduser()
        output_dir_raw = request.get("output_dir")
        output_dir = Path(str(output_dir_raw)).expanduser() if output_dir_raw else _default_output(input_dir)
        project_name = str(request["project"])
        token = request.get("token") or None
        selected_steps = [str(s) for s in request.get("steps", [])]
        force = bool(request.get("force", False))

        project = self._load_project(project_name)
        self._validate_selection(project, selected_steps, output_dir)
        network = self._load_network(project)
        state = RunState(output_dir)
        interaction = UiInteractionProvider(job, self._media_base_url)
        job.interaction_provider = interaction

        cfg = RunConfig(
            dataset_dir=input_dir,
            project=project,
            concept_token=token,
            output_dir=output_dir,
            force=force,
        )
        working_dir = cfg.resolved_output_dir / "dataset"
        shared_kw = dict(
            network=network,
            concept_token=token,
            original_dir=input_dir,
            network_type=project.network_type,
            interaction=interaction,
            force=force,
            caption_runtime={
                "model_id": request.get("caption_model_id") or None,
                "vram_mode": request.get("caption_vram_mode") or None,
            },
            mock_runtime=bool(request.get("mock_runtime", False)),
            mock_curate_coverage=str(request.get("mock_curate_coverage") or "auto"),
        )

        selected = set(selected_steps)
        for step in project.pipeline:
            if step.type not in selected:
                continue
            if job.cancel_requested:
                raise RuntimeError("Run cancelled")
            job.set_status("running", current_step=step.type)
            if not force and state.is_done(step.type):
                job.skipped_steps.append(step.type)
                job.add_log(f"{step.type} already done; skipping")
                continue

            invoke = STEP_INVOKE_MAP[step.type]
            result = invoke(working_dir, cfg.resolved_output_dir, step.config, **shared_kw)
            if step.type == "AuditStep" and isinstance(result, dict) and not result.get("pass"):
                job.add_log("AuditStep found issues; review reports/AuditStep_report.json")
            if step.type == "CurateStep" and isinstance(result, dict):
                interaction.curate_details(
                    result,
                    cfg.resolved_output_dir / "reports" / "CurateStep_report.json",
                )
            state.mark_done(step.type)
            job.completed_steps.append(step.type)

        job.result = {
            "output_dir": str(cfg.resolved_output_dir),
            "reports_dir": str(cfg.resolved_output_dir / "reports"),
            "run_config": str(cfg.resolved_output_dir / "run_config.yaml"),
        }
        job.set_status("completed", current_step=None)

    def _validate_selection(
        self,
        project: ProjectConfig,
        selected_steps: list[str],
        output_dir: Path,
    ) -> None:
        known = [s.type for s in project.pipeline]
        unknown = [s for s in selected_steps if s not in known]
        if unknown:
            raise ValueError(f"Selected step is not in project pipeline: {', '.join(unknown)}")
        if not selected_steps:
            raise ValueError("Select at least one pipeline step")

        state = RunState(output_dir)
        selected = set(selected_steps)
        for step_type in selected_steps:
            for req in STEP_PREREQUISITES.get(step_type, []):
                if req not in selected and not state.is_done(req):
                    raise ValueError(f"{step_type} requires completed or selected prerequisite {req}")

        first_selected_index = min(known.index(s) for s in selected)
        quality_selected = "QualityGateStep" in selected
        if first_selected_index > 0 and not (output_dir / "dataset").exists() and not quality_selected:
            raise ValueError(
                "The working dataset does not exist. Select QualityGateStep first or choose an existing output."
            )

    @staticmethod
    def _load_network(project: ProjectConfig):
        from ..networks import registry as net_registry

        return net_registry.load(project.network)

    def _load_project(self, name: str) -> ProjectConfig:
        if name in self._projects:
            return self._projects[name]
        return project_registry.load(name)


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
            }
            for step in project.pipeline
        ],
    }
