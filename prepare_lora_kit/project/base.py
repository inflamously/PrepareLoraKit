"""ProjectConfig — top-level per-project dataset workflow configuration.

A project is stored as a folder (see :mod:`prepare_lora_kit.project.store`), but
this module never touches the filesystem beyond :meth:`ProjectConfig.from_dir`:
it builds itself from one flat dict of the shape the store assembles, so the
parsing and validation here are independent of how the config is laid out on
disk.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from prepare_lora_kit.pipeline.configuration import (
    step_config_class,
    step_definition,
    step_prerequisites,
    step_slug,
    step_types,
)
from prepare_lora_kit.pipeline.configs import ScorerEntry
from prepare_lora_kit.project.steps import (
    PipelineSubstep,
    normalize_substeps,
)


# ── PipelineStep ──────────────────────────────────────────────────────────────

@dataclass
class PipelineStep:
    type: str
    config: Any  # one of the <StepType>Config instances
    substeps: list[PipelineSubstep] = field(default_factory=list)


# ── Top-level Project Config ──────────────────────────────────────────────────

@dataclass
class ProjectConfig:
    name: str
    input_dir: Optional[str] = None
    output_dir: Optional[str] = None
    pipeline: list[PipelineStep] = field(default_factory=list)
    # Steps the index lists but switches off. Never reaches the engine or the UI
    # payload — a disabled step is simply absent from ``pipeline``, which is a
    # state the whole pipeline already handles. This is carried only so error
    # messages can say "disabled" instead of "missing", which are very different
    # problems for a user whose tuned <step>.yaml is sitting right there.
    disabled_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ProjectConfig: 'name' is required")
        self._validate_pipeline()

    def _validate_pipeline(self) -> None:
        seen: set[str] = set()
        previous_index = -1
        for step in self.pipeline:
            t = step.type
            definition = step_definition(t)
            if definition is None:
                raise ValueError(
                    f"Unknown step type '{t}'. Known types: {', '.join(sorted(step_types()))}"
                )
            if t in seen:
                raise ValueError(f"Duplicate step type '{t}' in pipeline.")
            index = definition.order
            if index <= previous_index:
                raise ValueError(
                    f"Step '{t}' appears out of order. Reorder the `pipeline:` list "
                    f"in index.yaml to match: {', '.join(step_types())}"
                )
            for req in step_prerequisites(t):
                if req not in seen:
                    raise ValueError(
                        f"'{t}' requires '{req}' to appear earlier in the pipeline."
                    )
            step.substeps = normalize_substeps(t, step.substeps or None, step.config)
            seen.add(t)
            previous_index = index

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "ProjectConfig":
        """Build a project from one flat dict — no I/O.

        This is the seam the on-disk layout plugs into: the store assembles a
        folder into this shape, and everything below is layout-agnostic.
        """
        data = dict(data)
        name = data.get("name")
        if not name:
            raise ValueError("Project config is missing 'name'.")
        input_dir = data.get("input_dir")
        output_dir = data.get("output_dir")
        raw_pipeline = data.get("pipeline") or []

        disabled: list[str] = []
        pipeline: list[PipelineStep] = []
        for raw in raw_pipeline:
            raw = dict(raw)
            step_type = raw.pop("type")
            enabled = bool(raw.pop("enabled", True))
            raw_substeps = raw.pop("substeps", None)
            config_cls = step_config_class(step_type)
            if config_cls is None:
                raise ValueError(
                    f"Unknown step type '{step_type}'. "
                    f"Known: {', '.join(sorted(step_types()))}"
                )
            if not enabled:
                # Parked: skipped entirely, and deliberately not validated —
                # a step you have switched off must not be able to block a load.
                disabled.append(step_type)
                continue
            # Type-specific coercions
            if step_type == "QualityGateStep" and raw.get("scorers") is not None:
                raw["scorers"] = [ScorerEntry(**s) for s in raw["scorers"]]
            if step_type == "BucketPoolsCheckStep":
                if raw.get("resolution_buckets") is not None:
                    raw["resolution_buckets"] = [tuple(b) for b in raw["resolution_buckets"]]
            config = config_cls(**raw)
            pipeline.append(
                PipelineStep(
                    type=step_type,
                    config=config,
                    substeps=normalize_substeps(step_type, raw_substeps, config),
                )
            )

        _reject_disabled_prerequisites(pipeline, disabled)
        return cls(
            name=name,
            input_dir=input_dir,
            output_dir=output_dir,
            pipeline=pipeline,
            disabled_types=tuple(disabled),
        )

    @classmethod
    def from_dir(cls, directory: Path) -> "ProjectConfig":
        """Load a project folder. Advisory notes are dropped; see project_registry.load."""

        from prepare_lora_kit.project import store

        data, _notes = store.read_project_folder(directory)
        return cls.from_data(data)


def _reject_disabled_prerequisites(
    pipeline: list[PipelineStep],
    disabled: list[str],
) -> None:
    """Fail with the actual cause when a prerequisite was switched off.

    ``_validate_pipeline`` would catch this a moment later, but it would report
    the prerequisite as missing — misleading when the step is sitting in the
    folder with its settings intact and one word turned it off.
    """
    if not disabled:
        return
    disabled_set = set(disabled)
    for step in pipeline:
        for req in step_prerequisites(step.type):
            if req in disabled_set:
                raise ValueError(
                    f"'{step.type}' requires '{req}', which is disabled in index.yaml. "
                    f"Set `- {{step: {step_slug(req)}, enabled: true}}`, or disable "
                    f"{step_slug(step.type)} too."
                )
