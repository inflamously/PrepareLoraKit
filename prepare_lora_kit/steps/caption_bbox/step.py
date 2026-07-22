"""CaptionBboxStep — Bbox Annotation + Hugging Face captioning.

Thin entry point: :func:`run` constructs a :class:`RealCaptionStep` and runs it.
The orchestration lives in :mod:`~prepare_lora_kit.steps.caption_bbox.base`; the
real and mock implementations in ``real.py`` / ``mock.py``.

For each image:
  1. Optional region annotations are collected (UI-only; the CLI captions full images).
  2. Bbox context + image are sent to a HF caption model to produce a structured caption.
  3. Caption is cleaned, token-checked, and saved as {stem}.txt.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable

from prepare_lora_kit.cancellation import CancelCheck
from prepare_lora_kit.providers.interaction import InteractionProvider

import prepare_lora_kit.steps.caption_bbox.vlm as vlm
from prepare_lora_kit.steps.caption_bbox.real import RealCaptionStep
from prepare_lora_kit.steps.caption_bbox.artifacts import (
    BBOX_PREFIX,
    _bbox_stem,
    _clean_bbox_artifacts,
    _is_bbox_artifact,
    _save_bbox_training_item,
)
from prepare_lora_kit.steps.caption_bbox.reports import _save_failure_report

__all__ = [
    "run",
    "BBOX_PREFIX",
    "_bbox_stem",
    "_clean_bbox_artifacts",
    "_is_bbox_artifact",
    "_save_bbox_training_item",
    "_save_failure_report",
]


def run(
        dataset_dir: Path,
        concept_token: str | None = None,
        output_dir: Path | None = None,
        caption_model_id: str | None = None,
        caption_model_task: str = "auto",
        caption_strategy: str = "grounded",
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
        caption_prompt: str | None = None,
        region_prompt: str | None = None,
) -> dict:
    """Run the real VLM captioning step. See :class:`RealCaptionStep`."""
    return RealCaptionStep(
        dataset_dir,
        concept_token=concept_token,
        output_dir=output_dir,
        caption_model_id=caption_model_id,
        caption_model_task=caption_model_task,
        caption_strategy=caption_strategy,
        spot_check_pct=spot_check_pct,
        overwrite=overwrite,
        report_path=report_path,
        quantization=quantization,
        dtype=dtype,
        max_new_tokens=max_new_tokens,
        max_pixels=max_pixels,
        interaction=interaction,
        enabled_substeps=enabled_substeps,
        cancel_check=cancel_check,
        caption_status_callback=caption_status_callback,
        qwen_model_id=qwen_model_id,
        caption_prompt=caption_prompt,
        region_prompt=region_prompt,
    ).run()
