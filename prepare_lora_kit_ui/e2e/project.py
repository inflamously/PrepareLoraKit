"""Project config helpers for UI end-to-end mock fixtures."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit_pipeline.configs import QualityGateConfig, ImportConfig, ScorerEntry, UpscaleConfig, CurateConfig, \
    CaptionBboxConfig, VaeGateConfig, AuditConfig, BucketPoolsCheckConfig, ExportConfig
from prepare_lora_kit.project.base import ProjectConfig, PipelineStep
from .constants import MOCK_PROJECT_NAME, QUALITY_GATE_MIN_SIDE


def mock_project(input_dir: Path) -> ProjectConfig:
    return ProjectConfig(
        name=MOCK_PROJECT_NAME,
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
                "CaptionBboxStep",
                CaptionBboxConfig(
                    caption_model_id="mock",
                    vram_tier="auto",
                    max_new_tokens=32,
                    spot_check_pct=0.0,
                ),
            ),
            PipelineStep("VaeGateStep", VaeGateConfig()),
            PipelineStep("AuditStep", AuditConfig()),
            PipelineStep("BucketPoolsCheckStep", BucketPoolsCheckConfig()),
            PipelineStep("ExportStep", ExportConfig()),
        ],
    )
