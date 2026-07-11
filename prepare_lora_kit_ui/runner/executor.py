"""Desktop UI adapter for the shared pipeline execution engine."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prepare_lora_kit.pipeline.execution import execute_pipeline
from prepare_lora_kit.project import project_registry
from prepare_lora_kit.project.base import ProjectConfig

from prepare_lora_kit_ui.runner.execution_hooks import StepConfigResolver, UiJobHooks
from prepare_lora_kit_ui.runner.job import PipelineJob
from prepare_lora_kit_ui.runner.run_request import UiRunRequest

if TYPE_CHECKING:
    from prepare_lora_kit_ui.runner.interactions import UiInteractionProvider


class UiPipelineExecutor:
    """Parse a bridge run request and adapt engine events to a ``PipelineJob``."""

    def __init__(
            self,
            media_base_url: str | None = None,
            projects: dict[str, ProjectConfig] | None = None,
            interaction_provider_cls: type[UiInteractionProvider] | None = None,
    ) -> None:
        self._media_base_url = media_base_url
        self._projects = projects or {}
        self._interaction_provider_cls = interaction_provider_cls

    def execute(self, job: PipelineJob, request: dict[str, Any]) -> None:
        job.set_status("running")
        parsed = UiRunRequest.from_payload(request)
        project = self.load_project(parsed.project_name)
        interaction = self._create_interaction(job)
        job.interaction_provider = interaction
        hooks = UiJobHooks(job, interaction, parsed.pause_for_config)
        execute_pipeline(
            parsed.to_run_config(project, interaction, job),
            hooks.to_execution_hooks(),
        )

    def resolve_step_config(self, job: PipelineJob, interaction, step):
        """Compatibility entry point for integrations that resolve config directly."""

        return StepConfigResolver(job, interaction).resolve(step)

    def _create_interaction(self, job: PipelineJob) -> UiInteractionProvider:
        interaction_provider_cls = self._interaction_provider_cls
        if interaction_provider_cls is None:
            # Resolve through the facade so integrations can replace the
            # provider without coupling the core engine to the desktop UI.
            import prepare_lora_kit_ui.runner as runner
            interaction_provider_cls = runner.UiInteractionProvider
        return interaction_provider_cls(job, self._media_base_url)

    def load_project(self, name: str) -> ProjectConfig:
        if name in self._projects:
            return self._projects[name]
        return project_registry.load(name)
