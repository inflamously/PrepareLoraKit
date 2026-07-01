from unittest.mock import MagicMock, patch

import pytest

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.pipeline import RunConfig, run_all
from prepare_lora_kit.project.base import ProjectConfig, PipelineStep
from prepare_lora_kit.project.configs import (
    AuditConfig,
    BucketDryRunConfig,
    CaptionConfig,
    ConfigGenConfig,
    CurateConfig,
    ImportConfig,
    QualityGateConfig,
    UpscaleConfig,
    VaeGateConfig,
)
from prepare_lora_kit.utils.state import RunState


def _project() -> ProjectConfig:
    return ProjectConfig(
        name="test",
        network="flux-klein-9b",
        pipeline=[
            PipelineStep("ImportStep", ImportConfig()),
            PipelineStep("QualityGateStep", QualityGateConfig(auto_only=True)),
            PipelineStep("CurateStep", CurateConfig()),
            PipelineStep("UpscaleStep", UpscaleConfig()),
            PipelineStep("CaptionStep", CaptionConfig()),
            PipelineStep("VaeGateStep", VaeGateConfig()),
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
            "ImportStep",
            "QualityGateStep",
            "CurateStep",
            "UpscaleStep",
            "CaptionStep",
            "VaeGateStep",
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


def test_pipeline_resumes_from_first_pending_step_in_order(tmp_path):
    calls = []
    output_dir = tmp_path / "out"
    state = RunState(output_dir)
    state.mark_done("ImportStep")
    state.mark_done("QualityGateStep")

    def invoke_for(step_type):
        fn = MagicMock(name=step_type)
        fn.side_effect = lambda *args, **kwargs: calls.append(step_type) or (
            {"pass": True} if step_type == "AuditStep" else None
        )
        return fn

    invoke_map = {
        step_type: invoke_for(step_type)
        for step_type in [
            "ImportStep",
            "QualityGateStep",
            "CurateStep",
            "UpscaleStep",
            "CaptionStep",
            "VaeGateStep",
            "AuditStep",
            "ConfigGenStep",
            "BucketDryRunStep",
        ]
    }

    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=_project(),
        concept_token="sks",
        output_dir=output_dir,
    )

    with patch("prepare_lora_kit.networks.registry.load", return_value=MagicMock()), \
            patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", invoke_map, clear=True):
        run_all(cfg)

    assert calls == [
        "CurateStep",
        "UpscaleStep",
        "CaptionStep",
        "VaeGateStep",
        "AuditStep",
        "ConfigGenStep",
        "BucketDryRunStep",
    ]
    invoke_map["ImportStep"].assert_not_called()
    invoke_map["QualityGateStep"].assert_not_called()
    assert invoke_map["CurateStep"].call_args.kwargs["enabled_substeps"] == [
        "s2_1_dupecheck",
        "s2_2_clipscan",
        "s2_3_drop_images",
    ]
    assert RunState(output_dir).is_done("BucketDryRunStep")


def test_pipeline_skips_import_for_existing_legacy_working_dataset(tmp_path):
    calls = []
    output_dir = tmp_path / "out"
    (output_dir / "dataset").mkdir(parents=True)

    def invoke_for(step_type):
        fn = MagicMock(name=step_type)
        fn.side_effect = lambda *args, **kwargs: calls.append(step_type)
        return fn

    invoke_map = {
        step_type: invoke_for(step_type)
        for step_type in [
            "ImportStep",
            "QualityGateStep",
            "CurateStep",
            "UpscaleStep",
            "CaptionStep",
            "VaeGateStep",
            "AuditStep",
            "ConfigGenStep",
            "BucketDryRunStep",
        ]
    }

    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=_project(),
        concept_token="sks",
        output_dir=output_dir,
    )

    with patch("prepare_lora_kit.networks.registry.load", return_value=MagicMock()), \
            patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", invoke_map, clear=True):
        run_all(cfg)

    assert calls == [
        "QualityGateStep",
        "CurateStep",
        "UpscaleStep",
        "CaptionStep",
        "VaeGateStep",
        "AuditStep",
        "ConfigGenStep",
        "BucketDryRunStep",
    ]
    invoke_map["ImportStep"].assert_not_called()


