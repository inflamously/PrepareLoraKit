"""Data passed into and returned from shared pipeline execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from prepare_lora_kit.cancellation import CancelCheck
from prepare_lora_kit.paths import PROJECT_ROOT
from prepare_lora_kit.project.base import PipelineStep, ProjectConfig


@dataclass
class RunConfig:
    """All inputs needed to execute a project pipeline."""

    dataset_dir: Path
    project: ProjectConfig
    concept_token: Optional[str] = None
    output_dir: Optional[Path] = None
    force: bool = False
    cancel_check: CancelCheck | None = None
    selected_steps: list[str] | None = None
    requested_substeps: dict[str, list[str]] | None = None
    invoke_kwargs: dict[str, Any] = field(default_factory=dict)

    @property
    def resolved_output_dir(self) -> Path:
        return self.output_dir or (PROJECT_ROOT / "outputs" / self.dataset_dir.name)


@dataclass
class ExecutionResult:
    """Collected state from a successful pipeline execution."""

    output_dir: Path
    reports_dir: Path
    completed_steps: list[str] = field(default_factory=list)
    skipped_steps: list[str] = field(default_factory=list)
    completed_substeps: dict[str, list[str]] = field(default_factory=dict)
    skipped_substeps: dict[str, list[str]] = field(default_factory=dict)


StepStartHook = Callable[[PipelineStep, list[str]], None]
StepSkipHook = Callable[[PipelineStep, list[str], str], None]
SubstepCompleteHook = Callable[[PipelineStep, str], None]
ConfigResolver = Callable[[PipelineStep], Any]
PostStepHook = Callable[[PipelineStep, Any, Path], None]
StepCompleteHook = Callable[[PipelineStep, list[str]], None]
CompletionHook = Callable[[ExecutionResult], None]


@dataclass
class ExecutionHooks:
    """Optional adapter callbacks around the shared ordered step loop."""

    step_start: StepStartHook | None = None
    step_skip: StepSkipHook | None = None
    substep_complete: SubstepCompleteHook | None = None
    resolve_config: ConfigResolver | None = None
    post_step: PostStepHook | None = None
    step_complete: StepCompleteHook | None = None
    complete: CompletionHook | None = None
