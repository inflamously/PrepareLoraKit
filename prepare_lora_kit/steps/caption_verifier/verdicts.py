"""Verifier-side glue between the review's answers and the verdict ledger.

Kept out of :mod:`prepare_lora_kit.utils.verdict_ledger` so the ledger stays a
plain document with no opinion about either step, and out of ``step.py`` so the
"what does a verdict mean once the captions have been written" rules sit in one
readable place.
"""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.utils.verdict_ledger import VERDICTS, VerdictLedger

# The no-op answer every unjudged item lands on, matching the UI's
# ``normalizeCaptionVerdict`` fallback and the provider's own default.
DEFAULT_VERDICT = "correct"


def seed_initial_verdicts(items: list[dict], ledger: VerdictLedger) -> int:
    """Stamp each item with the verdict the review modal should open on.

    Done here rather than in the UI provider because the provider is handed
    these same dicts and already reads them defensively; the step is the only
    side that knows where the ledger lives.

    A stored verdict is treated as stale — and the item falls back to the
    ``correct`` default — when it has been resolved, or when the caption on disk
    no longer matches the one that was judged. The second check catches an edit
    made outside the app, where re-offering an old "wrong" would point the user
    at a caption that no longer says what they rejected.
    """
    seeded = 0
    for item in items or []:
        entry = ledger.entry_for(item["path"])
        current = str(item.get("caption") or "").strip()
        stale = (
            entry is None
            or entry.resolved
            or entry.caption_at_verdict.strip() != current
        )
        item["initial_verdict"] = DEFAULT_VERDICT if stale else entry.verdict
        if not stale:
            seeded += 1
    return seeded


def record_results(
        ledger: VerdictLedger,
        *,
        items: list[dict],
        results: dict[str, dict],
        applied: list[dict],
) -> int:
    """Persist this run's verdicts, returning how many were recorded.

    Only images the user actually judged are touched, so an image left alone
    this run keeps the verdict, caption and timestamp it earned in an earlier
    one — that merge is the whole reason the ledger exists.

    An image whose caption was **edited in the same review** is recorded
    already-resolved: the user has just fixed it by hand, and leaving it flagged
    would send CaptionBboxStep back to overwrite the text they typed. So
    *flag + edit* self-resolves, while *flag without edit* reopens for the VLM.
    """
    # Both maps are re-keyed on the resolved path. ``results`` keys come back
    # over the bridge already resolved while ``items`` carry the step's own
    # unresolved Paths; matching the two by raw string works today only because
    # the working dir happens to be resolved already.
    results_by_key = {_key(key): value for key, value in (results or {}).items()}
    applied_by_key = {_key(entry["path"]): entry for entry in (applied or [])}

    recorded = 0
    for item in items or []:
        key = _key(item["path"])
        result = results_by_key.get(key)
        if not isinstance(result, dict):
            continue
        verdict = result.get("verdict")
        if verdict not in VERDICTS:
            continue

        edit = applied_by_key.get(key)
        ledger.record(
            item["path"],
            verdict,
            # The caption now on disk — the edited text when one was written,
            # otherwise what the user was looking at when they judged.
            caption=edit["after"] if edit else str(item.get("caption") or ""),
            resolved=edit is not None,
        )
        recorded += 1
    return recorded


def _key(path: Path | str) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:
        return str(path)
