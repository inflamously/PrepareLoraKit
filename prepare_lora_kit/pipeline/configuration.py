from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from prepare_lora_kit.pipeline.configs import (
    AuditConfig,
    BucketPoolsCheckConfig,
    CaptionBboxConfig,
    CaptionVerifierConfig,
    CurateConfig,
    ExportConfig,
    ImportConfig,
    QualityGateConfig,
    UpscaleConfig,
    VaeGateConfig,
)


@dataclass(frozen=True)
class StepDefinition:
    """All static pipeline metadata for one project step type."""

    config_cls: type[Any]
    order: int
    slug: str
    prerequisites: tuple[str, ...] = field(default_factory=tuple)
    optional: bool = False
    resume_aware: bool = False


# Visual workflow order comes from ``order``. Direct prerequisites are runtime
# validation gates; Export intentionally only requires Import.
#
# ``slug`` is the on-disk vocabulary: it names this step's file inside a project
# folder (``caption_bbox`` -> ``caption_bbox.yaml``) and identifies it in
# ``index.yaml``. It is written out explicitly rather than derived from the step
# type because it is a file-format contract — deriving it would mean a Python
# class rename silently renames a file the user's projects already reference,
# which is exactly the breakage the old ``_STEP_MIGRATIONS`` table existed to
# paper over. Everything in memory (RunState keys, report filenames, invoke and
# substep registries, UI payloads) stays on the CamelCase step type.
STEP_DEFINITIONS: dict[str, StepDefinition] = {
    "ImportStep": StepDefinition(ImportConfig, order=0, slug="import"),
    "QualityGateStep": StepDefinition(
        QualityGateConfig,
        order=1,
        slug="quality_gate",
        prerequisites=("ImportStep",),
    ),
    "CurateStep": StepDefinition(
        CurateConfig,
        order=2,
        slug="curate",
        prerequisites=("QualityGateStep",),
    ),
    "UpscaleStep": StepDefinition(
        UpscaleConfig,
        order=3,
        slug="upscale",
        prerequisites=("ImportStep",),
        optional=True,
    ),
    "CaptionBboxStep": StepDefinition(
        CaptionBboxConfig,
        order=4,
        slug="caption_bbox",
        prerequisites=("QualityGateStep", "CurateStep"),
        resume_aware=True,
    ),
    # Optional text-encoder probe: renders each caption with a text-to-image
    # model so the user can tell a term the encoder knows from one it does not.
    # ``resume_aware`` so a plain re-run re-opens the review modal instead of
    # reporting "already done" and forcing the user through ``--force`` (which
    # would invalidate VaeGate/Audit/Buckets/Export for a caption tweak).
    "CaptionVerifierStep": StepDefinition(
        CaptionVerifierConfig,
        order=5,
        slug="caption_verifier",
        prerequisites=("CaptionBboxStep",),
        optional=True,
        resume_aware=True,
    ),
    "VaeGateStep": StepDefinition(
        VaeGateConfig,
        order=6,
        slug="vae_gate",
        prerequisites=("ImportStep",),
        resume_aware=True,
    ),
    "AuditStep": StepDefinition(
        AuditConfig,
        order=7,
        slug="audit",
        prerequisites=("VaeGateStep",),
    ),
    "BucketPoolsCheckStep": StepDefinition(
        BucketPoolsCheckConfig,
        order=8,
        slug="bucket_pools_check",
        prerequisites=("AuditStep",),
    ),
    "ExportStep": StepDefinition(
        ExportConfig,
        order=9,
        slug="export",
        prerequisites=("ImportStep",),
        optional=True,
    ),
}

# A slug becomes a filename, so this is the boundary that keeps one out of
# ``../`` or a drive letter. Checked at import time, below.
_SLUG_PATTERN = re.compile(r"[a-z][a-z0-9_]*")


def _ordered_step_types() -> tuple[str, ...]:
    orders: dict[int, str] = {}
    slugs: dict[str, str] = {}
    for step_type, definition in STEP_DEFINITIONS.items():
        if definition.order in orders:
            raise ValueError(
                f"Duplicate pipeline order {definition.order}: "
                f"{orders[definition.order]} and {step_type}"
            )
        orders[definition.order] = step_type
        if not _SLUG_PATTERN.fullmatch(definition.slug):
            raise ValueError(
                f"{step_type} has an invalid slug {definition.slug!r}: slugs name "
                f"files on disk and must match {_SLUG_PATTERN.pattern}"
            )
        if definition.slug in slugs:
            raise ValueError(
                f"Duplicate step slug '{definition.slug}': "
                f"{slugs[definition.slug]} and {step_type} would share a file"
            )
        slugs[definition.slug] = step_type
        unknown_prerequisites = [
            prerequisite
            for prerequisite in definition.prerequisites
            if prerequisite not in STEP_DEFINITIONS
        ]
        if unknown_prerequisites:
            raise ValueError(
                f"{step_type} has unknown prerequisite(s): "
                f"{', '.join(unknown_prerequisites)}"
            )
    return tuple(
        step_type
        for step_type, definition in sorted(
            STEP_DEFINITIONS.items(),
            key=lambda item: item[1].order,
        )
    )


def step_types() -> tuple[str, ...]:
    """Return known step types in visual workflow order."""

    return _ORDERED_STEP_TYPES


def step_definition(step_type: str) -> StepDefinition | None:
    """Return the static definition for a step type, if it exists."""

    return STEP_DEFINITIONS.get(step_type)


def step_config_class(step_type: str) -> type[Any] | None:
    """Return the config dataclass for a step type, if it exists."""

    definition = step_definition(step_type)
    return definition.config_cls if definition is not None else None


def step_prerequisites(step_type: str) -> tuple[str, ...]:
    """Return direct prerequisites for a step type."""

    definition = step_definition(step_type)
    return definition.prerequisites if definition is not None else ()


def is_optional_step_type(step_type: str) -> bool:
    """Return whether a step is excluded from default UI completion checks."""

    definition = step_definition(step_type)
    return bool(definition and definition.optional)


def is_resume_aware_step_type(step_type: str) -> bool:
    """Return whether a step should re-enter run() on plain re-runs."""

    definition = step_definition(step_type)
    return bool(definition and definition.resume_aware)


def step_slug(step_type: str) -> str | None:
    """Return the on-disk slug for a step type, if it exists."""

    definition = step_definition(step_type)
    return definition.slug if definition is not None else None


def step_type_for_slug(slug: str) -> str | None:
    """Return the step type an on-disk slug names, if it exists."""

    return _SLUG_TO_TYPE.get(slug)


def step_slugs() -> tuple[str, ...]:
    """Return known step slugs in visual workflow order."""

    return _ORDERED_STEP_SLUGS


_ORDERED_STEP_TYPES = _ordered_step_types()
_ORDERED_STEP_SLUGS = tuple(
    STEP_DEFINITIONS[step_type].slug for step_type in _ORDERED_STEP_TYPES
)
_SLUG_TO_TYPE = {
    definition.slug: step_type for step_type, definition in STEP_DEFINITIONS.items()
}

__all__ = [
    "STEP_DEFINITIONS",
    "StepDefinition",
    "is_optional_step_type",
    "is_resume_aware_step_type",
    "step_config_class",
    "step_definition",
    "step_prerequisites",
    "step_slug",
    "step_slugs",
    "step_type_for_slug",
    "step_types",
]
