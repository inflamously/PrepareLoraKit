"""CaptionVerifierStep — probe what a text encoder makes of each caption.

``run()`` never raises except :class:`CancelledRun`; every other failure becomes a
report with a reason (the VaeGateStep contract).
"""
from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from prepare_lora_kit.cancellation import CancelCheck, CancelledRun, check_cancel
from prepare_lora_kit.project.pipeline.substeps import substep_ids_for
from prepare_lora_kit.providers.interaction import InteractionProvider
from prepare_lora_kit.report import reporter
from prepare_lora_kit.steps.caption_verifier import captions as caption_io
from prepare_lora_kit.steps.caption_verifier import reports, verdicts
from prepare_lora_kit.steps.caption_verifier.generation import make_caption_generator
from prepare_lora_kit.steps.caption_verifier.t2i import T2IRuntime
from prepare_lora_kit.utils.verdict_ledger import VerdictLedger

STEP_TYPE = "CaptionVerifierStep"
PREVIEW_DIR_NAME = "CaptionVerifierStep_previews"
BACKUP_DIR_NAME = "captions_before"


def run(
    dataset_dir: Path,
    *,
    output_dir: Path | None = None,
    t2i_model_id: str = "auto",
    quantization: str = "auto",
    dtype: str = "bfloat16",
    offload: str = "auto",
    width: int | None = None,
    height: int | None = None,
    num_inference_steps: int | None = None,
    guidance_scale: float | None = None,
    seed: int = 42,
    negative_prompt: str | None = None,
    max_images: int | None = None,
    keep_previews: bool = True,
    report_path: Path | None = None,
    interaction: InteractionProvider | None = None,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
    status_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict:
    reporter.step_header("Caption Verifier — Text-Encoder Probe")

    dataset_dir = Path(dataset_dir)
    output_dir = Path(output_dir) if output_dir else dataset_dir
    enabled = set(enabled_substeps or substep_ids_for(STEP_TYPE))
    target_report = Path(report_path) if report_path else reports.report_path_for(output_dir)
    preview_root = target_report.parent / PREVIEW_DIR_NAME

    defaults = {
        "width": width,
        "height": height,
        "steps": num_inference_steps,
        "guidance": guidance_scale,
        "seed": seed,
        "negative_prompt": negative_prompt,
        "max_images": max_images,
        "keep_previews": keep_previews,
    }

    def _skip(reason: str, *, items=None, failures=None, model=None) -> dict:
        report = reports.build_skipped_report(
            reason, items=items, failures=failures, model=model,
            defaults=defaults, enabled_substeps=enabled,
        )
        reporter.warn(f"Caption verifier skipped: {reason}")
        reporter.save_report(report, target_report)
        return report

    if "verify_captions" not in enabled:
        return _skip("verify_captions substep disabled")

    items = caption_io.collect_verifiable_images(dataset_dir, max_images=max_images)
    if not items:
        return _skip("no captioned images")

    # Re-entering the step should remember what was already judged; the step is
    # the only side that knows where the ledger lives, so it stamps the items
    # the provider is about to turn into modal payloads.
    verdicts.seed_initial_verdicts(items, VerdictLedger(target_report.parent))

    # Previews are diagnostics, regenerated on demand — wipe stale ones so a
    # re-run never shows a render of a caption that has since been edited.
    shutil.rmtree(preview_root, ignore_errors=True)

    verify = getattr(interaction, "caption_verify", None) if interaction else None
    if verify is None:
        # The normal CLI path: pipeline.run passes no interaction provider.
        return _skip("no interactive caption verification provider", items=items)

    check_cancel(cancel_check)

    runtime = T2IRuntime(
        model_id=t2i_model_id,
        quantization=quantization,
        dtype=dtype,
        offload=offload,
        width=width,
        height=height,
        steps=num_inference_steps,
        guidance=guidance_scale,
        negative_prompt=negative_prompt,
        status_callback=status_callback,
    )

    generations: dict[str, list[dict]] = {}
    failures: list[dict] = []
    generator = make_caption_generator(
        runtime=runtime,
        preview_root=preview_root,
        generations=generations,
        failures=failures,
        base_seed=seed,
        cancel_check=cancel_check,
    )

    settings = {
        "model_id": t2i_model_id,
        "width": width,
        "height": height,
        "steps": num_inference_steps,
        "guidance": guidance_scale,
        "seed": seed,
        "negative_prompt": negative_prompt,
        "verdicts": list(reports.VERDICTS),
    }

    results, reason = _run_review(
        verify,
        items,
        generator=generator,
        preview_root=preview_root,
        settings=settings,
        runtime=runtime,
        failures=failures,
    )

    applied: list[dict] = []
    rejected: list[dict] = []
    if results and "apply_caption_edits" in enabled:
        applied, rejected = _apply_caption_edits(dataset_dir, results, preview_root)

    # After the edits so a hand-fixed caption is recorded as already resolved,
    # and beside the report rather than in it: the report is rebuilt from
    # scratch every run, so it cannot carry a verdict forward.
    if results:
        ledger = VerdictLedger(target_report.parent)
        verdicts.record_results(
            ledger, items=items, results=results, applied=applied,
        )
        ledger.save()

    if not keep_previews:
        _discard_previews(preview_root, generations)

    report = reports.build_report(
        items=items,
        results=results,
        generations=generations,
        applied=applied,
        rejected=rejected,
        failures=failures,
        model=runtime.metadata,
        status=runtime.status,
        defaults=defaults,
        enabled_substeps=enabled,
        reason=reason,
    )

    stats = report["statistics"]
    reporter.summary_counts(
        kept=stats["correct"], rejected=stats["wrong"], flagged=stats["generic"],
    )
    reporter.save_report(report, target_report)
    return report


def _run_review(
    verify,
    items,
    *,
    generator,
    preview_root: Path,
    settings: dict,
    runtime,
    failures: list[dict],
) -> tuple[dict[str, dict], str | None]:
    """Drive the interactive review, always unloading the runtime afterwards.

    A failure inside the review is recorded and returned as a reason rather than
    raised: renders and verdicts collected before the failure are still worth
    reporting. Cancellation is not a failure and propagates untouched.
    """
    try:
        results = verify(
            items, generator=generator, preview_dir=preview_root, settings=settings,
        ) or {}
    except CancelledRun:
        # Must precede the broad handler; a cancel is not a step failure.
        raise
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        reporter.error(f"Caption verification failed: {reason}")
        failures.append({"stage": "review", "path": None, "error": reason})
        return {}, reason
    finally:
        runtime.unload()
    return results, None


def _apply_caption_edits(
    dataset_dir: Path,
    results: dict[str, dict],
    preview_root: Path,
) -> tuple[list[dict], list[dict]]:
    """Write back the captions the reviewer edited, reporting any refused."""
    edits = {
        path: entry.get("caption", "")
        for path, entry in results.items()
        if isinstance(entry, dict) and entry.get("caption") is not None
    }
    applied, rejected = caption_io.apply_caption_edits(
        dataset_dir, edits, backup_dir=preview_root / BACKUP_DIR_NAME,
    )
    if applied:
        reporter.ok(f"Wrote {len(applied)} edited caption(s).")
    for entry in rejected:
        reporter.warn(
            f"Caption not written ({entry['reason']}): {Path(entry['path']).name}"
        )
    return applied, rejected


def _discard_previews(preview_root: Path, generations: dict[str, list[dict]]) -> None:
    """Drop the rendered probes and unlink them from the report.

    Runs before the report is built so it can never cite a deleted file.
    """
    _prune_previews(preview_root)
    for entries in generations.values():
        for entry in entries:
            entry["path"] = None


def _prune_previews(preview_root: Path) -> None:
    """Drop rendered probes but keep the caption backups — those are recovery data."""
    if not preview_root.exists():
        return
    for child in preview_root.iterdir():
        if child.name == BACKUP_DIR_NAME:
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
