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
            PipelineStep("CurateStep", CurateConfig(skip_clip=True)),
            PipelineStep(
                "UpscaleStep",
                UpscaleConfig(upscale_target=1664, upscale_model="lanczos"),
            ),
            PipelineStep("VaeGateStep", VaeGateConfig()),
            PipelineStep(
                "CaptionStep",
                CaptionConfig(
                    qwen_model_id="mock",
                    vram_tier="auto",
                    max_new_tokens=32,
                    spot_check_pct=0.0,
                ),
            ),
            PipelineStep("AuditStep", AuditConfig()),
            PipelineStep("ConfigGenStep", ConfigGenConfig()),
            PipelineStep("BucketDryRunStep", BucketDryRunConfig()),
        ],
    )
