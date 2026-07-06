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
        SubstepDefinition("import_images", "Import source images"),
    ),
    "QualityGateStep": (
        SubstepDefinition("score_images", "Score images"),
        SubstepDefinition("review_decisions", "Review decisions", prerequisites=("score_images",)),
    ),
    "CurateStep": (
        SubstepDefinition("duplicate_check", "Duplicate check"),
        SubstepDefinition("clip_scan", "CLIP scan", optional=True),
        SubstepDefinition("drop_images", "Drop images", prerequisites=("duplicate_check",)),
    ),
    "UpscaleStep": (
        SubstepDefinition("select_upscale_candidates", "Select candidates"),
        SubstepDefinition("upscale_images", "Upscale images", prerequisites=("select_upscale_candidates",)),
        SubstepDefinition("hallucination_check", "Hallucination check", prerequisites=("upscale_images",)),
    ),
    "CaptionBboxStep": (
        SubstepDefinition("annotate_regions", "Annotate regions"),
        SubstepDefinition("caption_images", "Caption images"),
        SubstepDefinition("validate_captions", "Validate captions", prerequisites=("caption_images",)),
    ),
    "VaeGateStep": (
        SubstepDefinition("reconstruct_images", "Reconstruct images"),
        SubstepDefinition("review_vae_artifacts", "Review artifacts", prerequisites=("reconstruct_images",)),
        SubstepDefinition("apply_vae_decisions", "Apply decisions", prerequisites=("review_vae_artifacts",)),
    ),
    "AuditStep": (
        SubstepDefinition("check_pairing", "Pairing"),
        SubstepDefinition("check_corrupt_files", "Corrupt files"),
        SubstepDefinition("check_caption_quality", "Caption quality"),
        SubstepDefinition("check_resolution", "Resolution"),
    ),
    "BucketPoolsCheckStep": (
        SubstepDefinition("assign_bucket_pools", "Assign buckets"),
        SubstepDefinition("report_thin_buckets", "Report thin buckets", prerequisites=("assign_bucket_pools",)),
        SubstepDefinition("write_cache_info", "Cache info", optional=True, enabled_by_default=False),
    ),
    "ExportStep": (
        SubstepDefinition("preview_export_diff", "Preview export diff"),
        SubstepDefinition("copy_export", "Copy to export folder", prerequisites=("preview_export_diff",)),
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
            enabled_by_id["review_decisions"] = False
    elif step_type == "CurateStep":
        if getattr(config, "skip_clip", False):
            enabled_by_id["clip_scan"] = False
    elif step_type == "AuditStep":
        enabled_by_id["check_pairing"] = bool(getattr(config, "check_pairing", True))
        enabled_by_id["check_corrupt_files"] = bool(getattr(config, "check_corrupt", True))
        enabled_by_id["check_caption_quality"] = bool(getattr(config, "check_caption_length", True))
        enabled_by_id["check_resolution"] = bool(getattr(config, "check_resolution_gate", True))
    elif step_type == "BucketPoolsCheckStep":
        enabled_by_id["write_cache_info"] = bool(getattr(config, "cache_mode", False))

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
