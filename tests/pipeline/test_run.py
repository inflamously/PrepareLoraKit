from unittest.mock import MagicMock, patch

from prepare_lora_kit.pipeline import RunConfig, run_all
from prepare_lora_kit.project.base import ProjectConfig, PipelineStep
from prepare_lora_kit.project.configs import (
    AuditConfig,
    BucketDryRunConfig,
    CaptionConfig,
    ConfigGenConfig,
    DedupeConfig,
    QualityGateConfig,
    UpscaleConfig,
    VaeGateConfig,
)


def _project() -> ProjectConfig:
    return ProjectConfig(
        name="test",
        network="flux-klein-9b",
        pipeline=[
            PipelineStep("QualityGateStep", QualityGateConfig(auto_only=True)),
            PipelineStep("DedupeStep", DedupeConfig()),
            PipelineStep("UpscaleStep", UpscaleConfig()),
            PipelineStep("VaeGateStep", VaeGateConfig()),
            PipelineStep("CaptionStep", CaptionConfig()),
            PipelineStep("AuditStep", AuditConfig()),
            PipelineStep("ConfigGenStep", ConfigGenConfig()),
            PipelineStep("BucketDryRunStep", BucketDryRunConfig()),
        ],
    )


def test_pipeline_runs_project_steps_in_order(tmp_path):
    calls = []

    def invoke_for(step_type):
        fn = MagicMock(name=step_type)
        fn.side_effect = lambda *args, **kwargs: calls.append(step_type) or (
            {"pass": True} if step_type == "AuditStep" else None
        )
        return fn

    invoke_map = {
        step_type: invoke_for(step_type)
        for step_type in [
            "QualityGateStep",
            "DedupeStep",
            "UpscaleStep",
            "VaeGateStep",
            "CaptionStep",
            "AuditStep",
            "ConfigGenStep",
            "BucketDryRunStep",
        ]
    }

    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=_project(),
        concept_token="sks",
        output_dir=tmp_path / "out",
    )

    with patch("prepare_lora_kit.networks.registry.load", return_value=MagicMock()), \
            patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", invoke_map, clear=True):
        run_all(cfg)

    assert calls == list(invoke_map)
    for step_type, invoke in invoke_map.items():
        invoke.assert_called_once()
