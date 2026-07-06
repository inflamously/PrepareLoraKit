"""Invoke adapter for CaptionBboxStep."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from prepare_lora_kit_pipeline.configs import CaptionBboxConfig

from .working_dataset import _require_working_dataset


def invoke_caption_bbox_step(working_dir: Path, output_dir: Path, cfg: CaptionBboxConfig,
                             *, concept_token: Optional[str], **_kw) -> None:
    _require_working_dataset(working_dir)
    if _kw.get("mock_runtime"):
        from .mock_caption import _mock_caption
        _mock_caption(
            working_dir,
            output_dir,
            concept_token=concept_token,
            force=bool(_kw.get("force", False)),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
            interaction=_kw.get("interaction"),
        )
        return

    from ..steps import caption_bbox
    runtime = _kw.get("caption_runtime") or {}
    caption_model_id = runtime.get("model_id") or cfg.caption_model_id
    caption_model_task = runtime.get("task") or cfg.caption_model_task
    quantization = runtime.get("vram_mode") or cfg.quantization
    caption_bbox.run(
        working_dir,
        concept_token=concept_token,
        output_dir=working_dir,
        caption_model_id=caption_model_id,
        caption_model_task=caption_model_task,
        quantization=quantization,
        dtype=cfg.dtype,
        max_new_tokens=cfg.max_new_tokens,
        spot_check_pct=cfg.spot_check_pct,
        overwrite=bool(_kw.get("force", False)),
        report_path=output_dir / "reports" / "CaptionBboxStep_report.json",
        interaction=_kw.get("interaction"),
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
        caption_status_callback=_kw.get("caption_status_callback"),
        caption_prompt=cfg.caption_prompt,
        region_prompt=cfg.region_prompt,
    )
