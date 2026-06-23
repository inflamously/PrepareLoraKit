"""
Step 3 — Upscale (optional)

Selectively upscales images below the target min-side.
The project config selects the upscaler. Missing configured upscalers skip with
a warning instead of silently falling back to another algorithm.
Re-runs Step 1 quality checks post-upscale to reject hallucinated-texture outputs.
"""
from __future__ import annotations

import os
import shutil
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ...cancellation import CancelCheck, CancelledRun, check_cancel
from ...utils import image as img_utils
from ...utils import report as rpt
from .hallucination import HALLUCINATION_SSIM_THRESHOLD, _hallucination_check
from .seedvr2_adapter import (
    DEFAULT_SEEDVR2_DIT_MODEL,
    SeedVR2Unavailable,
    SeedVR2Upscaler,
)
from .upscalers import UPSCALE_TARGET, _lanczos_upscale

Upscaler = Callable[[Path, Path], Path | None]


@dataclass
class OutputContext:
    output_dir: Path
    report_path: Path
    in_place: bool


@dataclass
class ImagePartitions:
    images: list[Path]
    candidates: list[Path]
    already_large: list[Path]


def run(
    dataset_dir: Path,
    output_dir: Path | None = None,
    upscale_target: int = UPSCALE_TARGET,
    upscaler: Upscaler | None = None,
    upscale_model: str = "seedvr2",
    hallucination_ssim_threshold: float = HALLUCINATION_SSIM_THRESHOLD,
    use_seedvr: bool | None = None,
    report_path: Path | None = None,
    seedvr2_submodule_dir: str | None = None,
    seedvr2_model_dir: str | None = None,
    seedvr2_dit_model: str = DEFAULT_SEEDVR2_DIT_MODEL,
    seedvr2_cuda_device: str | None = None,
    seedvr2_batch_size: int = 1,
    seedvr2_vae_tiled: bool = True,
    seedvr2_cache_models: bool = True,
    seedvr2_model_residency: str = "auto",
    seedvr2_debug: bool = False,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    rpt.step_header(3, "Upscale (optional)")
    check_cancel(cancel_check)
    enabled = set(enabled_substeps or [
        "s3_1_select_candidates",
        "s3_2_upscale",
        "s3_3_hallucination_check",
    ])
    upscale_model = _normalize_upscale_model(upscale_model, use_seedvr)
    context = _prepare_output_context(dataset_dir, output_dir, report_path)
    partitions = (
        _partition_images(dataset_dir, upscale_target)
        if "s3_1_select_candidates" in enabled
        else ImagePartitions(img_utils.iter_images(dataset_dir), [], img_utils.iter_images(dataset_dir))
    )
    results: dict = {"upscaled": [], "rejected_post": [], "skipped": []}
    results["substeps"] = {
        "s3_1_select_candidates": {"enabled": "s3_1_select_candidates" in enabled},
        "s3_2_upscale": {"enabled": "s3_2_upscale" in enabled},
        "s3_3_hallucination_check": {"enabled": "s3_3_hallucination_check" in enabled},
    }

    for path in partitions.already_large:
        check_cancel(cancel_check)
        _pass_through(context, path)

    if "s3_2_upscale" not in enabled:
        rpt.info("Upscale substep disabled; passing through originals.")
        results["skipped"] = [
            {"path": str(p), "reason": "s3_2_upscale disabled"}
            for p in partitions.candidates
        ]
        for path in partitions.candidates:
            check_cancel(cancel_check)
            _pass_through(context, path)
        return _save_report(results, context)

    if not partitions.candidates:
        rpt.ok(f"All images already >= {upscale_target}px - skipping upscale.")
        results["skipped"] = [str(p) for p in partitions.images]
        return _save_report(results, context)

    rpt.info(f"{len(partitions.candidates)} images below {upscale_target}px min-side will be upscaled.")
    check_cancel(cancel_check)
    resolved, skip_reason = _resolve_upscaler(
        upscale_model=upscale_model,
        upscaler=upscaler,
        upscale_target=upscale_target,
        seedvr2_submodule_dir=seedvr2_submodule_dir,
        seedvr2_model_dir=seedvr2_model_dir,
        seedvr2_dit_model=seedvr2_dit_model,
        seedvr2_cuda_device=seedvr2_cuda_device,
        seedvr2_batch_size=seedvr2_batch_size,
        seedvr2_vae_tiled=seedvr2_vae_tiled,
        seedvr2_cache_models=seedvr2_cache_models,
        seedvr2_model_residency=seedvr2_model_residency,
        seedvr2_debug=seedvr2_debug,
    )
    if skip_reason is not None:
        skipped = _skip_candidates(
            partitions.candidates,
            context,
            results,
            skip_reason,
            cancel_check=cancel_check,
        )
        check_cancel(cancel_check)
        return _save_report(skipped, context)

    assert resolved is not None
    if isinstance(resolved, SeedVR2Upscaler):
        _process_seedvr2_candidates(
            candidates=partitions.candidates,
            context=context,
            upscaler=resolved,
            hallucination_ssim_threshold=hallucination_ssim_threshold,
            hallucination_check_enabled="s3_3_hallucination_check" in enabled,
            results=results,
            cancel_check=cancel_check,
        )
    else:
        for path in partitions.candidates:
            check_cancel(cancel_check)
            _process_candidate(
                path=path,
                context=context,
                upscaler=resolved,
                hallucination_ssim_threshold=hallucination_ssim_threshold,
                hallucination_check_enabled="s3_3_hallucination_check" in enabled,
                results=results,
                cancel_check=cancel_check,
            )

    check_cancel(cancel_check)
    return _save_report(results, context)


def _normalize_upscale_model(upscale_model: str, use_seedvr: bool | None) -> str:
    if use_seedvr is not None:
        upscale_model = "seedvr2" if use_seedvr else "lanczos"
        _warn_deprecated("UpscaleStep.run(use_seedvr=...) is deprecated; use upscale_model instead.")
    if upscale_model == "seedvr":
        _warn_deprecated("upscale_model=seedvr is deprecated; use upscale_model=seedvr2 instead.")
        return "seedvr2"
    if upscale_model not in ("seedvr2", "lanczos", "custom"):
        raise ValueError(f"Unknown upscale_model: {upscale_model}")
    return upscale_model


def _warn_deprecated(message: str) -> None:
    warnings.warn(message, DeprecationWarning, stacklevel=3)
    rpt.warn(message)


def _prepare_output_context(
    dataset_dir: Path,
    output_dir: Path | None,
    report_path: Path | None,
) -> OutputContext:
    output_dir = output_dir or (dataset_dir / "_upscaled")
    output_dir.mkdir(parents=True, exist_ok=True)
    return OutputContext(
        output_dir=output_dir,
        report_path=report_path or (output_dir / "step3_report.json"),
        in_place=output_dir.resolve() == dataset_dir.resolve(),
    )


def _partition_images(dataset_dir: Path, upscale_target: int) -> ImagePartitions:
    images = img_utils.iter_images(dataset_dir)
    candidates: list[Path] = []
    already_large: list[Path] = []
    for path in images:
        if img_utils.min_side(path) < upscale_target:
            candidates.append(path)
        else:
            already_large.append(path)
    return ImagePartitions(images=images, candidates=candidates, already_large=already_large)


def _resolve_upscaler(
    *,
    upscale_model: str,
    upscaler: Upscaler | None,
    upscale_target: int,
    seedvr2_submodule_dir: str | None,
    seedvr2_model_dir: str | None,
    seedvr2_dit_model: str,
    seedvr2_cuda_device: str | None,
    seedvr2_batch_size: int,
    seedvr2_vae_tiled: bool,
    seedvr2_cache_models: bool,
    seedvr2_model_residency: str,
    seedvr2_debug: bool,
) -> tuple[Upscaler | None, str | None]:
    if upscaler is not None:
        return upscaler, None
    if upscale_model == "lanczos":
        rpt.info("Using Lanczos upscaler.")
        return lambda p, o: _lanczos_upscale(p, o, upscale_target), None
    if upscale_model == "custom":
        return None, "configured upscale_model=custom but no custom upscaler was provided"

    seedvr2 = SeedVR2Upscaler(
        resolution=upscale_target,
        submodule_dir=seedvr2_submodule_dir,
        model_dir=seedvr2_model_dir,
        dit_model=seedvr2_dit_model,
        cuda_device=seedvr2_cuda_device,
        batch_size=seedvr2_batch_size,
        vae_tiled=seedvr2_vae_tiled,
        cache_models=seedvr2_cache_models,
        model_residency=seedvr2_model_residency,
        debug=seedvr2_debug,
    )
    try:
        seedvr2.prepare()
    except SeedVR2Unavailable as exc:
        return None, _format_exception(exc)
    rpt.info("Using SeedVR2 upscaler.")
    return seedvr2, None


def _process_seedvr2_candidates(
    *,
    candidates: list[Path],
    context: OutputContext,
    upscaler: SeedVR2Upscaler,
    hallucination_ssim_threshold: float,
    hallucination_check_enabled: bool,
    results: dict,
    cancel_check: CancelCheck | None = None,
) -> None:
    tmp_by_source = {
        path: context.output_dir / (path.stem + ".upscaling.tmp" + path.suffix)
        for path in candidates
    }
    try:
        check_cancel(cancel_check)
        failures = upscaler.process_many(tmp_by_source, cancel_check=cancel_check)
        check_cancel(cancel_check)
    except CancelledRun:
        _cleanup_temp_files(tmp_by_source.values())
        raise
    except Exception as exc:
        reason = _format_exception(exc)
        rpt.error(f"SeedVR2 upscale failed: {reason} - keeping originals.")
        for path, tmp_path in tmp_by_source.items():
            tmp_path.unlink(missing_ok=True)
            results["skipped"].append({"path": str(path), "reason": reason})
            _pass_through(context, path)
        return

    for path, tmp_path in tmp_by_source.items():
        check_cancel(cancel_check)
        reason = failures.get(str(path))
        if reason is not None:
            rpt.error(f"Upscale failed for {path.name}: {reason} - keeping original.")
            results["skipped"].append({"path": str(path), "reason": reason})
            tmp_path.unlink(missing_ok=True)
            _pass_through(context, path)
            continue
        if not tmp_path.exists():
            reason = f"SeedVR2 did not write expected output: {tmp_path}"
            rpt.error(f"Upscale failed for {path.name}: {reason} - keeping original.")
            results["skipped"].append({"path": str(path), "reason": reason})
            _pass_through(context, path)
            continue
        _accept_candidate(
            path=path,
            tmp_path=tmp_path,
            context=context,
            hallucination_ssim_threshold=hallucination_ssim_threshold,
            hallucination_check_enabled=hallucination_check_enabled,
            results=results,
        )


def _skip_candidates(
    candidates: list[Path],
    context: OutputContext,
    results: dict,
    reason: str,
    cancel_check: CancelCheck | None = None,
) -> dict:
    rpt.warn(f"{reason} - skipping upscale candidates.")
    for path in candidates:
        check_cancel(cancel_check)
        _pass_through(context, path)
        results["skipped"].append({"path": str(path), "reason": reason})
    return results


def _process_candidate(
    *,
    path: Path,
    context: OutputContext,
    upscaler: Upscaler,
    hallucination_ssim_threshold: float,
    hallucination_check_enabled: bool,
    results: dict,
    cancel_check: CancelCheck | None = None,
) -> None:
    tmp_path = context.output_dir / (path.stem + ".upscaling.tmp" + path.suffix)
    try:
        check_cancel(cancel_check)
        upscaler(path, tmp_path)
        check_cancel(cancel_check)
    except CancelledRun:
        tmp_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        reason = _format_exception(exc)
        rpt.error(f"Upscale failed for {path.name}: {reason} - keeping original.")
        results["skipped"].append({"path": str(path), "reason": reason})
        tmp_path.unlink(missing_ok=True)
        _pass_through(context, path)
        return

    _accept_candidate(
        path=path,
        tmp_path=tmp_path,
        context=context,
        hallucination_ssim_threshold=hallucination_ssim_threshold,
        hallucination_check_enabled=hallucination_check_enabled,
        results=results,
    )


def _accept_candidate(
    *,
    path: Path,
    tmp_path: Path,
    context: OutputContext,
    hallucination_ssim_threshold: float,
    hallucination_check_enabled: bool,
    results: dict,
) -> None:
    out_path = context.output_dir / path.name
    hall_ssim = _hallucination_check(path, tmp_path) if hallucination_check_enabled else 1.0
    if hallucination_check_enabled and hall_ssim < hallucination_ssim_threshold:
        rpt.warn(f"REJECT upscale {path.name} (SSIM={hall_ssim:.3f}) - keeping original size.")
        results["rejected_post"].append({"path": str(path), "hall_ssim": hall_ssim})
        tmp_path.unlink(missing_ok=True)
        _pass_through(context, path)
        return

    rpt.ok(f"Upscaled {path.name} -> {out_path.name} (hall_ssim={hall_ssim:.3f})")
    os.replace(tmp_path, out_path)
    results["upscaled"].append({"original": str(path), "upscaled": str(out_path)})


def _cleanup_temp_files(paths) -> None:
    for path in paths:
        Path(path).unlink(missing_ok=True)


def _pass_through(context: OutputContext, path: Path) -> None:
    """Ensure the original sits at its output slot unchanged."""
    if context.in_place:
        return
    dst = context.output_dir / path.name
    if not dst.exists():
        shutil.copy2(path, dst)


def _save_report(results: dict, context: OutputContext) -> dict:
    rpt.save_report(results, context.report_path)
    return results


def _format_exception(exc: BaseException) -> str:
    message = str(exc).strip()
    return message or type(exc).__name__
