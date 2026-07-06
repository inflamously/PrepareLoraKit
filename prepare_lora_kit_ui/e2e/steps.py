"""Step selection helpers for UI end-to-end mock fixtures."""
from __future__ import annotations

from prepare_lora_kit_pipeline.configuration import STEP_TYPE_MAP


def resolve_mock_steps(raw: str) -> list[str]:
    value = raw.strip()
    if not value:
        raise ValueError("Mock step cannot be empty")
    if value.lower() == "all":
        return list(STEP_TYPE_MAP)

    lowered = value.lower()
    for step_type in STEP_TYPE_MAP:
        if step_type.lower() == lowered:
            return [step_type]

    known = ", ".join(["all", *STEP_TYPE_MAP])
    raise ValueError(f"Unknown mock step '{raw}'. Known: {known}")
