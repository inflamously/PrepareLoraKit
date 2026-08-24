"""Real (Hugging Face VLM) implementation of CaptionBboxStep."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from prepare_lora_kit.pipeline.configs import CaptionBboxConfig
from prepare_lora_kit.steps.caption_bbox import vlm, workflow
from prepare_lora_kit.steps.caption_bbox.base import CaptionStep
from prepare_lora_kit.steps.caption_bbox.options import CaptionBboxRunOptions
from prepare_lora_kit.steps.caption_bbox.workflow import CaptionWorkflowResult
from prepare_lora_kit.steps.context import StepRunContext


class RealCaptionStep(CaptionStep):
    """Captions with a Hugging Face VLM runtime (:class:`vlm.CaptionRuntime`)."""

    HEADER = "Caption — Bbox Annotation + HF Captioning"

    def __init__(
        self,
        dataset_dir: Path,
        config: CaptionBboxConfig,
        *,
        context: StepRunContext | None = None,
        options: CaptionBboxRunOptions | None = None,
    ) -> None:
        context = context or StepRunContext()
        options = options or CaptionBboxRunOptions()
        super().__init__(
            dataset_dir,
            concept_token=options.concept_token,
            output_dir=context.output_dir,
            spot_check_pct=config.spot_check_pct,
            overwrite=options.overwrite,
            report_path=context.report_path,
            max_new_tokens=config.max_new_tokens,
            interaction=context.interaction,
            enabled_substeps=context.enabled_substeps,
            cancel_check=context.cancel_check,
        )
        self.model_id = str(config.caption_model_id or "").strip()
        # Constructed up front (never loaded until there is captioning work) so the
        # region-caption callback and the full-image loop share one runtime instance.
        self.runtime = vlm.CaptionRuntime(
            self.model_id,
            task=config.caption_model_task,
            quantization=options.quantization or config.quantization,
            dtype=config.dtype,
            max_pixels=options.max_pixels,
            status_callback=options.status_callback,
            caption_prompt=config.caption_prompt,
            region_prompt=config.region_prompt,
            caption_strategy=config.caption_strategy,
            domain_brief=config.domain_brief,
        )

    def prepare_runtime(self, needs_captioning: bool) -> None:
        if needs_captioning:
            if not self.model_id:
                raise RuntimeError(
                    "CaptionBboxStep requires caption_model_id before captioning can run.")
            self.runtime.load()

    def teardown(self) -> None:
        self.runtime.unload()

    def report_model_metadata(self) -> dict[str, Any]:
        return self.runtime.metadata

    def report_status(self) -> dict[str, Any]:
        return self.runtime.status

    def _region_caption_fn(self, crop: Any, source_path: Path, *, box: dict | None = None) -> str:
        return self.runtime.caption_region(crop, source_path=source_path, box=box)

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
