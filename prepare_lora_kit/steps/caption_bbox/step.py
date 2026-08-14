"""CaptionBboxStep — thin entry point; the orchestration lives in :mod:`.base`."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from prepare_lora_kit.cancellation import CancelCheck
from prepare_lora_kit.providers.interaction import InteractionProvider
from prepare_lora_kit.steps.caption_bbox import vlm
from prepare_lora_kit.steps.caption_bbox.artifacts import (
    BBOX_PREFIX,
    _bbox_stem,
    _clean_bbox_artifacts,
    _is_bbox_artifact,
    _save_bbox_training_item,
)
from prepare_lora_kit.steps.caption_bbox.real import RealCaptionStep
from prepare_lora_kit.steps.caption_bbox.reports import _save_failure_report

__all__ = [
    "BBOX_PREFIX",
    "_bbox_stem",
    "_clean_bbox_artifacts",
    "_is_bbox_artifact",
    "_save_bbox_training_item",
    "_save_failure_report",
    "run",
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
        domain_brief: str | None = None,
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
        domain_brief=domain_brief,
    ).run()
