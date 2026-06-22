import pytest

from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit.ui.bridge import UiBridge
from prepare_lora_kit.ui.dev_fixture import (
    MOCK_PROJECT_NAME,
    create_mock_ui_fixture,
    resolve_mock_steps,
)
from prepare_lora_kit.ui.runner import JobManager, PipelineJob
from prepare_lora_kit.utils.state import RunState


def test_resolve_mock_steps_accepts_aliases_and_all():
    assert resolve_mock_steps("s2") == ["DedupeStep"]
    assert resolve_mock_steps("2") == ["DedupeStep"]
    assert resolve_mock_steps("dedupestep") == ["DedupeStep"]
    assert resolve_mock_steps("all")[0] == "QualityGateStep"
    assert resolve_mock_steps("all")[-1] == "BucketDryRunStep"


def test_mock_fixture_generates_dataset_and_prerequisite_state(tmp_path):
    fixture = create_mock_ui_fixture("AuditStep", root=tmp_path / "mock")

    assert fixture.project.name == MOCK_PROJECT_NAME
    assert fixture.selected_steps == ["AuditStep"]
    assert len(list(fixture.input_dir.glob("*.png"))) == 4
    assert len(list((fixture.output_dir / "dataset").glob("*.png"))) == 4
    assert len(list((fixture.output_dir / "dataset").glob("*.txt"))) == 4

    state = RunState(fixture.output_dir)
    assert state.is_done("QualityGateStep")
    assert state.is_done("CaptionStep")
    assert not state.is_done("AuditStep")


def test_mock_fixture_does_not_seed_captions_before_caption_step(tmp_path):
    fixture = create_mock_ui_fixture("DedupeStep", root=tmp_path / "mock")

    assert not list((fixture.output_dir / "dataset").glob("*.txt"))
    assert RunState(fixture.output_dir).is_done("QualityGateStep")
    assert not RunState(fixture.output_dir).is_done("DedupeStep")


def test_mock_fixture_rejects_non_empty_unmarked_root(tmp_path):
    root = tmp_path / "not-dedicated"
    root.mkdir()
    (root / "input").mkdir()

    with pytest.raises(ValueError, match="Mock output root must be empty"):
        create_mock_ui_fixture("DedupeStep", root=root)


def test_bridge_exposes_in_memory_mock_project(tmp_path):
    fixture = create_mock_ui_fixture("DedupeStep", root=tmp_path / "mock")
    bridge = UiBridge(
        projects={fixture.project.name: fixture.project},
        bootstrap=fixture.bootstrap_payload(),
    )

    assert fixture.project.name in bridge.list_projects()["projects"]

    info = bridge.app_info()
    assert info["bootstrap"]["project"] == fixture.project.name

    result = bridge.load_project(fixture.project.name, str(fixture.output_dir))
    assert result["project_name"] == fixture.project.name
    assert result["input_dir"] == str(fixture.input_dir)
    assert result["output_dir"] == str(fixture.output_dir)


def test_mock_project_dedupe_runs_through_job_manager(tmp_path):
    fixture = create_mock_ui_fixture("DedupeStep", root=tmp_path / "mock")
    manager = JobManager(projects={fixture.project.name: fixture.project})
    job = PipelineJob(manager, "mock-job")

    manager._execute(
        job,
        {
            "input_dir": str(fixture.input_dir),
            "output_dir": str(fixture.output_dir),
            "project": fixture.project.name,
            "token": fixture.token,
            "force": True,
            "mock_runtime": True,
            "steps": ["DedupeStep"],
        },
    )

    snapshot = job.snapshot()
    assert snapshot["status"] == "completed"
    assert snapshot["completed_steps"] == ["DedupeStep"]
    assert (fixture.output_dir / "reports" / "DedupeStep_report.json").exists()


def test_project_yaml_can_parse_dedupe_skip_clip(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text(
        """\
name: mock
network: flux-klein-9b
pipeline:
  - type: DedupeStep
    skip_clip: true
"""
    )

    project = ProjectConfig.from_yaml(path)

    assert project.pipeline[0].config.skip_clip is True
