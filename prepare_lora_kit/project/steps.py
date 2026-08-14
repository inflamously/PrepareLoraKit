"""Compatibility re-export of the step/substep definitions now in
:mod:`prepare_lora_kit.project.pipeline`.
"""
from __future__ import annotations

from prepare_lora_kit.project.pipeline import (
    SUBSTEP_ORDER_INDEX,
    SUBSTEP_PARENT,
    SUBSTEP_REGISTRY,
    PipelineSubstep,
    SubstepDefinition,
    default_substeps_for,
    enabled_substep_ids,
    is_step_satisfied,
    mark_legacy_import_satisfied,
    normalize_substeps,
    substep_aliases,
    substep_payloads,
)

__all__ = [
    "SUBSTEP_ORDER_INDEX",
    "SUBSTEP_PARENT",
    "SUBSTEP_REGISTRY",
    "PipelineSubstep",
    "SubstepDefinition",
    "default_substeps_for",
    "enabled_substep_ids",
    "is_step_satisfied",
    "mark_legacy_import_satisfied",
    "normalize_substeps",
    "substep_aliases",
    "substep_payloads",
]
