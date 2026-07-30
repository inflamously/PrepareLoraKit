"""Report construction for CaptionVerifierStep.

Every branch — success, partial, skipped — emits the **same top-level key set**
so the UI report renderer never needs ``.get()`` guards. A test enforces it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from prepare_lora_kit.project.pipeline.substeps import substep_ids_for

_REPORT_NAME = "CaptionVerifierStep_report.json"
STEP_TYPE = "CaptionVerifierStep"
VERDICTS = ("correct", "generic", "wrong")

_EMPTY_MODEL = {
    "model_id": None,
    "family": None,
    "pipeline_cls": None,
    "quantization": None,
    "dtype": None,
    "offload": None,
    "device": None,
    "quantize_components": [],
    "loaded": False,
}


def report_path_for(output_dir: Path) -> Path:
    return Path(output_dir) / _REPORT_NAME


def build_report(
    *,
    items: list[dict],
    results: dict[str, dict],
    generations: dict[str, list[dict]],
    applied: list[dict],
    rejected: list[dict],
    failures: list[dict],
    model: dict | None,
    status: dict | None,
    defaults: dict | None,
    enabled_substeps: set[str] | None = None,
    reason: str | None = None,
) -> dict:
    """Assemble the full report.

    Unreviewed images still appear with ``verdict: null`` so the report is a
    complete census of the dataset, matching how VaeGateStep reports every
    review item.
    """
    applied_by_path = {entry["path"]: entry for entry in applied}
    rejected_by_path = {entry["path"]: entry for entry in rejected}

    report_items: list[dict] = []
    counts = dict.fromkeys(VERDICTS, 0)
    for item in items:
        key = str(item["path"])
        result = results.get(key) or {}
        verdict = result.get("verdict")
        verdict = verdict if verdict in VERDICTS else None
        if verdict:
            counts[verdict] += 1

        before = str(item.get("caption") or "")
        after = str(result.get("caption") or before)
        written = key in applied_by_path
        report_items.append({
            "path": key,
            "name": item.get("name") or Path(key).name,
            "verdict": verdict,
            "caption_before": before,
            "caption_after": after,
            "caption_changed": after.strip() != before.strip(),
            "caption_written": written,
            "caption_rejected_reason": rejected_by_path.get(key, {}).get("reason"),
            "generations": list(generations.get(key, [])),
        })

    generated = sum(len(entries) for entries in generations.values())
    verified = sum(1 for entry in report_items if entry["verdict"] is not None)
    # "Skipped" means the step produced nothing at all — a partial run with some
    # renders or verdicts is a success that carries failures.
    skipped = bool(reason) and generated == 0 and verified == 0

    return {
        "skipped": skipped,
        "reason": reason,
        "model": {**_EMPTY_MODEL, **(model or {})},
        "status": dict(status or {}),
        "defaults": dict(defaults or {}),
        "statistics": {
            "images": len(report_items),
            "verified": verified,
            "unverified": len(report_items) - verified,
            "generated": generated,
            "correct": counts["correct"],
            "generic": counts["generic"],
            "wrong": counts["wrong"],
            "captions_edited": len(applied),
            "captions_rejected": len(rejected),
            "generation_failures": len(failures),
        },
        "verdict_counts": dict(counts),
        "items": report_items,
        "failures": list(failures),
        "substeps": substep_report(enabled_substeps),
    }


def build_skipped_report(
    reason: str,
    *,
    items: list[dict] | None = None,
    failures: list[dict] | None = None,
    model: dict | None = None,
    defaults: dict | None = None,
    enabled_substeps: set[str] | None = None,
) -> dict:
    """A no-work report with the same shape as a successful one."""
    report = build_report(
        items=list(items or []),
        results={},
        generations={},
        applied=[],
        rejected=[],
        failures=list(failures or []),
        model=model,
        status={},
        defaults=defaults,
        enabled_substeps=enabled_substeps,
        reason=reason,
    )
    report["skipped"] = True
    return report


def substep_report(enabled_substeps: set[str] | None) -> dict[str, Any]:
    enabled = set(enabled_substeps or substep_ids_for(STEP_TYPE))
    return {
        substep_id: {"enabled": substep_id in enabled}
        for substep_id in substep_ids_for(STEP_TYPE)
    }
