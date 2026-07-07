"""Compatibility re-export of the pipeline step/substep definitions.

The canonical definitions now live in the :mod:`prepare_lora_kit.project.pipeline`
package (``pipeline/steps.py`` and ``pipeline/substeps.py``). This module is kept
as a thin shim so existing ``from .steps import ...`` import paths stay stable.
"""
from __future__ import annotations

from prepare_lora_kit.project.pipeline import (  # noqa: F401
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
    step_aliases,
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
    "step_aliases",
    "substep_aliases",
    "substep_payloads",
]
