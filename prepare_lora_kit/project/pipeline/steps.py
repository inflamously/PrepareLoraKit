"""Canonical project pipeline step order and prerequisites."""
from __future__ import annotations

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
    """Return legacy short aliases.

    Numbered aliases were removed with the named workflow refactor. The helper
    remains for import compatibility with older callers.
    """

    return {}


__all__ = [
    "is_step_satisfied",
    "mark_legacy_import_satisfied",
    "step_aliases",
]
