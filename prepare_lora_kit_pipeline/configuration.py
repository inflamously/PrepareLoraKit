from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prepare_lora_kit_pipeline.configs import (
    AuditConfig,
    BucketPoolsCheckConfig,
    CaptionBboxConfig,
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
    prerequisites: tuple[str, ...] = field(default_factory=tuple)
    optional: bool = False
    resume_aware: bool = False


# Visual workflow order comes from ``order``. Direct prerequisites are runtime
# validation gates; Export intentionally only requires Import.
STEP_DEFINITIONS: dict[str, StepDefinition] = {
    "ImportStep": StepDefinition(ImportConfig, order=0),
    "QualityGateStep": StepDefinition(
        QualityGateConfig,
        order=1,
        prerequisites=("ImportStep",),
    ),
    "CurateStep": StepDefinition(
        CurateConfig,
        order=2,
        prerequisites=("QualityGateStep",),
    ),
    "UpscaleStep": StepDefinition(
        UpscaleConfig,
        order=3,
        prerequisites=("ImportStep",),
        optional=True,
    ),
    "CaptionBboxStep": StepDefinition(
        CaptionBboxConfig,
        order=4,
        prerequisites=("QualityGateStep", "CurateStep"),
        resume_aware=True,
    ),
    "VaeGateStep": StepDefinition(
        VaeGateConfig,
        order=5,
        prerequisites=("ImportStep",),
        resume_aware=True,
    ),
    "AuditStep": StepDefinition(
        AuditConfig,
        order=6,
        prerequisites=("VaeGateStep",),
    ),
    "BucketPoolsCheckStep": StepDefinition(
        BucketPoolsCheckConfig,
        order=7,
        prerequisites=("AuditStep",),
    ),
    "ExportStep": StepDefinition(
        ExportConfig,
        order=8,
        prerequisites=("ImportStep",),
        optional=True,
    ),
}


def _ordered_step_types() -> tuple[str, ...]:
    orders: dict[int, str] = {}
    for step_type, definition in STEP_DEFINITIONS.items():
        if definition.order in orders:
            raise ValueError(
                f"Duplicate pipeline order {definition.order}: "
                f"{orders[definition.order]} and {step_type}"
            )
        orders[definition.order] = step_type
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


_ORDERED_STEP_TYPES = _ordered_step_types()

__all__ = [
    "StepDefinition",
    "STEP_DEFINITIONS",
    "step_types",
    "step_definition",
    "step_config_class",
    "step_prerequisites",
    "is_optional_step_type",
    "is_resume_aware_step_type",
]
