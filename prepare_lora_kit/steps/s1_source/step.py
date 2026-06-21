"""
Step 1 — Source Image Quality Gates + Manual Review

Phase A: automated scoring via pluggable scorer registry.
Phase B: tkinter gallery — all images shown with pass/fail borders, click to
         toggle, hover for per-gate scores + overall quality score.
         Falls back to easygui/terminal one-by-one review when tkinter absent.
"""
from __future__ import annotations
from pathlib import Path

from ...interaction import CliInteractionProvider, InteractionProvider
from ...utils import image as img_utils
from ...utils import report as rpt
from .scoring import DEFAULTS, SCORER_REGISTRY, _score_image


def run(
    input_dir: Path,
    output_dir: Path,
    thresholds: dict | None = None,
    auto_only: bool = False,
    manual_all: bool = False,
    scorers: list[dict] | None = None,
    report_path: Path | None = None,
    interaction: InteractionProvider | None = None,
) -> dict:
    """
    Run Step 1.

    Returns report dict: {path_str: {kept, decision, scores, reasons}}.
    Writes report to report_path (default output_dir/step1_report.json).

    Pass `scorers` to override SCORER_REGISTRY with custom quality checks.
    Each scorer: {"name", "fn", "threshold_key", "op", "optional", "borderline_key"}.
    """
    rpt.step_header(1, "Source Image Quality Gates")

    thresholds = {**DEFAULTS, **(thresholds or {})}
    scorers = scorers if scorers is not None else SCORER_REGISTRY
    images = img_utils.iter_images(input_dir)
    if not images:
        rpt.warn(f"No images found in {input_dir}")
        return {}

    rpt.info(f"Scoring {len(images)} images …")

    report: dict = {}
    kept = rejected = flagged = 0
    scored: list[tuple[Path, dict]] = []   # successfully scored → eligible for gallery

    # ── Phase A: score everything ───────────────────────────────────────────
    for path in images:
        key = str(path)
        try:
            info = _score_image(path, thresholds, scorers)
        except Exception as exc:
            rpt.error(f"{path.name}: scoring failed — {exc}")
            report[key] = {"kept": False, "decision": "reject", "reason": str(exc),
                           "scores": {}, "quality": 0.0}
            rejected += 1
            continue
        scored.append((path, info))

    # ── Phase B: decide ─────────────────────────────────────────────────────
    if auto_only:
        decisions = {str(p): ("reject" if i["auto_reject"] else "keep") for p, i in scored}
    else:
        provider = interaction or CliInteractionProvider()
        decisions = provider.source_review(scored)

    for path, info in scored:
        key = str(path)
        decision = decisions.get(key, "reject" if info["auto_reject"] else "keep")
        kept_bool = decision == "keep"
        flag_bool = decision == "flag"
        report[key] = {
            "kept": kept_bool or flag_bool,
            "decision": decision,
            "reason": "; ".join(info["auto_reasons"]) if info["auto_reasons"] else None,
            "scores": info["scores"],
            "quality": info["quality"],
        }
        if kept_bool:
            kept += 1
        elif flag_bool:
            flagged += 1
        else:
            rejected += 1

    rpt.summary_counts(kept, rejected, flagged)

    survivors = [path_str for path_str, info in report.items() if info.get("kept")]
    img_utils.materialize(survivors, input_dir, output_dir)

    report_path = report_path or (output_dir / "step1_report.json")
    rpt.save_report(report, report_path)
    return report
