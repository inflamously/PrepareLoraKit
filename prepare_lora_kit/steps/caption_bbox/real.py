"""Real (Hugging Face VLM) implementation of CaptionBboxStep."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from prepare_lora_kit.cancellation import CancelCheck
from prepare_lora_kit.providers.interaction import InteractionProvider

import prepare_lora_kit.steps.caption_bbox.vlm as vlm
from prepare_lora_kit.steps.caption_bbox import workflow
from prepare_lora_kit.steps.caption_bbox.base import CaptionStep
from prepare_lora_kit.steps.caption_bbox.workflow import CaptionWorkflowResult


class RealCaptionStep(CaptionStep):
    """Captions with a Hugging Face VLM runtime (:class:`vlm.CaptionRuntime`)."""

    HEADER = "Caption — Bbox Annotation + HF Captioning"

    def __init__(
            self,
            dataset_dir: Path,
            *,
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
    ) -> None:
        super().__init__(
            dataset_dir,
            concept_token=concept_token,
            output_dir=output_dir,
            spot_check_pct=spot_check_pct,
            overwrite=overwrite,
            report_path=report_path,
            max_new_tokens=max_new_tokens,
            interaction=interaction,
            enabled_substeps=enabled_substeps,
            cancel_check=cancel_check,
        )
        self.model_id = str(caption_model_id or qwen_model_id or "").strip()
        # Constructed up front (never loaded until there is captioning work) so the
        # region-caption callback and the full-image loop share one runtime instance.
        self.runtime = vlm.CaptionRuntime(
            self.model_id,
            task=caption_model_task,
            quantization=quantization,
            dtype=dtype,
            max_pixels=max_pixels,
            status_callback=caption_status_callback,
            caption_prompt=caption_prompt,
            region_prompt=region_prompt,
            caption_strategy=caption_strategy,
        )

    def prepare_runtime(self, needs_captioning: bool) -> None:
        if needs_captioning:
            if not self.model_id:
                raise RuntimeError("CaptionBboxStep requires caption_model_id before captioning can run.")
            self.runtime.load()

    def teardown(self) -> None:
        self.runtime.unload()

    def report_model_metadata(self) -> dict[str, Any]:
        return self.runtime.metadata

    def report_status(self) -> dict[str, Any]:
        return self.runtime.status

    def _region_caption_fn(self, crop: Any, source_path: Path) -> str:
        return self.runtime.caption_region(crop)

    def caption_full_image(
            self,
            path: Path,
            annotations: list,
            *,
            images: list[Path],
            result: CaptionWorkflowResult,
            output_dir: Path,
    ) -> str:
        return workflow._caption_full_image(
            path,
            annotations,
            images=images,
            enabled=self.enabled,
            result=result,
            runtime=self.runtime,
            concept_token=self.concept_token,
            max_new_tokens=self.max_new_tokens,
            report_path=self._resolved_report_path(output_dir),
            cancel_check=self.cancel_check,
        )
