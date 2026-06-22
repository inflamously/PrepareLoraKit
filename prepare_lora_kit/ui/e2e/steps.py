"""Step selection helpers for UI end-to-end mock fixtures."""
from __future__ import annotations

from ...project.base import STEP_TYPE_MAP


_STEP_ALIASES: dict[str, str] = {}
for _index, _step_type in enumerate(STEP_TYPE_MAP, start=1):
    _STEP_ALIASES[str(_index)] = _step_type
    _STEP_ALIASES[f"s{_index}"] = _step_type


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
        ["all", *STEP_TYPE_MAP, *[f"s{i}" for i in range(1, len(STEP_TYPE_MAP) + 1)]]
    )
    raise ValueError(f"Unknown mock step '{raw}'. Known: {known}")
