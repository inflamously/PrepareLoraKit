"""Canonical project pipeline step order and prerequisites."""
from __future__ import annotations

from ..configs import (
    AuditConfig,
    BucketDryRunConfig,
    CaptionConfig,
    ConfigGenConfig,
    CurateConfig,
    ImportConfig,
    QualityGateConfig,
    UpscaleConfig,
    VaeGateConfig,
)


STEP_TYPE_MAP: dict[str, type] = {
    "ImportStep": ImportConfig,
    "QualityGateStep": QualityGateConfig,
    "CurateStep": CurateConfig,
    "UpscaleStep": UpscaleConfig,
    "CaptionStep": CaptionConfig,
    "VaeGateStep": VaeGateConfig,
    "AuditStep": AuditConfig,
    "ConfigGenStep": ConfigGenConfig,
    "BucketDryRunStep": BucketDryRunConfig,
}

# Defines the order steps are ran in the pipeline down
STEP_ORDER = tuple(STEP_TYPE_MAP)
OPTIONAL_STEP_TYPES = {"UpscaleStep"}
STEP_PREREQUISITES: dict[str, list[str]] = {
    "QualityGateStep": ["ImportStep"],
    "CurateStep": ["QualityGateStep"],
    "UpscaleStep": ["CurateStep"],
    "CaptionStep": ["CurateStep"],
    "VaeGateStep": ["CaptionStep"],
    "AuditStep": ["CaptionStep"],
    "ConfigGenStep": ["AuditStep"],
    "BucketDryRunStep": ["ConfigGenStep"],
}
STEP_ORDER_INDEX = {step_type: index for index, step_type in enumerate(STEP_ORDER)}


def is_step_satisfied(step_type: str, state, output_dir) -> bool:
    """Return whether a prerequisite is complete, including legacy import state."""

    if state.is_done(step_type):
        return True
    return step_type == "ImportStep" and (output_dir / "dataset").exists()


def mark_legacy_import_satisfied(state, output_dir) -> bool:
    """Mark ImportStep done when an existing working dataset predates ImportStep."""

    if state.is_done("ImportStep") or not (output_dir / "dataset").exists():
        return False
    state.mark_done("ImportStep", {"legacy_working_dataset": True})
    return True


def step_aliases() -> dict[str, str]:
    """Return CLI/UI aliases while preserving s1..s8 meanings."""

    aliases = {"0": "ImportStep", "s0": "ImportStep"}
    for index, step_type in enumerate(STEP_ORDER[1:], start=1):
        aliases[str(index)] = step_type
        aliases[f"s{index}"] = step_type
    return aliases


__all__ = [
    "OPTIONAL_STEP_TYPES",
    "STEP_ORDER",
    "STEP_ORDER_INDEX",
    "STEP_PREREQUISITES",
    "STEP_TYPE_MAP",
    "is_step_satisfied",
    "mark_legacy_import_satisfied",
    "step_aliases",
]
