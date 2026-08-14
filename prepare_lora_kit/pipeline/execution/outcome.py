"""What a finished step's own report says about whether it did any work.

The persisted status stays ``done`` either way — prerequisites and resume read that —
so the distinction is recorded beside it as ``outcome``, which the UI badge reads.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

OUTCOME_COMPLETED = "completed"
OUTCOME_SKIPPED = "skipped"

SKIP_ALREADY_DONE = "already_done"
SKIP_LEGACY_IMPORT = "legacy_import"

_EMPTY_REPORT_REASON = "step wrote an empty report"
_UNSPECIFIED_REASON = "step reported no work"


@dataclass(frozen=True)
class StepOutcome:
    """Whether a step that ran to completion actually did anything."""

    completed: bool
    reason: str = ""

    def state_meta(self) -> dict[str, str]:
        if self.completed:
            return {"outcome": OUTCOME_COMPLETED}
        return {"outcome": OUTCOME_SKIPPED, "outcome_reason": self.reason}


def step_outcome(result: Any) -> StepOutcome:
    """Read a step's return value as the report it just wrote."""

    if not isinstance(result, dict):
        # Nothing report-shaped to read; returning without raising is the only
        # signal there is.
        return StepOutcome(True)
    if not result:
        return StepOutcome(False, _EMPTY_REPORT_REASON)
    skipped = result.get("skipped")
    # Deliberately `is True` and not truthiness: UpscaleStep's ``skipped`` is a
    # list of individual images it passed over, not a verdict on the step.
    if skipped is True:
        return StepOutcome(False, str(result.get("reason") or _UNSPECIFIED_REASON))
    return StepOutcome(True)


def records_a_run(record: dict[str, Any]) -> bool:
    """Whether a run-state record was written by a step that actually executed.

    Only such a record promises a report on disk. Manifests written before
    outcomes were tracked, and the records the app fabricates for a satisfied
    prerequisite (a pre-existing working dataset, the dev fixture), make no such
    promise and must not be judged against one.
    """
    return record.get("outcome") in {OUTCOME_COMPLETED, OUTCOME_SKIPPED}


def describe_skip(step_type: str, reason: str) -> str:
    """One sentence for a step the run did not execute, for logs and console."""

    if reason == SKIP_LEGACY_IMPORT:
        return "ImportStep satisfied by existing working dataset"
    if reason == SKIP_ALREADY_DONE:
        return f"{step_type} already done — skipping (use --force to re-run)"
    return f"{step_type} reported no work: {reason}"


def persist_step_outcome(
        state: Any,
        step_type: str,
        substeps: list[str],
        outcome: StepOutcome,
) -> None:
    """Write one finished step to the run-state manifest: substeps, then parent.

    Shared by the pipeline engine and the standalone ``plk step`` command so a
    step run either way leaves the same record behind.
    """
    for substep_id in substeps:
        if outcome.completed:
            state.mark_substep_done(step_type, substep_id)
        else:
            state.mark_substep_skipped(step_type, substep_id, outcome.reason)
    state.mark_done(
        step_type, {"enabled_substeps": list(substeps), **outcome.state_meta()}
    )


__all__ = [
    "OUTCOME_COMPLETED",
    "OUTCOME_SKIPPED",
    "SKIP_ALREADY_DONE",
    "SKIP_LEGACY_IMPORT",
    "StepOutcome",
    "describe_skip",
    "persist_step_outcome",
    "records_a_run",
    "step_outcome",
]
