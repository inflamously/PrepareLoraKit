"""ProjectConfig — top-level per-project dataset workflow configuration."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import yaml

from prepare_lora_kit.pipeline.configuration import (
    step_config_class,
    step_definition,
    step_prerequisites,
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

    def __post_init__(self) -> None:
        self.pipeline = _normalize_pipeline_steps(self.pipeline)
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
                    f"Step '{t}' appears out of order. Expected pipeline order: "
                    f"{', '.join(step_types())}"
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
    def from_yaml(cls, path: Path) -> "ProjectConfig":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        migrated = _migrate_legacy_project_data(data)
        if migrated:
            path.write_text(yaml.safe_dump(data, sort_keys=False))

        name = data.pop("name")
        input_dir = data.pop("input_dir", None)
        output_dir = data.pop("output_dir", None)
        raw_pipeline = data.pop("pipeline", []) or []
        raw_pipeline = _normalize_raw_pipeline(raw_pipeline)

        pipeline: list[PipelineStep] = []
        for raw in raw_pipeline:
            raw = dict(raw)
            step_type = raw.pop("type")
            raw_substeps = raw.pop("substeps", None)
            config_cls = step_config_class(step_type)
            if config_cls is None:
                raise ValueError(
                    f"Unknown step type '{step_type}'. "
                    f"Known: {', '.join(sorted(step_types()))}"
                )
            # Type-specific coercions
            if step_type == "QualityGateStep" and raw.get("scorers") is not None:
                raw["scorers"] = [ScorerEntry(**s) for s in raw["scorers"]]
            if step_type == "BucketPoolsCheckStep":
                if raw.get("bucket_overrides") is not None and raw.get("resolution_buckets") is None:
                    raw["resolution_buckets"] = raw.pop("bucket_overrides")
                raw.pop("bucket_overrides", None)
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
        return cls(name=name, input_dir=input_dir, output_dir=output_dir, pipeline=pipeline)


def _normalize_raw_pipeline(raw_pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if raw_pipeline and raw_pipeline[0].get("type") == "QualityGateStep":
        return [{"type": "ImportStep"}, *raw_pipeline]
    return raw_pipeline


def _normalize_pipeline_steps(pipeline: list[PipelineStep]) -> list[PipelineStep]:
    if pipeline and pipeline[0].type == "QualityGateStep":
        import_config_cls = step_config_class("ImportStep")
        if import_config_cls is None:
            raise ValueError("Unknown step type 'ImportStep'.")
        import_config = import_config_cls()
        import_step = PipelineStep(
            type="ImportStep",
            config=import_config,
            substeps=normalize_substeps("ImportStep", None, import_config),
        )
        return [import_step, *pipeline]
    return pipeline


_STEP_MIGRATIONS: dict[str, str | None] = {
    "CaptionStep": "CaptionBboxStep",
    "BucketDryRunStep": "BucketPoolsCheckStep",
}

_SUBSTEP_MIGRATIONS: dict[str, str] = {
    "s0_import": "import_images",
    "s1_1_score": "score_images",
    "s1_2_decide": "review_decisions",
    "s2_1_dupecheck": "duplicate_check",
    "s2_2_clipscan": "clip_scan",
    "s2_3_drop_images": "drop_images",
    "s3_1_select_candidates": "select_upscale_candidates",
    "s3_2_upscale": "upscale_images",
    "s3_3_hallucination_check": "hallucination_check",
    "s5_1_annotate": "annotate_regions",
    "s5_2_caption": "caption_images",
    "s5_3_validate": "validate_captions",
    "s4_1_reconstruct": "reconstruct_images",
    "s4_2_review": "review_vae_artifacts",
    "s4_3_apply_decisions": "apply_vae_decisions",
    "s6_1_pairing": "check_pairing",
    "s6_2_corrupt": "check_corrupt_files",
    "s6_3_caption_quality": "check_caption_quality",
    "s6_4_resolution": "check_resolution",
    "s8_1_assign_buckets": "assign_bucket_pools",
    "s8_2_report_thin_buckets": "report_thin_buckets",
    "s8_3_cache_info": "write_cache_info",
    "s9_1_diff": "preview_export_diff",
    "s9_2_export": "copy_export",
}


def _migrate_legacy_project_data(data: dict[str, Any]) -> bool:
    """Rewrite legacy project YAML data to the named dataset workflow schema."""

    changed = False
    raw_pipeline = data.get("pipeline")
    if not isinstance(raw_pipeline, list):
        return changed

    migrated_pipeline: list[dict[str, Any]] = []
    for raw in raw_pipeline:
        if not isinstance(raw, dict):
            migrated_pipeline.append(raw)
            continue
        item = dict(raw)
        old_type = str(item.get("type", ""))
        new_type = _STEP_MIGRATIONS.get(old_type, old_type)
        if new_type is None:
            changed = True
            continue
        if new_type != old_type:
            item["type"] = new_type
            changed = True
        substeps = item.get("substeps")
        if isinstance(substeps, list):
            for index, substep in enumerate(substeps):
                if isinstance(substep, dict):
                    old_id = str(substep.get("id", ""))
                    new_id = _SUBSTEP_MIGRATIONS.get(old_id, old_id)
                    if new_id != old_id:
                        substep["id"] = new_id
                        changed = True
                elif isinstance(substep, str) and substep in _SUBSTEP_MIGRATIONS:
                    substeps[index] = _SUBSTEP_MIGRATIONS[substep]
                    changed = True
        if item.get("type") == "BucketPoolsCheckStep" and "bucket_overrides" in item:
            item["resolution_buckets"] = item.pop("bucket_overrides")
            changed = True
        migrated_pipeline.append(item)

    if migrated_pipeline != raw_pipeline:
        data["pipeline"] = migrated_pipeline
        changed = True
    return changed
