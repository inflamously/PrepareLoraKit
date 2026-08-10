from unittest.mock import MagicMock, patch

import pytest

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.pipeline import RunConfig, run_all, step_types
from prepare_lora_kit.pipeline.configs import (
    AuditConfig,
    BucketPoolsCheckConfig,
    CaptionBboxConfig,
    CurateConfig,
    ImportConfig,
    QualityGateConfig,
    UpscaleConfig,
    VaeGateConfig,
)
from prepare_lora_kit.pipeline.validation import validate_pipeline_selection
from prepare_lora_kit.project.base import PipelineStep, ProjectConfig
from prepare_lora_kit.project.steps import PipelineSubstep
from prepare_lora_kit.utils.state import RunState


def _project() -> ProjectConfig:
    return ProjectConfig(
        name="test",
        pipeline=[
            PipelineStep("ImportStep", ImportConfig()),
            PipelineStep("UpscaleStep", UpscaleConfig()),
            PipelineStep("QualityGateStep", QualityGateConfig(auto_only=True)),
            PipelineStep("CurateStep", CurateConfig()),
            PipelineStep("CaptionBboxStep", CaptionBboxConfig()),
            PipelineStep("VaeGateStep", VaeGateConfig()),
            PipelineStep("AuditStep", AuditConfig()),
            PipelineStep("BucketPoolsCheckStep", BucketPoolsCheckConfig()),
        ],
    )


# Derived, not spelled out: these lists were duplicated in five tests and every
# one of them had to be hand-edited the last time a step moved.
PIPELINE_STEPS = [step.type for step in _project().pipeline]


def _steps_after(step_type: str) -> list[str]:
    return PIPELINE_STEPS[PIPELINE_STEPS.index(step_type) + 1:]


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
        for step_type in PIPELINE_STEPS
    }

    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=_project(),
        concept_token="sks",
        output_dir=tmp_path / "out",
    )

    with patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", invoke_map, clear=True):
        run_all(cfg)

    assert calls == list(invoke_map)
    for invoke in invoke_map.values():
        invoke.assert_called_once()


def test_upscale_runs_before_the_quality_gate():
    """The whole point of upscale sitting second.

    QualityGate's ``min_side`` scorer rejects small images and Curate drops
    near-duplicates. Run after either of them, upscale could only ever rescue
    images that had already been deleted from the working dataset.
    """
    canonical = list(step_types())
    assert canonical.index("UpscaleStep") < canonical.index("QualityGateStep")
    assert canonical.index("UpscaleStep") < canonical.index("CurateStep")
    assert canonical.index("ImportStep") < canonical.index("UpscaleStep")


def test_pipeline_resumes_from_first_pending_step_in_order(tmp_path):
    calls = []
    output_dir = tmp_path / "out"
    state = RunState(output_dir)
    state.mark_done("ImportStep")
    state.mark_done("UpscaleStep")

    def invoke_for(step_type):
        fn = MagicMock(name=step_type)
        fn.side_effect = lambda *args, **kwargs: calls.append(step_type) or (
            {"pass": True} if step_type == "AuditStep" else None
        )
        return fn

    invoke_map = {
        step_type: invoke_for(step_type)
        for step_type in PIPELINE_STEPS
    }

    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=_project(),
        concept_token="sks",
        output_dir=output_dir,
    )

    with patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", invoke_map, clear=True):
        run_all(cfg)

    assert calls == _steps_after("UpscaleStep")
    invoke_map["ImportStep"].assert_not_called()
    invoke_map["UpscaleStep"].assert_not_called()
    assert invoke_map["CurateStep"].call_args.kwargs["enabled_substeps"] == [
        "duplicate_check",
        "clip_scan",
        "drop_images",
    ]
    assert RunState(output_dir).is_done("BucketPoolsCheckStep")


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
        for step_type in PIPELINE_STEPS
    }

    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=_project(),
        concept_token="sks",
        output_dir=output_dir,
    )

    with patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", invoke_map, clear=True):
        run_all(cfg)

    assert calls == _steps_after("ImportStep")
    invoke_map["ImportStep"].assert_not_called()


def test_pipeline_force_reimports_from_original(tmp_path):
    calls = []
    output_dir = tmp_path / "out"
    working = output_dir / "dataset"
    working.mkdir(parents=True)

    all_steps = PIPELINE_STEPS
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

    with patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", invoke_map, clear=True):
        run_all(cfg)

    # --force reset the manifest so every previously-done step re-runs, including
    # ImportStep, which re-seeds the working dataset from the original.
    assert calls == PIPELINE_STEPS
    invoke_map["ImportStep"].assert_called_once()


def test_pipeline_reruns_resume_aware_caption_without_force(tmp_path):
    # CaptionBboxStep is resume-aware: even when marked done, a plain re-run re-enters it
    # (it self-determines pending work) instead of being skipped like other steps.
    calls = []
    output_dir = tmp_path / "out"
    (output_dir / "dataset").mkdir(parents=True)
    state = RunState(output_dir)
    for step_type in PIPELINE_STEPS:
        state.mark_done(step_type)

    def invoke_for(step_type):
        fn = MagicMock(name=step_type)
        fn.side_effect = lambda *args, **kwargs: calls.append(step_type) or (
            {"pass": True} if step_type == "AuditStep" else None
        )
        return fn

    invoke_map = {step_type: invoke_for(step_type) for step_type in PIPELINE_STEPS}

    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=_project(),
        concept_token="sks",
        output_dir=output_dir,
    )

    with patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP", invoke_map, clear=True):
        run_all(cfg)

    # Only the resume-aware CaptionBboxStep re-runs; the other done steps stay skipped.
    assert calls == ["CaptionBboxStep", "VaeGateStep"]
    invoke_map["CaptionBboxStep"].assert_called_once()


def test_pipeline_does_not_mark_cancelled_step_done(tmp_path):
    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=ProjectConfig(
            name="test",
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

    with patch.dict("prepare_lora_kit.pipeline.STEP_INVOKE_MAP",
                    {"ImportStep": invoke}, clear=True), \
            pytest.raises(CancelledRun):
        run_all(cfg)

    invoke.assert_called_once()
    assert not RunState(tmp_path / "out").is_done("ImportStep")


def test_pipeline_prevalidates_enabled_substep_prerequisites(tmp_path):
    project = ProjectConfig(
        name="test",
        pipeline=[
            PipelineStep("ImportStep", ImportConfig()),
            PipelineStep(
                "QualityGateStep",
                QualityGateConfig(auto_only=False),
                substeps=[
                    PipelineSubstep("score_images", enabled=False),
                    PipelineSubstep("review_decisions", enabled=True),
                ],
            ),
        ],
    )
    cfg = RunConfig(
        dataset_dir=tmp_path / "dataset",
        project=project,
        output_dir=tmp_path / "out",
    )

    with pytest.raises(ValueError, match="review_decisions requires enabled substep score_images"):
        run_all(cfg)


def test_pipeline_prevalidates_working_dataset_for_non_import_pipeline(tmp_path):
    project = ProjectConfig(
        name="test",
        pipeline=[
            PipelineStep("ImportStep", ImportConfig()),
            PipelineStep("VaeGateStep", VaeGateConfig()),
        ],
    )
    out = tmp_path / "out"
    RunState(out).mark_done("ImportStep")

    with pytest.raises(ValueError, match="working dataset"):
        validate_pipeline_selection(project, ["VaeGateStep"], out)
