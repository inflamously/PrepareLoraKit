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
from prepare_lora_kit.utils import image as img_utils
from prepare_lora_kit.report import reporter

from prepare_lora_kit.steps.quality_gate.scoring import DEFAULTS, SCORER_REGISTRY, _score_image

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
        return {}

    if "score_images" in enabled:
        reporter.info(f"Scoring {len(images)} images …")

    report_data: dict = {}
    kept = rejected = flagged = 0
    scored: list[tuple[Path, dict]] = []   # successfully scored → eligible for gallery

    # ── Phase A: score everything ───────────────────────────────────────────
    if "score_images" in enabled:
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

        for path, result in zip(images, results):
            check_cancel(cancel_check)
            key = str(path)
            if isinstance(result, Exception):
                reporter.error(f"{path.name}: scoring failed — {result}")
                report_data[key] = {"kept": False, "decision": "reject", "reason": str(result),
                                    "scores": {}, "quality": 0.0}
                rejected += 1
                continue
            scored.append((path, result))
    else:
        reporter.warn("Skipping source scoring substep; keeping images unless review changes them.")
        scored = [
            (path, {"scores": {}, "quality": None, "auto_reject": False, "auto_reasons": []})
            for path in images
        ]

    # ── Phase B: decide ─────────────────────────────────────────────────────
    if auto_only or "review_decisions" not in enabled:
        decisions = {str(p): ("reject" if i["auto_reject"] else "keep") for p, i in scored}
    else:
        check_cancel(cancel_check)
        provider = interaction or CliInteractionProvider()
        decisions = provider.source_review(scored)
        check_cancel(cancel_check)

    for path, info in scored:
        check_cancel(cancel_check)
        key = str(path)
        decision = decisions.get(key, "reject" if info["auto_reject"] else "keep")
        kept_bool = decision == "keep"
        flag_bool = decision == "flag"
        report_data[key] = {
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

    reporter.summary_counts(kept, rejected, flagged)

    survivors = [path_str for path_str, info in report_data.items() if info.get("kept")]
    check_cancel(cancel_check)
    img_utils.materialize(survivors, input_dir, output_dir)

    report_path = report_path or (output_dir / "step1_report.json")
    check_cancel(cancel_check)
    reporter.save_report(report_data, report_path)
    return report_data
