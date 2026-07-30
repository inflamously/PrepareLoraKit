"""Invoke adapter for CaptionVerifierStep."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.invoke.working_dataset import _require_working_dataset
from prepare_lora_kit.pipeline.configs import CaptionVerifierConfig


def invoke_caption_verifier_step(working_dir: Path, output_dir: Path,
                                 cfg: CaptionVerifierConfig, **_kw) -> dict:
    _require_working_dataset(working_dir)
    if _kw.get("mock_runtime"):
        from prepare_lora_kit.invoke.mock_caption_verifier import _mock_caption_verifier
        return _mock_caption_verifier(
            working_dir,
            output_dir,
            interaction=_kw.get("interaction"),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
        )

    from prepare_lora_kit.steps import caption_verifier
    return caption_verifier.run(
        working_dir,
        output_dir=working_dir,
        t2i_model_id=cfg.t2i_model_id,
        quantization=cfg.quantization,
        dtype=cfg.dtype,
        offload=cfg.offload,
        width=cfg.width,
        height=cfg.height,
        num_inference_steps=cfg.num_inference_steps,
        guidance_scale=cfg.guidance_scale,
        seed=cfg.seed,
        negative_prompt=cfg.negative_prompt,
        max_images=cfg.max_images,
        keep_previews=cfg.keep_previews,
        report_path=output_dir / "reports" / "CaptionVerifierStep_report.json",
        interaction=_kw.get("interaction"),
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
        status_callback=_kw.get("caption_status_callback"),
    )