def test_pipeline_force_resets_state_but_keeps_working_dataset(tmp_path):
    calls = []
    output_dir = tmp_path / "out"
    working = output_dir / "dataset"
    working.mkdir(parents=True)
    # A hand-drawn bbox sidecar in the working dataset must survive a forced re-run.
    boxes = working / "plk_bbox__image__boxes.json"
    boxes.write_text("[]", encoding="utf-8")

    all_steps = [
        "ImportStep",
        "QualityGateStep",
        "CurateStep",
        "UpscaleStep",
        "CaptionStep",
        "VaeGateStep",
        "AuditStep",
        "ConfigGenStep",
        "BucketDryRunStep",
    ]
    state = RunState(output_dir)
    for step_type in all_steps:
        state.mark_done(step_type)

    def invoke_for(step_type):
        fn = MagicMock(name=step_type)
        fn.side_effect = lambda *args, **kwargs: calls.append(step_type) or (
            {"pass": True} if step_type == "AuditStep" else None
        )
        return fn

    invoke_map = {step_type: invoke_for(step_type) for step_type in all_steps}

    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=_project(),
        concept_token="sks",
        output_dir=output_dir,
        force=True,
    )

    with patch("prepare_lora_kit.networks.registry.load", return_value=MagicMock()), \
            patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", invoke_map, clear=True):
        run_all(cfg)

    # --force reset the manifest so every previously-done step re-runs, EXCEPT
    # ImportStep — it is satisfied by the existing working dataset and never
    # re-invoked, so it can't rmtree the hand-drawn boxes it holds.
    assert calls == [
        "QualityGateStep",
        "CurateStep",
        "UpscaleStep",
        "CaptionStep",
        "VaeGateStep",
        "AuditStep",
        "ConfigGenStep",
        "BucketDryRunStep",
    ]
    invoke_map["ImportStep"].assert_not_called()
    assert boxes.exists()


def test_pipeline_reruns_resume_aware_caption_without_force(tmp_path):
    # CaptionStep is resume-aware: even when marked done, a plain re-run re-enters it
    # (it self-determines pending work) instead of being skipped like other steps.
    calls = []
    output_dir = tmp_path / "out"
    (output_dir / "dataset").mkdir(parents=True)
    state = RunState(output_dir)
    for step_type in ["ImportStep", "QualityGateStep", "CurateStep", "UpscaleStep",
                      "CaptionStep", "VaeGateStep", "AuditStep", "ConfigGenStep",
                      "BucketDryRunStep"]:
        state.mark_done(step_type)

    def invoke_for(step_type):
        fn = MagicMock(name=step_type)
        fn.side_effect = lambda *args, **kwargs: calls.append(step_type) or (
            {"pass": True} if step_type == "AuditStep" else None
        )
        return fn

    invoke_map = {step_type: invoke_for(step_type) for step_type in [
        "ImportStep", "QualityGateStep", "CurateStep", "UpscaleStep", "CaptionStep",
        "VaeGateStep", "AuditStep", "ConfigGenStep", "BucketDryRunStep",
    ]}

    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=_project(),
        concept_token="sks",
        output_dir=output_dir,
    )

    with patch("prepare_lora_kit.networks.registry.load", return_value=MagicMock()), \
            patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", invoke_map, clear=True):
        run_all(cfg)

    # Only the resume-aware CaptionStep re-runs; the other done steps stay skipped.
    assert calls == ["CaptionStep"]
    invoke_map["CaptionStep"].assert_called_once()


def test_pipeline_does_not_mark_cancelled_step_done(tmp_path):
    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=ProjectConfig(
            name="test",
            network="flux-klein-9b",
            pipeline=[PipelineStep("ImportStep", ImportConfig())],
        ),
        output_dir=tmp_path / "out",
    )
    checks = 0

    def cancel_after_invoke():
        nonlocal checks
        checks += 1
        if checks >= 2:
            raise CancelledRun("Run cancelled")

    cfg.cancel_check = cancel_after_invoke
    invoke = MagicMock(return_value=None)

    with patch("prepare_lora_kit.networks.registry.load", return_value=MagicMock()), \
            patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", {"ImportStep": invoke}, clear=True), \
            pytest.raises(CancelledRun):
        run_all(cfg)

    invoke.assert_called_once()
    assert not RunState(tmp_path / "out").is_done("ImportStep")
