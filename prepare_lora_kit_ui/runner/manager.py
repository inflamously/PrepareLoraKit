"""Pipeline job registration and thread lifecycle management."""
from __future__ import annotations

import contextlib
import threading
import traceback
import uuid
from typing import TYPE_CHECKING, Any

from rich.console import Console

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit.report import reporter

from prepare_lora_kit_ui.runner.constants import TERMINAL_STATUSES
from prepare_lora_kit_ui.runner.executor import UiPipelineExecutor
from prepare_lora_kit_ui.runner.job import PipelineJob
from prepare_lora_kit_ui.runner.logging import _LogStream

if TYPE_CHECKING:
    from prepare_lora_kit_ui.runner.interactions import UiInteractionProvider

class JobManager:
    """Starts and tracks one pipeline job at a time."""

    def __init__(
            self,
            media_base_url: str | None = None,
            projects: dict[str, ProjectConfig] | None = None,
            interaction_provider_cls: type[UiInteractionProvider] | None = None,
    ) -> None:
        self._jobs: dict[str, PipelineJob] = {}
        self._job_projects: dict[str, str] = {}
        self._active_job_id: str | None = None
        self._executor = UiPipelineExecutor(
            media_base_url=media_base_url,
            projects=projects,
            interaction_provider_cls=interaction_provider_cls,
        )
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
            project_name = request.get("project")
            if project_name:
                self._job_projects[job_id] = str(project_name)
            self._active_job_id = job_id
        job.start(self._run_job, job, request)
        return job_id

    def project_statuses(self) -> dict[str, str]:
        """Map project name -> latest job status for any project that has run."""
        statuses: dict[str, str] = {}
        for job_id, name in self._job_projects.items():
            job = self._jobs.get(job_id)
            if job is None:
                continue
            statuses[name] = job.snapshot()["status"]
        return statuses

    def active_job(self) -> dict[str, Any] | None:
        """Return the in-flight job (id, project, snapshot), or None if idle.

        Used to reconnect the frontend to a still-running pipeline after the
        webview is reloaded (F5), which wipes JS state but leaves this manager
        and its job thread untouched.
        """
        with self._lock:
            job_id = self._active_job_id
            job = self._jobs.get(job_id) if job_id else None
            project = self._job_projects.get(job_id) if job_id else None
        if job_id is None or job is None:
            return None
        snapshot = job.snapshot()
        if snapshot["status"] in TERMINAL_STATUSES:
            return None
        return {"job_id": job_id, "project": project, "job": snapshot}

    def get(self, job_id: str) -> PipelineJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise ValueError(f"Unknown job id: {job_id}") from exc

    def cancel_active(self) -> bool:
        with self._lock:
            if self._active_job_id is None:
                return False
            job = self._jobs.get(self._active_job_id)
        if job is None:
            return False
        if job.snapshot()["status"] in TERMINAL_STATUSES:
            return False
        job.cancel()
        return True

    def active_interaction_provider(self, job_id: str) -> UiInteractionProvider | None:
        job = self.get(job_id)
        provider = getattr(job, "interaction_provider", None)
        return provider

    def _run_job(self, job: PipelineJob, request: dict[str, Any]) -> None:
        stream = _LogStream(job)
        old_console = reporter.console
        try:
            reporter.console = Console(
                file=stream,
                force_terminal=False,
                no_color=True,
                color_system=None,
                highlight=False,
                width=120,
            )
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                self._executor.execute(job, request)
        except CancelledRun as exc:
            job.error = str(exc)
            job.set_status("cancelled")
        except Exception as exc:
            job.error = str(exc)
            job.add_log(traceback.format_exc())
            job.set_status("cancelled" if job.cancel_requested else "failed")
        finally:
            stream.flush()
            reporter.console = old_console
