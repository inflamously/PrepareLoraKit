"""CaptionBboxStep — thin entry point; the orchestration lives in :mod:`.base`."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.pipeline.configs import CaptionBboxConfig
from prepare_lora_kit.steps.caption_bbox import vlm
from prepare_lora_kit.steps.caption_bbox.artifacts import (
    BBOX_PREFIX,
    _bbox_stem,
    _clean_bbox_artifacts,
    _is_bbox_artifact,
    _save_bbox_training_item,
)
from prepare_lora_kit.steps.caption_bbox.options import CaptionBboxRunOptions
from prepare_lora_kit.steps.caption_bbox.real import RealCaptionStep
from prepare_lora_kit.steps.caption_bbox.reports import _save_failure_report
from prepare_lora_kit.steps.context import StepRunContext

__all__ = [
    "BBOX_PREFIX",
    "_bbox_stem",
    "_clean_bbox_artifacts",
    "_is_bbox_artifact",
    "_save_bbox_training_item",
    "_save_failure_report",
    "run",
    "vlm",
]


def run(
    dataset_dir: Path,
    config: CaptionBboxConfig,
    *,
    context: StepRunContext | None = None,
    options: CaptionBboxRunOptions | None = None,
) -> dict:
    """Run the real VLM captioning step. See :class:`RealCaptionStep`."""
    return RealCaptionStep(
        dataset_dir,
        config,
        context=context,
        options=options,
    ).run()
