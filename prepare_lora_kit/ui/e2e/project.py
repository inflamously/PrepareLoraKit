"""Project config helpers for UI end-to-end mock fixtures."""
from __future__ import annotations

from pathlib import Path

from ...project.base import PipelineStep, ProjectConfig
from ...project.configs import (
    AuditConfig,
    BucketDryRunConfig,
    CaptionConfig,
    ConfigGenConfig,
    CurateConfig,
    ImportConfig,
    QualityGateConfig,
    ScorerEntry,
    UpscaleConfig,
    VaeGateConfig,
)
from .constants import MOCK_PROJECT_NAME, QUALITY_GATE_MIN_SIDE


def mock_project(input_dir: Path) -> ProjectConfig:
    return ProjectConfig(
        name=MOCK_PROJECT_NAME,
        network="flux-klein-9b",
        input_dir=str(input_dir),
        pipeline=[
            PipelineStep("ImportStep", ImportConfig()),
            PipelineStep(
                "QualityGateStep",
                QualityGateConfig(
                    scorers=[
                        ScorerEntry(
                            name="min_side",
                            op="lt",
                            threshold=QUALITY_GATE_MIN_SIDE,
                        )
                    ],
                    auto_only=False,
                ),
            ),
            # Mock runtime uses deterministic embeddings; keep clipscan enabled
            # so coverage plot flows exercise the UI without loading CLIP.
            PipelineStep("CurateStep", CurateConfig(skip_clip=False)),
            PipelineStep(
                "UpscaleStep",
                UpscaleConfig(upscale_target=1664, upscale_model="lanczos"),
            ),
            PipelineStep(
                "CaptionStep",
                CaptionConfig(
                    caption_model_id="mock",
                    vram_tier="auto",
                    max_new_tokens=32,
                    spot_check_pct=0.0,
                ),
            ),
            PipelineStep("VaeGateStep", VaeGateConfig()),
            PipelineStep("AuditStep", AuditConfig()),
            PipelineStep("ConfigGenStep", ConfigGenConfig()),
            PipelineStep("BucketDryRunStep", BucketDryRunConfig()),
        ],
    )
