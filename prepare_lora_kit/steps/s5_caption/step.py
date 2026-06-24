"""
Step 5 — Caption with Bbox Annotation + Hugging Face captioning

For each image:
  1. Open a tkinter bbox-draw canvas (Ideogram-4-style region annotation).
  2. User draws boxes and labels each region.
  3. Bbox context + image are sent to a HF caption model to produce a structured caption.
  4. Caption is cleaned, token-checked, and saved as {stem}.txt.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable

from ...cancellation import CancelCheck, check_cancel
from ...interaction import CliInteractionProvider, InteractionProvider
from ...utils import image as img_utils
from ...utils import report as rpt

from . import vlm
from .artifacts import (
    BBOX_PREFIX,
    _bbox_stem,
    _clean_bbox_artifacts,
    _is_bbox_artifact,
    _save_bbox_training_item,
)
from .reports import _save_failure_report, build_success_report, save_success_report
from .validation import render_spot_check, validate_captions
from .workflow import CaptionWorkflowResult, caption_images

DEFAULT_SUBSTEPS = ["s5_1_annotate", "s5_2_caption", "s5_3_validate"]
__all__ = [
    "run",
    "BBOX_PREFIX",
    "_bbox_stem",
    "_clean_bbox_artifacts",
    "_is_bbox_artifact",
    "_save_bbox_training_item",
    "_save_failure_report",
]

# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    dataset_dir: Path,
    concept_token: str | None = None,
    output_dir: Path | None = None,
    caption_model_id: str | None = None,
    caption_model_task: str = "auto",
    spot_check_pct: float = 0.10,
    overwrite: bool = False,
    report_path: Path | None = None,
    quantization: str = "none",
    dtype: str = "bfloat16",
    max_new_tokens: int = 200,
    max_pixels: int = vlm._DEFAULT_MAX_PIXELS,
    interaction: InteractionProvider | None = None,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
    caption_status_callback: Callable[[dict[str, Any]], None] | None = None,
    qwen_model_id: str | None = None,
) -> dict:
    style_mode = not concept_token
    rpt.step_header(5, "Caption — Bbox Annotation + HF Captioning")
    enabled = set(enabled_substeps or DEFAULT_SUBSTEPS)
    model_id = str(caption_model_id or qwen_model_id or "").strip()

    output_dir = _prepare_output_dir(output_dir or dataset_dir, overwrite)
    all_images, images = _collect_source_images(dataset_dir)
    if not all_images:
        rpt.warn(f"No images in {dataset_dir}")
        return {}

    _log_caption_mode(images, concept_token, style_mode=style_mode)
    _require_model_for_captioning(enabled, model_id)

    check_cancel(cancel_check)
    img_utils.materialize(all_images, dataset_dir, output_dir)

    runtime = _create_runtime(
        model_id,
        caption_model_task=caption_model_task,
        quantization=quantization,
        dtype=dtype,
        max_pixels=max_pixels,
        caption_status_callback=caption_status_callback,
    )

    try:
        # Load caption model before we continue
        runtime.load()

        caption_result = _caption_dataset(
            images,
            output_dir=output_dir,
            overwrite=overwrite,
            enabled=enabled,
            interaction=interaction,
            runtime=runtime,
            concept_token=concept_token,
            style_mode=style_mode,
            max_new_tokens=max_new_tokens,
            report_path=report_path,
            cancel_check=cancel_check,
        )
        return _validate_and_save_success(
            images,
            caption_result,
            runtime=runtime,
            concept_token=concept_token,
            style_mode=style_mode,
            enabled=enabled,
            spot_check_pct=spot_check_pct,
            report_path=report_path,
            output_dir=output_dir,
            cancel_check=cancel_check,
        )
    finally:
        runtime.unload()


def _create_runtime(
    model_id: str,
    *,
    caption_model_task: str,
    quantization: str,
    dtype: str,
    max_pixels: int,
    caption_status_callback: Callable[[dict[str, Any]], None] | None,
) -> vlm.CaptionRuntime:
    return vlm.CaptionRuntime(
        model_id,
        task=caption_model_task,
        quantization=quantization,
        dtype=dtype,
        max_pixels=max_pixels,
        status_callback=caption_status_callback,
    )


def _caption_dataset(
    images: list[Path],
    *,
    output_dir: Path,
    overwrite: bool,
    enabled: set[str],
    interaction: InteractionProvider | None,
    runtime: vlm.CaptionRuntime,
    concept_token: str | None,
    style_mode: bool,
    max_new_tokens: int,
    report_path: Path | None,
    cancel_check: CancelCheck | None,
) -> CaptionWorkflowResult:
    return caption_images(
        images,
        output_dir=output_dir,
        overwrite=overwrite,
        enabled=enabled,
        provider=interaction or CliInteractionProvider(),
        runtime=runtime,
        concept_token=concept_token,
        style_mode=style_mode,
        max_new_tokens=max_new_tokens,
        report_path=report_path,
        cancel_check=cancel_check,
    )


def _validate_and_save_success(
    images: list[Path],
    caption_result: CaptionWorkflowResult,
    *,
    runtime: vlm.CaptionRuntime,
    concept_token: str | None,
    style_mode: bool,
    enabled: set[str],
    spot_check_pct: float,
    report_path: Path | None,
    output_dir: Path,
    cancel_check: CancelCheck | None,
) -> dict:
    check_cancel(cancel_check)
    missing_token, short, long_ = validate_captions(
        caption_result.captions,
        concept_token,
        style_mode=style_mode,
        enabled=enabled,
        cancel_check=cancel_check,
    )
    sample = render_spot_check(
        caption_result.captions,
        spot_check_pct,
        enabled=enabled,
        cancel_check=cancel_check,
    )

    report = build_success_report(
        images=images,
        captions=caption_result.captions,
        runtime=runtime,
        skipped_annotation=caption_result.skipped_annotation,
        missing_token=missing_token,
        short_captions=short,
        long_captions=long_,
        spot_check_sample=sample,
        enabled=enabled,
    )
    check_cancel(cancel_check)
    save_success_report(report, report_path, output_dir)
    return report


def _prepare_output_dir(output_dir: Path, overwrite: bool) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    if overwrite:
        _clean_bbox_artifacts(output_dir)
    return output_dir


def _collect_source_images(dataset_dir: Path) -> tuple[list[Path], list[Path]]:
    all_images = img_utils.iter_images(dataset_dir)
    images = [p for p in all_images if not _is_bbox_artifact(p)]
    return all_images, images


def _log_caption_mode(
    images: list[Path],
    concept_token: str | None,
    *,
    style_mode: bool,
) -> None:
    if style_mode:
        rpt.info(f"Captioning {len(images)} images in style mode (no concept token).")
    else:
        rpt.info(f"Captioning {len(images)} images. Concept token: '{concept_token}'")


def _require_model_for_captioning(enabled: set[str], model_id: str) -> None:
    if "s5_2_caption" in enabled and not model_id:
        raise RuntimeError("CaptionStep requires caption_model_id before captioning can run.")
