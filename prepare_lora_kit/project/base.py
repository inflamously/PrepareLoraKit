"""
ProjectConfig — top-level per-project pipeline configuration.

Separate from NetworkProfile (which describes the *model*). A ProjectConfig
references a network by name and holds a pipeline: an ordered list of
PipelineStep entries. Each entry has a type (e.g. "CaptionStep") and
step-specific config fields.

The per-step config dataclasses live in ``configs.py``; this module wires
them into the pipeline registry and validates project-level structure.

Loaded from configs/projects/<name>.yaml via the project registry.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import yaml

from .configs import ScorerEntry
from .steps import (
    STEP_ORDER_INDEX,
    STEP_PREREQUISITES,
    STEP_TYPE_MAP,
    PipelineSubstep,
    normalize_substeps,
)


# ── Step Type Registry ────────────────────────────────────────────────────────
# STEP_TYPE_MAP and STEP_PREREQUISITES are re-exported from project.steps for
# callers that still import them from project.base.


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
    network: str                         # references a NetworkProfile by name
    # Optional per-run adapter-network type override (lora|lokr|dora). When set,
    # it wins over the profile's config_template.network.type in step 7.
    network_type: Optional[str] = None
    input_dir: Optional[str] = None
    pipeline: list[PipelineStep] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.pipeline = _normalize_pipeline_steps(self.pipeline)
        if not self.name:
            raise ValueError("ProjectConfig: 'name' is required")
        if not self.network:
            raise ValueError("ProjectConfig: 'network' is required")
        if self.network_type is not None:
            from ..networks.net_types import KNOWN_NET_TYPES
            if self.network_type not in KNOWN_NET_TYPES:
                raise ValueError(
                    f"ProjectConfig: unknown network_type '{self.network_type}'. "
                    f"Known: {', '.join(sorted(KNOWN_NET_TYPES))}"
                )
        self._validate_pipeline()

    def _validate_pipeline(self) -> None:
        seen: set[str] = set()
        previous_index = -1
        for step in self.pipeline:
            t = step.type
            if t not in STEP_TYPE_MAP:
                raise ValueError(
                    f"Unknown step type '{t}'. Known types: {', '.join(sorted(STEP_TYPE_MAP))}"
                )
            if t in seen:
                raise ValueError(f"Duplicate step type '{t}' in pipeline.")
            index = STEP_ORDER_INDEX[t]
            if index <= previous_index:
                raise ValueError(
                    f"Step '{t}' appears out of order. Expected pipeline order: "
                    f"{', '.join(STEP_TYPE_MAP)}"
                )
            for req in STEP_PREREQUISITES.get(t, []):
                if req not in seen:
                    raise ValueError(
                        f"'{t}' requires '{req}' to appear earlier in the pipeline."
                    )
            step.substeps = normalize_substeps(t, step.substeps or None, step.config)
            seen.add(t)
            previous_index = index

    @classmethod
    def from_yaml(cls, path: Path) -> "ProjectConfig":
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        name = data.pop("name")
        network = data.pop("network")
        network_type = data.pop("network_type", None)
        input_dir = data.pop("input_dir", None)
        raw_pipeline = data.pop("pipeline", []) or []
        raw_pipeline = _normalize_raw_pipeline(raw_pipeline)

        pipeline: list[PipelineStep] = []
        for raw in raw_pipeline:
            raw = dict(raw)
            step_type = raw.pop("type")
            raw_substeps = raw.pop("substeps", None)
            config_cls = STEP_TYPE_MAP.get(step_type)
            if config_cls is None:
                raise ValueError(
                    f"Unknown step type '{step_type}'. "
                    f"Known: {', '.join(sorted(STEP_TYPE_MAP))}"
                )
            # Type-specific coercions
            if step_type == "QualityGateStep" and raw.get("scorers") is not None:
                raw["scorers"] = [ScorerEntry(**s) for s in raw["scorers"]]
            if step_type == "BucketDryRunStep" and raw.get("bucket_overrides") is not None:
                raw["bucket_overrides"] = [tuple(b) for b in raw["bucket_overrides"]]
            config = config_cls(**raw)
            pipeline.append(
                PipelineStep(
                    type=step_type,
                    config=config,
                    substeps=normalize_substeps(step_type, raw_substeps, config),
                )
            )

        return cls(name=name, network=network, network_type=network_type,
                   input_dir=input_dir, pipeline=pipeline)


def _normalize_raw_pipeline(raw_pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if raw_pipeline and raw_pipeline[0].get("type") == "QualityGateStep":
        return [{"type": "ImportStep"}, *raw_pipeline]
    return raw_pipeline


def _normalize_pipeline_steps(pipeline: list[PipelineStep]) -> list[PipelineStep]:
    if pipeline and pipeline[0].type == "QualityGateStep":
        import_config = STEP_TYPE_MAP["ImportStep"]()
        import_step = PipelineStep(
            type="ImportStep",
            config=import_config,
            substeps=normalize_substeps("ImportStep", None, import_config),
        )
        return [import_step, *pipeline]
    return pipeline
