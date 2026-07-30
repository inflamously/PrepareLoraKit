"""
Step 1 — Source Image Quality Gates + Manual Review

Phase A: automated scoring via pluggable scorer registry.
Phase B: tkinter gallery — all images shown with pass/fail borders, click to
         toggle, hover for per-gate scores + overall quality score.
         Falls back to easygui/terminal one-by-one review when tkinter absent.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.interaction import CliInteractionProvider
from prepare_lora_kit.providers.interaction import InteractionProvider
from prepare_lora_kit.report import reporter, step_report_path
from prepare_lora_kit.steps.quality_gate.scoring import DEFAULTS, SCORER_REGISTRY, _score_image
from prepare_lora_kit.utils import image as img_utils


def run(
    input_dir: Path,
    output_dir: Path,
    thresholds: dict | None = None,
    auto_only: bool = False,
    manual_all: bool = False,
    scorers: list[dict] | None = None,
    report_path: Path | None = None,
    interaction: InteractionProvider | None = None,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    reporter.step_header("Source Image Quality Gates")

    enabled = set(enabled_substeps or ["score_images", "review_decisions"])
    thresholds = {**DEFAULTS, **(thresholds or {})}
    scorers = scorers if scorers is not None else SCORER_REGISTRY
    images = img_utils.iter_images(input_dir)
    if not images:
        reporter.warn(f"No images found in {input_dir}")
        # This report is a per-image map, so "nothing scored" is an empty one.
        # It is still written: a missing file would be indistinguishable from a
        # step that never ran, which is what the step badge reads as.
        reporter.save_report({}, report_path or step_report_path(output_dir, "QualityGateStep"))
        return {}

    # ── Phase A: score everything ───────────────────────────────────────────
    if "score_images" in enabled:
        reporter.info(f"Scoring {len(images)} images …")
        scored, report_data = _score_all(images, thresholds, scorers, cancel_check)
    else:
        reporter.warn("Skipping source scoring substep; keeping images unless review changes them.")
        report_data = {}
        scored = [
            (path, {"scores": {}, "quality": None, "auto_reject": False, "auto_reasons": []})
            for path in images
        ]
    # Images that failed to score are already rejected rows in report_data.
    rejected = len(report_data)

    # ── Phase B: decide ─────────────────────────────────────────────────────
    decisions = _resolve_decisions(
        scored,
        auto_only=auto_only,
        review_enabled="review_decisions" in enabled,
        interaction=interaction,
        cancel_check=cancel_check,
    )
    rows, kept, decided_rejects, flagged = _apply_decisions(scored, decisions, cancel_check)
    report_data.update(rows)
    rejected += decided_rejects

    reporter.summary_counts(kept, rejected, flagged)

    survivors = [path_str for path_str, info in report_data.items() if info.get("kept")]
    check_cancel(cancel_check)
    img_utils.materialize(survivors, input_dir, output_dir)

    report_path = report_path or step_report_path(output_dir, "QualityGateStep")
    check_cancel(cancel_check)
    reporter.save_report(report_data, report_path)
    return report_data


def _score_all(
    images: list[Path],
    thresholds: dict,
    scorers: list[dict],
    cancel_check: CancelCheck | None,
) -> tuple[list[tuple[Path, dict]], dict]:
    """Score every image.

    Returns the successfully scored pairs (those are what the gallery can show)
    and a ready-made reject row for each image that blew up while scoring, so one
    unreadable file costs only itself.
    """
    scored: list[tuple[Path, dict]] = []
    failures: dict = {}
    try:
        def _score_one(path: Path):
            # Decode each image once; share it across all scorers. cv2/skimage
            # release the GIL so blur/noise/jpeg run in parallel across workers
            # (the CLIP watermark forward serializes on its own lock).
            check_cancel(cancel_check)
            try:
                return _score_image(img_utils.ImageData(path), thresholds, scorers)
            except Exception as exc:
                return exc

        # Warm-up: score the first image serially so every lazy import (skimage,
        # transformers) and the one-time CLIP model load happens once on the main
        # thread. Initialising those concurrently across workers races — a worker
        # can observe a half-built lazy module ("cannot import name 'CLIPModel'").
        results = [_score_one(images[0])] if images else []
        if len(images) > 1:
            workers = min(8, os.cpu_count() or 4)
            with ThreadPoolExecutor(max_workers=workers) as ex:
                results.extend(ex.map(_score_one, images[1:]))

        for path, result in zip(images, results, strict=True):
            check_cancel(cancel_check)
            if isinstance(result, Exception):
                reporter.error(f"{path.name}: scoring failed — {result}")
                failures[str(path)] = {
                    "kept": False, "decision": "reject", "reason": str(result),
                    "scores": {}, "quality": 0.0,
                }
                continue
            scored.append((path, result))
    finally:
        # The executor has stopped every scoring worker before cleanup runs.
        img_utils.unload_watermark_model()
    return scored, failures


def _resolve_decisions(
    scored: list[tuple[Path, dict]],
    *,
    auto_only: bool,
    review_enabled: bool,
    interaction: InteractionProvider | None,
    cancel_check: CancelCheck | None,
) -> dict[str, str]:
    """Keep/reject/flag per image — from the gallery, or straight from the gates."""
    if auto_only or not review_enabled:
        return {str(p): ("reject" if i["auto_reject"] else "keep") for p, i in scored}

    check_cancel(cancel_check)
    provider = interaction or CliInteractionProvider()
    decisions = provider.source_review(scored)
    check_cancel(cancel_check)
    return decisions


def _apply_decisions(
    scored: list[tuple[Path, dict]],
    decisions: dict[str, str],
    cancel_check: CancelCheck | None,
) -> tuple[dict, int, int, int]:
    """Fold decisions into report rows, returning them plus (kept, rejected, flagged)."""
    rows: dict = {}
    kept = rejected = flagged = 0
    for path, info in scored:
        check_cancel(cancel_check)
        key = str(path)
        decision = decisions.get(key, "reject" if info["auto_reject"] else "keep")
        kept_bool = decision == "keep"
        flag_bool = decision == "flag"
        rows[key] = {
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
    return rows, kept, rejected, flagged
