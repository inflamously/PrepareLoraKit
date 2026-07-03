"""
Step 3 — Upscale (optional)

Selectively upscales images below the target min-side.
The project config selects the upscaler. Missing configured upscalers skip with
a warning instead of silently falling back to another algorithm.
Re-runs Step 1 quality checks post-upscale to reject hallucinated-texture outputs.

JPEG sources are always converted to PNG when processed (never on a plain
pass-through), since JPEG compression artifacts shouldn't survive into
training data. Images at/above ``upscale_highlight_threshold`` that are still
JPEG get an extra downscale-then-reupscale cleanup pass first, since their
block artifacts are baked in at the original encoding resolution.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ...cancellation import CancelCheck, CancelledRun, check_cancel
from ...providers.interaction import InteractionProvider
from ...utils import image as img_utils
from ...utils import report as rpt
from .hallucination import HALLUCINATION_SSIM_THRESHOLD, _hallucination_check
from .jpeg_cleanup import _is_jpeg, _write_downscaled_copy
from .seedvr2_adapter import (
    DEFAULT_SEEDVR2_DIT_MODEL,
    SeedVR2Unavailable,
    SeedVR2Upscaler,
)
from .upscalers import UPSCALE_HIGHLIGHT_THRESHOLD, UPSCALE_TARGET, _lanczos_upscale

Upscaler = Callable[[Path, Path], Path | None]


@dataclass
class OutputContext:
    output_dir: Path
    report_path: Path
    in_place: bool
    src_dir: Path


@dataclass
class ImageInfo:
    path: Path
    min_side: int | None
    is_jpeg: bool
    flagged: bool
    planned_action: str  # "upscale" | "jpeg_cleanup" | "pass_through"
    needs_pre_downscale: bool


@dataclass
class ImagePartitions:
    images: list[ImageInfo]

    def with_action(self, action: str) -> list[ImageInfo]:
        return [info for info in self.images if info.planned_action == action]


def run(
    dataset_dir: Path,
    output_dir: Path | None = None,
    upscale_target: int = UPSCALE_TARGET,
    upscale_highlight_threshold: int = UPSCALE_HIGHLIGHT_THRESHOLD,
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
    interaction: InteractionProvider | None = None,
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
    seedvr2_kwargs = dict(
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

    # The shrink-then-regrow cleanup only makes sense with a generative upscaler
    # (SeedVR2) that can restore detail. Doing it with Lanczos just blurs the
    # image (downscale + interpolated upscale = detail loss), so it is gated off
    # for non-SeedVR2 models — those JPEGs get a plain upscale or pass through.
    enable_seedvr2_cleanup = upscale_model == "seedvr2"

    if "s3_1_select_candidates" in enabled:
        partitions = _partition_images(
            dataset_dir, upscale_target, upscale_highlight_threshold, enable_seedvr2_cleanup,
        )
        _resolve_destination_collisions(partitions, context)
    else:
        partitions = ImagePartitions(images=[
            ImageInfo(
                path=path, min_side=None, is_jpeg=_is_jpeg(path),
                flagged=False, planned_action="pass_through", needs_pre_downscale=False,
            )
            for path in img_utils.iter_images(dataset_dir)
        ])

    results: dict = {"upscaled": [], "rejected_post": [], "skipped": []}
    results["substeps"] = {
        "s3_1_select_candidates": {"enabled": "s3_1_select_candidates" in enabled},
        "s3_2_upscale": {"enabled": "s3_2_upscale" in enabled},
        "s3_3_hallucination_check": {"enabled": "s3_3_hallucination_check" in enabled},
    }

    flagged = [info for info in partitions.images if info.flagged]
    if flagged:
        rpt.warn(
            f"{len(flagged)} images flagged (<= {upscale_highlight_threshold}px min-side, "
            "or a JPEG due for artifact cleanup)."
        )

    if "s3_1_select_candidates" in enabled and interaction is not None and flagged:
        check_cancel(cancel_check)
        decisions = interaction.upscale_review(_build_review_items(flagged, upscale_highlight_threshold))
        _apply_review_decisions(partitions, decisions)
        check_cancel(cancel_check)

    results["images"] = [_image_info_report(info) for info in partitions.images]

    for info in partitions.with_action("pass_through"):
        check_cancel(cancel_check)
        _pass_through(context, info.path)

    if "s3_2_upscale" not in enabled:
        rpt.info("Upscale substep disabled; passing through originals.")
        actionable = partitions.with_action("upscale") + partitions.with_action("jpeg_cleanup")
        results["skipped"] = [
            {"path": str(info.path), "reason": "s3_2_upscale disabled"} for info in actionable
        ]
        for info in actionable:
            check_cancel(cancel_check)
            _pass_through(context, info.path)
        return _save_report(results, context)

    candidates = partitions.with_action("upscale")
    cleanup_candidates = partitions.with_action("jpeg_cleanup")

    if not candidates and not cleanup_candidates:
        rpt.ok(f"All images already >= {upscale_target}px - skipping upscale.")
        results["skipped"] = [str(info.path) for info in partitions.images]
        return _save_report(results, context)

    with tempfile.TemporaryDirectory(prefix="plk_upscale_scratch_") as scratch_dir_str:
        scratch_dir = Path(scratch_dir_str)

        if candidates:
            rpt.info(f"{len(candidates)} images below {upscale_target}px min-side will be upscaled.")
            check_cancel(cancel_check)
            resolved, skip_reason = _resolve_upscaler(
                upscale_model=upscale_model,
                upscaler=upscaler,
                upscale_target=upscale_target,
                seedvr2_kwargs=seedvr2_kwargs,
            )
            if skip_reason is not None:
                _skip_candidates(
                    [info.path for info in candidates],
                    context,
                    results,
                    skip_reason,
                    cancel_check=cancel_check,
                )
            else:
                assert resolved is not None
                pre_downscale_paths = {info.path for info in candidates if info.needs_pre_downscale}
                if isinstance(resolved, SeedVR2Upscaler):
                    _process_seedvr2_candidates(
                        candidates=[info.path for info in candidates],
                        context=context,
                        upscaler=resolved,
                        hallucination_ssim_threshold=hallucination_ssim_threshold,
                        hallucination_check_enabled="s3_3_hallucination_check" in enabled,
                        results=results,
                        pre_downscale_paths=pre_downscale_paths,
                        scratch_dir=scratch_dir,
                        cancel_check=cancel_check,
                    )
                else:
                    for info in candidates:
                        check_cancel(cancel_check)
                        effective_upscaler = (
                            _with_predownscale(resolved, scratch_dir)
                            if info.path in pre_downscale_paths
                            else resolved
                        )
                        _process_candidate(
                            path=info.path,
                            context=context,
                            upscaler=effective_upscaler,
                            hallucination_ssim_threshold=hallucination_ssim_threshold,
                            hallucination_check_enabled="s3_3_hallucination_check" in enabled,
                            results=results,
                            cancel_check=cancel_check,
                        )

        if cleanup_candidates:
            check_cancel(cancel_check)
            _process_jpeg_cleanup_candidates(
                infos=cleanup_candidates,
                context=context,
                upscale_target=upscale_target,
                hallucination_ssim_threshold=hallucination_ssim_threshold,
                hallucination_check_enabled="s3_3_hallucination_check" in enabled,
                results=results,
                seedvr2_kwargs=seedvr2_kwargs,
                scratch_dir=scratch_dir,
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
        src_dir=dataset_dir,
    )


def _dest_for(context: OutputContext, path: Path) -> Path:
    """Mirror a source image's subpath into the output dir, unchanged format.

    Used for plain pass-through copies, which must stay byte-for-byte the
    original format — only ``_processed_dest_for`` converts JPEGs to PNG.
    """
    return context.output_dir / path.relative_to(context.src_dir)


def _processed_dest_for(context: OutputContext, path: Path) -> Path:
    """Destination for an image that gets actively processed (upscaled or
    JPEG-cleaned-up). JPEG sources always land as PNG; everything else keeps
    its original suffix."""
    dest = _dest_for(context, path)
    return dest.with_suffix(".png") if _is_jpeg(path) else dest


def _tmp_for(out_path: Path, path: Path) -> Path:
    """Temp upscale target next to the final destination (same subdir)."""
    return out_path.parent / (path.stem + ".upscaling.tmp" + out_path.suffix)


def _partition_images(
    dataset_dir: Path,
    upscale_target: int,
    upscale_highlight_threshold: int,
    enable_seedvr2_cleanup: bool,
) -> ImagePartitions:
    images = img_utils.iter_images(dataset_dir)
    infos: list[ImageInfo] = []
    for path in images:
        min_side = img_utils.min_side(path)
        is_jpeg = _is_jpeg(path)
        # The shrink-then-regrow trick (pre-downscale here, jpeg_cleanup below)
        # is only safe with a generative upscaler; otherwise it would blur.
        needs_pre_downscale = (
            is_jpeg and min_side >= upscale_highlight_threshold and enable_seedvr2_cleanup
        )
        if min_side < upscale_target:
            planned_action = "upscale"
        elif needs_pre_downscale:
            planned_action = "jpeg_cleanup"
        else:
            planned_action = "pass_through"
        infos.append(ImageInfo(
            path=path,
            min_side=min_side,
            is_jpeg=is_jpeg,
            flagged=min_side <= upscale_highlight_threshold or needs_pre_downscale,
            planned_action=planned_action,
            needs_pre_downscale=needs_pre_downscale,
        ))
    return ImagePartitions(images=infos)


def _resolve_destination_collisions(partitions: ImagePartitions, context: OutputContext) -> None:
    """Guard against a JPEG→PNG conversion clobbering another source image.

    A processed ``foo.jpg`` lands at ``foo.png``; if a different ``foo.png``
    (or ``foo.jpeg``) also exists, the conversion would overwrite it. When that
    happens we leave the JPEG untouched (pass-through, keeping its suffix) so no
    data is silently lost.
    """
    dest_by_path: dict[Path, Path] = {}
    dest_counts: dict[Path, int] = {}
    for info in partitions.images:
        dest = _planned_dest(context, info)
        dest_by_path[info.path] = dest
        dest_counts[dest] = dest_counts.get(dest, 0) + 1
    for info in partitions.images:
        if (
            info.is_jpeg
            and info.planned_action != "pass_through"
            and dest_counts[dest_by_path[info.path]] > 1
        ):
            rpt.warn(
                f"Destination collision for {info.path.name}: another image already targets "
                f"{dest_by_path[info.path].name}; leaving it untouched to avoid overwrite."
            )
            info.planned_action = "pass_through"
            info.needs_pre_downscale = False
            info.flagged = False


def _planned_dest(context: OutputContext, info: ImageInfo) -> Path:
    if info.planned_action == "pass_through":
        return _dest_for(context, info.path)
    return _processed_dest_for(context, info.path)


def _image_info_report(info: ImageInfo) -> dict:
    return {
        "path": str(info.path),
        "min_side": info.min_side,
        "is_jpeg": info.is_jpeg,
        "flagged": info.flagged,
        "planned_action": info.planned_action,
    }


def _build_review_items(flagged: list[ImageInfo], threshold: int) -> list[dict]:
    items = []
    for info in flagged:
        try:
            width, height = img_utils.image_size(info.path)
        except Exception:
            width = height = None
        items.append({
            "path": str(info.path),
            "name": info.path.name,
            "width": width,
            "height": height,
            "min_side": info.min_side,
            "threshold": threshold,
            "is_jpeg": info.is_jpeg,
            "planned_action": info.planned_action,
            "flagged": info.flagged,
            "initial_decision": "upscale",
        })
    return items


def _apply_review_decisions(partitions: ImagePartitions, decisions: dict[str, str]) -> None:
    for info in partitions.images:
        decision = decisions.get(str(info.path)) or decisions.get(str(info.path.resolve()))
        if decision == "skip":
            info.planned_action = "pass_through"


def _resolve_upscaler(
    *,
    upscale_model: str,
    upscaler: Upscaler | None,
    upscale_target: int,
    seedvr2_kwargs: dict,
) -> tuple[Upscaler | None, str | None]:
    if upscaler is not None:
        return upscaler, None
    if upscale_model == "lanczos":
        rpt.info("Using Lanczos upscaler.")
        return lambda p, o: _lanczos_upscale(p, o, upscale_target), None
    if upscale_model == "custom":
        return None, "configured upscale_model=custom but no custom upscaler was provided"

    seedvr2, skip_reason = _build_seedvr2(resolution=upscale_target, **seedvr2_kwargs)
    if skip_reason is not None:
        return None, skip_reason
    rpt.info("Using SeedVR2 upscaler.")
    return seedvr2, None


def _build_seedvr2(
    *,
    resolution: int,
    submodule_dir: str | None,
    model_dir: str | None,
    dit_model: str,
    cuda_device: str | None,
    batch_size: int,
    vae_tiled: bool,
    cache_models: bool,
    model_residency: str,
    debug: bool,
) -> tuple[SeedVR2Upscaler | None, str | None]:
    seedvr2 = SeedVR2Upscaler(
        resolution=resolution,
        submodule_dir=submodule_dir,
        model_dir=model_dir,
        dit_model=dit_model,
        cuda_device=cuda_device,
        batch_size=batch_size,
        vae_tiled=vae_tiled,
        cache_models=cache_models,
        model_residency=model_residency,
        debug=debug,
    )
    try:
        seedvr2.prepare()
    except SeedVR2Unavailable as exc:
        return None, _format_exception(exc)
    return seedvr2, None


def _with_predownscale(inner: Upscaler, scratch_dir: Path) -> Upscaler:
    """Wrap an upscaler so it runs on a pre-shrunk copy of a JPEG source.

    Shrinking sheds compression block artifacts (baked in at the original
    encoding resolution) before the inner upscaler regrows the resolution,
    instead of upscaling the noisy JPEG pixels directly.
    """
    def _wrapped(path: Path, output_path: Path) -> Path | None:
        downscaled = _write_downscaled_copy(path, scratch_dir)
        return inner(downscaled, output_path)

    return _wrapped


def _process_seedvr2_candidates(
    *,
    candidates: list[Path],
    context: OutputContext,
    upscaler: SeedVR2Upscaler,
    hallucination_ssim_threshold: float,
    hallucination_check_enabled: bool,
    results: dict,
    pre_downscale_paths: set[Path] | None = None,
    scratch_dir: Path | None = None,
    cancel_check: CancelCheck | None = None,
) -> None:
    pre_downscale_paths = pre_downscale_paths or set()
    tmp_by_source = {}
    sources_by_path = {}
    for path in candidates:
        out_path = _processed_dest_for(context, path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_by_source[path] = _tmp_for(out_path, path)
        if path in pre_downscale_paths:
            assert scratch_dir is not None
            sources_by_path[path] = _write_downscaled_copy(path, scratch_dir)
    try:
        check_cancel(cancel_check)
        failures = upscaler.process_many(
            tmp_by_source, sources_by_path=sources_by_path or None, cancel_check=cancel_check,
        )
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


def _process_jpeg_cleanup_candidates(
    *,
    infos: list[ImageInfo],
    context: OutputContext,
    upscale_target: int,
    hallucination_ssim_threshold: float,
    hallucination_check_enabled: bool,
    results: dict,
    seedvr2_kwargs: dict,
    scratch_dir: Path,
    cancel_check: CancelCheck | None = None,
) -> None:
    _probe, skip_reason = _build_seedvr2(resolution=upscale_target, **seedvr2_kwargs)
    if skip_reason is not None:
        rpt.warn(f"SeedVR2 unavailable for JPEG cleanup ({skip_reason}) - leaving large JPEGs untouched.")
        for info in infos:
            check_cancel(cancel_check)
            results["skipped"].append({
                "path": str(info.path),
                "reason": f"jpeg_cleanup unavailable: {skip_reason}",
            })
            _pass_through(context, info.path)
        return

    rpt.info(f"{len(infos)} large JPEG(s) will be cleaned up via SeedVR2 (downscale then re-upscale).")
    # Each image is re-upscaled to its own min-side so it never ends up smaller
    # than it started. Group by that target so same-size images share one worker
    # (the model is loaded once per group, not once per image).
    by_target: dict[int, list[ImageInfo]] = {}
    for info in infos:
        target = max(upscale_target, info.min_side or upscale_target)
        by_target.setdefault(target, []).append(info)

    for target, group in sorted(by_target.items()):
        check_cancel(cancel_check)
        seedvr2, build_reason = _build_seedvr2(resolution=target, **seedvr2_kwargs)
        if build_reason is not None:
            for info in group:
                results["skipped"].append({"path": str(info.path), "reason": f"jpeg_cleanup: {build_reason}"})
                _pass_through(context, info.path)
            continue
        group_paths = [info.path for info in group]
        _process_seedvr2_candidates(
            candidates=group_paths,
            context=context,
            upscaler=seedvr2,
            hallucination_ssim_threshold=hallucination_ssim_threshold,
            hallucination_check_enabled=hallucination_check_enabled,
            results=results,
            pre_downscale_paths=set(group_paths),
            scratch_dir=scratch_dir,
            cancel_check=cancel_check,
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
    out_path = _processed_dest_for(context, path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _tmp_for(out_path, path)
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
    out_path = _processed_dest_for(context, path)
    hall_ssim = _hallucination_check(path, tmp_path) if hallucination_check_enabled else 1.0
    if hallucination_check_enabled and hall_ssim < hallucination_ssim_threshold:
        rpt.warn(f"REJECT upscale {path.name} (SSIM={hall_ssim:.3f}) - keeping original size.")
        results["rejected_post"].append({"path": str(path), "hall_ssim": hall_ssim})
        tmp_path.unlink(missing_ok=True)
        _pass_through(context, path)
        return

    rpt.ok(f"Upscaled {path.name} -> {out_path.name} (hall_ssim={hall_ssim:.3f})")
    os.replace(tmp_path, out_path)
    if context.in_place and out_path != path:
        # The original sat at the same path/dir as out_path under a different
        # (pre-conversion) suffix - e.g. a JPEG source converted to PNG.
        path.unlink(missing_ok=True)
    results["upscaled"].append({"original": str(path), "upscaled": str(out_path)})


def _cleanup_temp_files(paths) -> None:
    for path in paths:
        Path(path).unlink(missing_ok=True)


def _pass_through(context: OutputContext, path: Path) -> None:
    """Ensure the original sits at its output slot unchanged (same format)."""
    if context.in_place:
        return
    dst = _dest_for(context, path)
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def _save_report(results: dict, context: OutputContext) -> dict:
    rpt.save_report(results, context.report_path)
    return results


def _format_exception(exc: BaseException) -> str:
    message = str(exc).strip()
    return message or type(exc).__name__
