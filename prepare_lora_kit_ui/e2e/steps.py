"""Step selection helpers for UI end-to-end mock fixtures."""
from __future__ import annotations

from prepare_lora_kit.pipeline import step_types


def resolve_mock_steps(raw: str) -> list[str]:
    value = raw.strip()
    if not value:
        raise ValueError("Mock step cannot be empty")
    if value.lower() == "all":
        return list(step_types())

    lowered = value.lower()
    for step_type in step_types():
        if step_type.lower() == lowered:
            return [step_type]

    known = ", ".join(["all", *step_types()])
    raise ValueError(f"Unknown mock step '{raw}'. Known: {known}")
