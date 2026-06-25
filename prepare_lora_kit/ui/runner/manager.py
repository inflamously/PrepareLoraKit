"""Pipeline job manager and execution orchestration."""
from __future__ import annotations

import contextlib
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any

from rich.console import Console

from . import UiInteractionProvider
from ...cancellation import CancelledRun
from ...pipeline import RunConfig
from ...project import registry as project_registry
from ...project.base import ProjectConfig
from ...project.config_schema import apply_overrides, has_schema
from ...project.steps import (
    STEP_PREREQUISITES,
    SUBSTEP_REGISTRY,
    enabled_substep_ids,
    is_step_satisfied,
    mark_legacy_import_satisfied,
    normalize_substeps,
)
from ...utils.state import RunState
from .constants import TERMINAL_STATUSES
from .job import PipelineJob
from .logging import _LogStream
from .payloads import _default_output


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
        from ...utils import report as rpt

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
        except CancelledRun as exc:
            job.error = str(exc)
            job.set_status("cancelled")
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
        requested_substeps = {
            str(step_type): [str(substep_id) for substep_id in substeps]
            for step_type, substeps in (request.get("substeps") or {}).items()
            if isinstance(substeps, list)
        }
        force = bool(request.get("force", False))
        pause_for_config = bool(request.get("pause_for_config", False))

        project = self._load_project(project_name)
        selected_substeps = self._resolve_selected_substeps(project, selected_steps, requested_substeps)
        self._validate_selection(project, selected_steps, output_dir, selected_substeps)
        network = self._load_network(project)
        state = RunState(output_dir)
        from . import UiInteractionProvider

        interaction = UiInteractionProvider(job, self._media_base_url)
        job.interaction_provider = interaction

        cfg = RunConfig(
            dataset_dir=input_dir,
            project=project,
            concept_token=token,
            output_dir=output_dir,
            force=force,
            cancel_check=job.raise_if_cancelled,
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
                "task": request.get("caption_model_task") or None,
            },
            caption_status_callback=job.set_caption_status,
            mock_runtime=bool(request.get("mock_runtime", False)),
            mock_curate_coverage=str(request.get("mock_curate_coverage") or "auto"),
            cancel_check=job.raise_if_cancelled,
        )

        selected = set(selected_steps)
        for step in project.pipeline:
            if step.type not in selected:
                continue
            if job.cancel_requested:
                raise CancelledRun("Run cancelled")
            enabled_substeps = selected_substeps.get(step.type, enabled_substep_ids(step.type, step.substeps))
            job.set_status(
                "running",
                current_step=step.type,
                current_substep=enabled_substeps[0] if enabled_substeps else None,
            )
            if (
                not force
                and step.type == "ImportStep"
                and mark_legacy_import_satisfied(state, cfg.resolved_output_dir)
            ):
                job.skipped_steps.append(step.type)
                job.skipped_substeps[step.type] = enabled_substeps
                job.add_log("ImportStep satisfied by existing working dataset")
                continue
            if not force and state.is_done(step.type):
                job.skipped_steps.append(step.type)
                job.skipped_substeps[step.type] = enabled_substeps
                job.add_log(f"{step.type} already done; skipping")
                continue

            effective_config = step.config
            if pause_for_config and has_schema(step.type):
                effective_config = self._resolve_step_config(job, interaction, step)

            from . import STEP_INVOKE_MAP

            invoke = STEP_INVOKE_MAP[step.type]
            result = invoke(
                working_dir,
                cfg.resolved_output_dir,
                effective_config,
                **shared_kw,
                enabled_substeps=enabled_substeps,
            )
            job.raise_if_cancelled()
            if step.type == "AuditStep" and isinstance(result, dict) and not result.get("pass"):
                job.add_log("AuditStep found issues; review reports/AuditStep_report.json")
            if step.type == "CurateStep" and isinstance(result, dict):
                job.raise_if_cancelled()
                interaction.curate_details(
                    result,
                    cfg.resolved_output_dir / "reports" / "CurateStep_report.json",
                )
                job.raise_if_cancelled()
            for substep_id in enabled_substeps:
                state.mark_substep_done(step.type, substep_id)
            state.mark_done(step.type, {"enabled_substeps": enabled_substeps})
            job.completed_steps.append(step.type)
            job.completed_substeps[step.type] = enabled_substeps

        job.result = {
            "output_dir": str(cfg.resolved_output_dir),
            "reports_dir": str(cfg.resolved_output_dir / "reports"),
            "run_config": str(cfg.resolved_output_dir / "run_config.yaml"),
        }
        job.set_status("completed", current_step=None, current_substep=None)

    def _resolve_step_config(self, job: PipelineJob, interaction, step):
        """Pause for frontend config edits and return the validated step config.

        Re-prompts (with the validation error) until the overrides apply cleanly
        or the run is cancelled.
        """
        error: str | None = None
        while True:
            overrides = interaction.step_config(step.type, step.config, error=error)
            try:
                return apply_overrides(step.type, step.config, overrides)
            except ValueError as exc:
                error = str(exc)
                job.add_log(f"{step.type} config rejected: {exc}")

    def _resolve_selected_substeps(
        self,
        project: ProjectConfig,
        selected_steps: list[str],
        requested_substeps: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        selected = set(selected_steps)
        resolved: dict[str, list[str]] = {}
        for step in project.pipeline:
            if step.type not in selected:
                continue
            raw = requested_substeps.get(step.type)
            if raw is None:
                resolved[step.type] = enabled_substep_ids(step.type, step.substeps)
                continue
            known = {definition.id for definition in SUBSTEP_REGISTRY.get(step.type, ())}
            unknown = [substep_id for substep_id in raw if substep_id not in known]
            if unknown:
                raise ValueError(
                    f"Selected substep is not in {step.type}: {', '.join(unknown)}"
                )
            substeps = normalize_substeps(
                step.type,
                [{"id": definition.id, "enabled": definition.id in set(raw)}
                 for definition in SUBSTEP_REGISTRY.get(step.type, ())],
                step.config,
            )
            resolved[step.type] = enabled_substep_ids(step.type, substeps)
        return resolved

    def _validate_selection(
        self,
        project: ProjectConfig,
        selected_steps: list[str],
        output_dir: Path,
        selected_substeps: dict[str, list[str]] | None = None,
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
            enabled_substeps = (selected_substeps or {}).get(step_type)
            if enabled_substeps == []:
                raise ValueError(f"{step_type} has no enabled substeps")
            if enabled_substeps is not None:
                enabled_set = set(enabled_substeps)
                for definition in SUBSTEP_REGISTRY.get(step_type, ()):
                    if definition.id not in enabled_set:
                        continue
                    missing = [
                        req for req in definition.prerequisites
                        if req not in enabled_set
                    ]
                    if missing:
                        raise ValueError(
                            f"{definition.id} requires enabled substep {', '.join(missing)}"
                        )
            for req in STEP_PREREQUISITES.get(step_type, []):
                if req not in selected and not is_step_satisfied(req, state, output_dir):
                    raise ValueError(f"{step_type} requires completed or selected prerequisite {req}")

        needs_working_dataset = any(step_type != "ImportStep" for step_type in selected)
        if needs_working_dataset and "ImportStep" not in selected and not (output_dir / "dataset").exists():
            raise ValueError(
                "The working dataset does not exist. Select ImportStep first or choose an existing output."
            )

    @staticmethod
    def _load_network(project: ProjectConfig):
        from ...networks import registry as net_registry

        return net_registry.load(project.network)

    def _load_project(self, name: str) -> ProjectConfig:
        if name in self._projects:
            return self._projects[name]
        return project_registry.load(name)
