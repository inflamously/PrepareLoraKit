"""
Per-step invoke adapters — bridge a PipelineStep's config to its step module's
``run()`` entry point. ``STEP_INVOKE_MAP`` maps a step type to its adapter.

Each adapter signature: (working_dir, output_dir, cfg, *, network, concept_token, original_dir)

Each adapter (and its deterministic ``--mock`` runtime counterpart, if any) lives in its own
module in this package; this file only wires them into ``STEP_INVOKE_MAP`` and re-exports them
for backward compatibility with callers that still do ``from prepare_lora_kit import invoke``.
"""
from __future__ import annotations
from typing import Callable

from .working_dataset import _require_working_dataset
from .import_step import _invoke_ImportStep
from .quality_gate_step import _invoke_QualityGateStep
from .curate_step import _invoke_CurateStep
from .upscale_step import _invoke_UpscaleStep
from .vae_gate_step import _invoke_VaeGateStep
from .caption_bbox_step import _invoke_CaptionBboxStep
from .audit_step import _invoke_AuditStep
from .bucket_pools_check_step import _invoke_BucketPoolsCheckStep
from .export_step import _invoke_ExportStep
from .mock_curate import _mock_curate
from .mock_embeddings import _mock_embeddings
from .mock_vae_gate import _mock_vae_gate
from .mock_caption import _mock_caption

STEP_INVOKE_MAP: dict[str, Callable] = {
    "ImportStep": _invoke_ImportStep,
    "QualityGateStep": _invoke_QualityGateStep,
    "CurateStep": _invoke_CurateStep,
    "UpscaleStep": _invoke_UpscaleStep,
    "VaeGateStep": _invoke_VaeGateStep,
    "CaptionBboxStep": _invoke_CaptionBboxStep,
    "AuditStep": _invoke_AuditStep,
    "BucketPoolsCheckStep": _invoke_BucketPoolsCheckStep,
    "ExportStep": _invoke_ExportStep,
}

__all__ = [
    "STEP_INVOKE_MAP",
    "_require_working_dataset",
    "_invoke_ImportStep",
    "_invoke_QualityGateStep",
    "_invoke_CurateStep",
    "_invoke_UpscaleStep",
    "_invoke_VaeGateStep",
    "_invoke_CaptionBboxStep",
    "_invoke_AuditStep",
    "_invoke_BucketPoolsCheckStep",
    "_invoke_ExportStep",
    "_mock_curate",
    "_mock_embeddings",
    "_mock_vae_gate",
    "_mock_caption",
]
