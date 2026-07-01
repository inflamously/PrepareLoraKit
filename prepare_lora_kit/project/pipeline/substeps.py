"""Ordered substeps within each parent pipeline step, plus selection helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SubstepDefinition:
    """UI/config metadata for an ordered unit within a parent pipeline step."""

    id: str
    label: str
    optional: bool = False
    enabled_by_default: bool = True
    prerequisites: tuple[str, ...] = ()


@dataclass
class PipelineSubstep:
    """Project-level enabled/disabled setting for a substep."""

    id: str
    enabled: bool = True


SUBSTEP_REGISTRY: dict[str, tuple[SubstepDefinition, ...]] = {
    "ImportStep": (
        SubstepDefinition("s0_import", "Import source images"),
    ),
    "QualityGateStep": (
        SubstepDefinition("s1_1_score", "Score images"),
        SubstepDefinition("s1_2_decide", "Review decisions", prerequisites=("s1_1_score",)),
    ),
    "CurateStep": (
        SubstepDefinition("s2_1_dupecheck", "Duplicate check"),
        SubstepDefinition("s2_2_clipscan", "CLIP scan", optional=True),
        SubstepDefinition("s2_3_drop_images", "Drop images", prerequisites=("s2_1_dupecheck",)),
    ),
    "UpscaleStep": (
        SubstepDefinition("s3_1_select_candidates", "Select candidates"),
        SubstepDefinition("s3_2_upscale", "Upscale images", prerequisites=("s3_1_select_candidates",)),
        SubstepDefinition("s3_3_hallucination_check", "Hallucination check", prerequisites=("s3_2_upscale",)),
    ),
    "VaeGateStep": (
        SubstepDefinition("s4_1_reconstruct", "Reconstruct images"),
        SubstepDefinition("s4_2_review", "Review artifacts", prerequisites=("s4_1_reconstruct",)),
        SubstepDefinition("s4_3_apply_decisions", "Apply decisions", prerequisites=("s4_2_review",)),
    ),
    "CaptionStep": (
        SubstepDefinition("s5_1_annotate", "Annotate regions"),
        SubstepDefinition("s5_2_caption", "Caption images"),
        SubstepDefinition("s5_3_validate", "Validate captions", prerequisites=("s5_2_caption",)),
    ),
    "AuditStep": (
        SubstepDefinition("s6_1_pairing", "Pairing"),
        SubstepDefinition("s6_2_corrupt", "Corrupt files"),
        SubstepDefinition("s6_3_caption_quality", "Caption quality"),
        SubstepDefinition("s6_4_resolution", "Resolution"),
    ),
    "ConfigGenStep": (
        SubstepDefinition("s7_1_dataset_stats", "Dataset stats"),
        SubstepDefinition("s7_2_build_config", "Build config", prerequisites=("s7_1_dataset_stats",)),
        SubstepDefinition("s7_3_write_config", "Write config", prerequisites=("s7_2_build_config",)),
    ),
    "BucketDryRunStep": (
        SubstepDefinition("s8_1_assign_buckets", "Assign buckets"),
        SubstepDefinition("s8_2_report_thin_buckets", "Report thin buckets", prerequisites=("s8_1_assign_buckets",)),
        SubstepDefinition("s8_3_cache_info", "Cache info", optional=True, enabled_by_default=False),
    ),
    "ExportStep": (
        SubstepDefinition("s9_1_diff", "Preview export diff"),
        SubstepDefinition("s9_2_export", "Copy to export folder", prerequisites=("s9_1_diff",)),
    ),
}
SUBSTEP_ORDER_INDEX = {
    substep.id: index
    for definitions in SUBSTEP_REGISTRY.values()
    for index, substep in enumerate(definitions)
}
SUBSTEP_PARENT = {
    substep.id: step_type
    for step_type, definitions in SUBSTEP_REGISTRY.items()
    for substep in definitions
}


def substep_aliases() -> dict[str, str]:
    """Return lowercase aliases for substep IDs."""

    return {substep_id.lower(): substep_id for substep_id in SUBSTEP_PARENT}


def default_substeps_for(step_type: str, config: Any | None = None) -> list[PipelineSubstep]:
    """Return default substep selections, honoring legacy config toggles."""

    definitions = SUBSTEP_REGISTRY.get(step_type, ())
    entries = [
        PipelineSubstep(id=definition.id, enabled=definition.enabled_by_default)
        for definition in definitions
    ]
    if config is None:
        return entries

    enabled_by_id = {entry.id: entry.enabled for entry in entries}
    if step_type == "QualityGateStep":
        if getattr(config, "auto_only", False) or not getattr(config, "manual_review", True):
            enabled_by_id["s1_2_decide"] = False
    elif step_type == "CurateStep":
        if getattr(config, "skip_clip", False):
            enabled_by_id["s2_2_clipscan"] = False
    elif step_type == "AuditStep":
        enabled_by_id["s6_1_pairing"] = bool(getattr(config, "check_pairing", True))
        enabled_by_id["s6_2_corrupt"] = bool(getattr(config, "check_corrupt", True))
        enabled_by_id["s6_3_caption_quality"] = bool(getattr(config, "check_caption_length", True))
        enabled_by_id["s6_4_resolution"] = bool(getattr(config, "check_resolution_gate", True))
    elif step_type == "BucketDryRunStep":
        enabled_by_id["s8_3_cache_info"] = bool(getattr(config, "cache_mode", False))

    return [
        PipelineSubstep(id=entry.id, enabled=enabled_by_id.get(entry.id, entry.enabled))
        for entry in entries
    ]


def normalize_substeps(
    step_type: str,
    raw_substeps: list[Any] | None,
    config: Any | None = None,
) -> list[PipelineSubstep]:
    """Validate and normalize project/YAML substep selections for one parent step."""

    defaults = default_substeps_for(step_type, config)
    if raw_substeps is None:
        return defaults

    definitions = SUBSTEP_REGISTRY.get(step_type, ())
    known = {definition.id for definition in definitions}
    by_id = {entry.id: entry.enabled for entry in defaults}
    seen: set[str] = set()

    for raw in raw_substeps:
        if isinstance(raw, str):
            substep_id = raw
            enabled = True
        elif isinstance(raw, dict):
            substep_id = str(raw.get("id", ""))
            enabled = bool(raw.get("enabled", True))
        elif isinstance(raw, PipelineSubstep):
            substep_id = raw.id
            enabled = raw.enabled
        else:
            raise ValueError(f"{step_type}: substep entries must be strings or mappings")

        if substep_id not in known:
            raise ValueError(
                f"{step_type}: unknown substep '{substep_id}'. "
                f"Known: {', '.join(sorted(known))}"
            )
        if substep_id in seen:
            raise ValueError(f"{step_type}: duplicate substep '{substep_id}'")
        seen.add(substep_id)
        by_id[substep_id] = enabled

    return [PipelineSubstep(id=definition.id, enabled=by_id[definition.id]) for definition in definitions]


def enabled_substep_ids(step_type: str, substeps: list[PipelineSubstep]) -> list[str]:
    """Return enabled substep IDs in canonical order for a parent step."""

    known = {definition.id for definition in SUBSTEP_REGISTRY.get(step_type, ())}
    enabled = {substep.id for substep in substeps if substep.enabled and substep.id in known}
    return [definition.id for definition in SUBSTEP_REGISTRY.get(step_type, ()) if definition.id in enabled]


def substep_payloads(step_type: str, substeps: list[PipelineSubstep], state=None) -> list[dict[str, Any]]:
    """Build UI payload entries for a parent step's substeps."""

    selected = {substep.id: substep.enabled for substep in substeps}
    payloads: list[dict[str, Any]] = []
    for definition in SUBSTEP_REGISTRY.get(step_type, ()):
        status = "pending"
        if state is not None:
            status = state.get_substep(step_type, definition.id).get("status", "pending")
        payloads.append({
            "id": definition.id,
            "label": definition.label,
            "enabled": bool(selected.get(definition.id, definition.enabled_by_default)),
            "status": status,
            "prerequisites": list(definition.prerequisites),
            "optional": definition.optional,
        })
    return payloads


__all__ = [
    "SUBSTEP_ORDER_INDEX",
    "SUBSTEP_PARENT",
    "SUBSTEP_REGISTRY",
    "PipelineSubstep",
    "SubstepDefinition",
    "default_substeps_for",
    "enabled_substep_ids",
    "normalize_substeps",
    "substep_aliases",
    "substep_payloads",
]
