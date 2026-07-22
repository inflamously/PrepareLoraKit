"""
Per-step invoke adapters — bridge a PipelineStep's config to its step module's
``run()`` entry point. ``STEP_INVOKE_MAP`` maps a step type to its adapter.

Each adapter signature: (working_dir, output_dir, cfg, *, concept_token, original_dir)

Each adapter (and its deterministic ``--mock`` runtime counterpart, if any) lives in its own
module in this package; this file only wires them into ``STEP_INVOKE_MAP`` and re-exports them
for backward compatibility with callers that still do ``from prepare_lora_kit import invoke``.
"""
from __future__ import annotations
from typing import Callable

from .working_dataset import _require_working_dataset
from .import_step import invoke_import_step
from .quality_gate_step import invoke_quality_gate_step
from .curate_step import invoke_curate_step
from .upscale_step import invoke_upscale_step
from .vae_gate_step import invoke_vae_gate_step
from .caption_bbox_step import invoke_caption_bbox_step
from .audit_step import invoke_audit_step
from .bucket_pools_check_step import invoke_bucket_pools_check_step
from .export_step import invoke_export_step
from .mock_curate import _mock_curate
from .mock_embeddings import _mock_embeddings
from .mock_vae_gate import _mock_vae_gate
from prepare_lora_kit.steps.caption_bbox.mock import _mock_caption

STEP_INVOKE_MAP: dict[str, Callable] = {
    "ImportStep": invoke_import_step,
    "QualityGateStep": invoke_quality_gate_step,
    "CurateStep": invoke_curate_step,
    "UpscaleStep": invoke_upscale_step,
    "VaeGateStep": invoke_vae_gate_step,
    "CaptionBboxStep": invoke_caption_bbox_step,
    "AuditStep": invoke_audit_step,
    "BucketPoolsCheckStep": invoke_bucket_pools_check_step,
    "ExportStep": invoke_export_step,
}

__all__ = [
    "STEP_INVOKE_MAP",
    "_require_working_dataset",
    "invoke_import_step",
    "invoke_quality_gate_step",
    "invoke_curate_step",
    "invoke_upscale_step",
    "invoke_vae_gate_step",
    "invoke_caption_bbox_step",
    "invoke_audit_step",
    "invoke_bucket_pools_check_step",
    "invoke_export_step",
    "_mock_curate",
    "_mock_embeddings",
    "_mock_vae_gate",
    "_mock_caption",
]
