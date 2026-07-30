"""
Step config schemas — per-step configuration dataclasses.

Each pipeline step type (e.g. "CaptionBboxStep") has a matching config dataclass
(e.g. CaptionBboxConfig) holding its tunable fields and validation. These are
referenced by ProjectConfig.pipeline via ``STEP_DEFINITIONS`` in
``prepare_lora_kit.pipeline.configuration``.

Each config lives in its own module under this package; they are re-exported
here so callers can keep importing from ``project.configs``.
"""
from __future__ import annotations

from .audit_config import AuditConfig
from .bucket_pools_check_config import BucketPoolsCheckConfig
from .caption_bbox_config import CaptionBboxConfig
from .caption_verifier_config import CaptionVerifierConfig
from .curate_config import CurateConfig
from .export_config import ExportConfig
from .import_config import ImportConfig
from .quality_gate_config import QualityGateConfig, ScorerEntry
from .upscale_config import UpscaleConfig
from .vae_gate_config import VaeGateConfig

__all__ = [
    "AuditConfig",
    "BucketPoolsCheckConfig",
    "CaptionBboxConfig",
    "CaptionVerifierConfig",
    "CurateConfig",
    "ExportConfig",
    "ImportConfig",
    "QualityGateConfig",
    "ScorerEntry",
    "UpscaleConfig",
    "VaeGateConfig",
]
