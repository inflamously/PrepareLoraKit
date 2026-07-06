"""
Step config schemas — per-step configuration dataclasses.

Each pipeline step type (e.g. "CaptionBboxStep") has a matching config dataclass
(e.g. CaptionBboxConfig) holding its tunable fields and validation. These are
referenced by ProjectConfig.pipeline via ``STEP_DEFINITIONS`` in
``prepare_lora_kit_pipeline.configuration``.

Each config lives in its own module under this package; they are re-exported
here so callers can keep importing from ``project.configs``.
"""
from __future__ import annotations

from .import_config import ImportConfig
from .quality_gate_config import ScorerEntry, QualityGateConfig
from .curate_config import CurateConfig
from .upscale_config import UpscaleConfig
from .vae_gate_config import VaeGateConfig
from .caption_bbox_config import CaptionBboxConfig
from .audit_config import AuditConfig
from .bucket_pools_check_config import BucketPoolsCheckConfig
from .export_config import ExportConfig

__all__ = [
    "ImportConfig",
    "ScorerEntry",
    "QualityGateConfig",
    "CurateConfig",
    "UpscaleConfig",
    "VaeGateConfig",
    "CaptionBboxConfig",
    "AuditConfig",
    "BucketPoolsCheckConfig",
    "ExportConfig",
]
