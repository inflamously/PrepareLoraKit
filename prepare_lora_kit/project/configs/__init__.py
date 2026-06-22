"""
Step config schemas — per-step configuration dataclasses.

Each pipeline step type (e.g. "CaptionStep") has a matching config dataclass
(e.g. CaptionConfig) holding its tunable fields and validation. These are
referenced by ProjectConfig.pipeline via the STEP_TYPE_MAP registry in
``base.py``.

Each config lives in its own module under this package; they are re-exported
here so callers can keep importing from ``project.configs``.
"""
from __future__ import annotations

from .quality_gate_config import ScorerEntry, QualityGateConfig
from .curate_config import CurateConfig
from .upscale_config import UpscaleConfig
from .vae_gate_config import VaeGateConfig
from .caption_config import CaptionConfig
from .audit_config import AuditConfig
from .config_gen_config import ConfigGenConfig
from .bucket_dry_run_config import BucketDryRunConfig

__all__ = [
    "ScorerEntry",
    "QualityGateConfig",
    "CurateConfig",
    "UpscaleConfig",
    "VaeGateConfig",
    "CaptionConfig",
    "AuditConfig",
    "ConfigGenConfig",
    "BucketDryRunConfig",
]
