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
from .caption_step import _invoke_CaptionStep
from .audit_step import _invoke_AuditStep
from .config_gen_step import _invoke_ConfigGenStep
from .bucket_dry_run_step import _invoke_BucketDryRunStep
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
    "CaptionStep": _invoke_CaptionStep,
    "AuditStep": _invoke_AuditStep,
    "ConfigGenStep": _invoke_ConfigGenStep,
    "BucketDryRunStep": _invoke_BucketDryRunStep,
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
    "_invoke_CaptionStep",
    "_invoke_AuditStep",
    "_invoke_ConfigGenStep",
    "_invoke_BucketDryRunStep",
    "_invoke_ExportStep",
    "_mock_curate",
    "_mock_embeddings",
    "_mock_vae_gate",
    "_mock_caption",
]
