"""Verifier-side glue between the review's answers and the verdict ledger.

Kept out of :mod:`prepare_lora_kit.utils.verdict_ledger` so the ledger stays a
plain document with no opinion about either step, and out of ``step.py`` so the
"what does a verdict mean once the captions have been written" rules sit in one
readable place.
"""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.utils.verdict_ledger import VERDICTS, VerdictLedger


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
