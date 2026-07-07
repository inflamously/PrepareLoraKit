"""Step 9 — Export finalized dataset to a training folder.

Copies the finalized image + ``.txt`` caption pairs out of the working dataset
into a separate export folder an ai-toolkit / LoRA trainer can point at,
preserving subject subfolders. A diff pre-step previews the changes (added /
modified / orphaned) and requires confirmation before anything is written.

The export is non-destructive: the pristine source input and the working
dataset are never mutated, and target files no longer in the final set
(``orphaned``) are reported but left in place.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ...cancellation import CancelCheck, check_cancel
from ...interaction import CliInteractionProvider
from ...paths import PROJECT_ROOT
from prepare_lora_kit.report import reporter
from .diff import ExportDiff, compute_diff
from .export import export_entries


def _resolve_target(target_dir: str | Path | None, original_dir: Path | None, dataset_dir: Path) -> Path:
    """Resolve the export destination, defaulting to ``<input>_export``."""
    if target_dir:
        target = Path(target_dir).expanduser()
        if not target.is_absolute():
            target = PROJECT_ROOT / target
        return target
    base = Path(original_dir) if original_dir else Path(dataset_dir)
    return base.parent / f"{base.name}_export"


def _entry_payload(entry) -> dict[str, Any]:
    return {
        "rel": entry.rel,
        "image": entry.image_src,
        "caption": entry.caption_src,
        "image_status": entry.image_status,
        "caption_status": entry.caption_status,
    }


def _review_payload(diff: ExportDiff) -> dict[str, Any]:
    return {
        "target_dir": diff.target_dir,
        "added": [_entry_payload(e) for e in diff.added],
        "modified": [_entry_payload(e) for e in diff.modified],
        "orphaned": list(diff.orphaned),
        "counts": diff.counts(),
    }


def _normalize_decision(decision: Any) -> tuple[bool, list[str]]:
    if not isinstance(decision, dict):
        return False, []
    excluded = decision.get("excluded", [])
    excluded_list = [str(x) for x in excluded] if isinstance(excluded, list) else []
    return bool(decision.get("confirmed", False)), excluded_list


def run(
    dataset_dir: Path,
    *,
    original_dir: Path | None = None,
    target_dir: str | None = None,
    output_dir: Path | None = None,
    interaction=None,
    report_path: Path | None = None,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    reporter.step_header("Export finalized dataset")
    enabled = set(enabled_substeps or ["preview_export_diff", "copy_export"])
    dataset_dir = Path(dataset_dir)
    output_dir = Path(output_dir) if output_dir else dataset_dir

    resolved_target = _resolve_target(target_dir, original_dir, dataset_dir)
    check_cancel(cancel_check)
    diff = compute_diff(dataset_dir, resolved_target)
    counts = diff.counts()
    reporter.info(f"Export target: {resolved_target}")
    reporter.info(
        f"Diff — added {counts['added']}, modified {counts['modified']}, "
        f"unchanged {counts['unchanged']}, orphaned {counts['orphaned']}"
    )

    confirmed = True
    excluded: list[str] = []
    if "preview_export_diff" in enabled:
        check_cancel(cancel_check)
        provider = interaction or CliInteractionProvider()
        decision = provider.export_review(_review_payload(diff))
        confirmed, excluded = _normalize_decision(decision)

    copied: list[dict] = []
    exported = False
    if not confirmed:
        reporter.warn("Export cancelled — nothing written.")
    elif "copy_export" in enabled:
        check_cancel(cancel_check)
        copied = export_entries(
            diff.changed,
            resolved_target,
            excluded=excluded,
            cancel_check=cancel_check,
        )
        exported = True
        reporter.ok(f"Exported {len(copied)} file group(s) → {resolved_target}")

    report_data = {
        "target_dir": str(resolved_target),
        "counts": counts,
        "confirmed": confirmed,
        "exported": exported,
        "excluded": excluded,
        "copied": copied,
        "orphaned": list(diff.orphaned),
        "substeps": {
            "preview_export_diff": {"enabled": "preview_export_diff" in enabled},
            "copy_export": {"enabled": "copy_export" in enabled},
        },
    }
    check_cancel(cancel_check)
    reporter.save_report(report_data, report_path or (output_dir / "reports" / "ExportStep_report.json"))
    return report_data
