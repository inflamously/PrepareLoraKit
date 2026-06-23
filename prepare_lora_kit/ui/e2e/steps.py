"""Step selection helpers for UI end-to-end mock fixtures."""
from __future__ import annotations

from ...project.base import STEP_TYPE_MAP
from ...project.steps import step_aliases


_STEP_ALIASES = step_aliases()


def resolve_mock_steps(raw: str) -> list[str]:
    value = raw.strip()
    if not value:
        raise ValueError("Mock step cannot be empty")
    if value.lower() == "all":
        return list(STEP_TYPE_MAP)

    lowered = value.lower()
    if lowered in _STEP_ALIASES:
        return [_STEP_ALIASES[lowered]]
    for step_type in STEP_TYPE_MAP:
        if step_type.lower() == lowered:
            return [step_type]

    known = ", ".join(
        ["all", *STEP_TYPE_MAP, *sorted(_STEP_ALIASES)]
    )
    raise ValueError(f"Unknown mock step '{raw}'. Known: {known}")
