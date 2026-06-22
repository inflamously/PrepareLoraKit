import json

import pytest

from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit.ui.bridge import UiBridge
from prepare_lora_kit.ui.e2e import (
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


def test_dev_fixture_module_reexports_e2e_fixture_api():
    from prepare_lora_kit.ui import dev_fixture

    assert dev_fixture.MOCK_PROJECT_NAME == MOCK_PROJECT_NAME
    assert dev_fixture.create_mock_ui_fixture is create_mock_ui_fixture
    assert dev_fixture.resolve_mock_steps is resolve_mock_steps


def test_mock_fixture_generates_dataset_and_prerequisite_state(tmp_path):
    fixture = create_mock_ui_fixture("AuditStep", root=tmp_path / "mock")

    assert fixture.project.name == MOCK_PROJECT_NAME
    assert fixture.selected_steps == ["AuditStep"]
    assert len(list(fixture.input_dir.glob("*.png"))) == 5
    assert len(list((fixture.output_dir / "dataset").glob("*.png"))) == 4
    assert len(list((fixture.output_dir / "dataset").glob("*.txt"))) == 4
    assert (fixture.input_dir / "mock_bad_too_small.png").exists()
    assert not (fixture.output_dir / "dataset" / "mock_bad_too_small.png").exists()

    state = RunState(fixture.output_dir)
    assert state.is_done("QualityGateStep")
    assert state.is_done("CaptionStep")
    assert not state.is_done("AuditStep")


def test_mock_fixture_does_not_seed_captions_before_caption_step(tmp_path):
    fixture = create_mock_ui_fixture("DedupeStep", root=tmp_path / "mock")

    assert len(list((fixture.output_dir / "dataset").glob("*.png"))) == 4
    assert not (fixture.output_dir / "dataset" / "mock_bad_too_small.png").exists()
    assert not list((fixture.output_dir / "dataset").glob("*.txt"))
    assert RunState(fixture.output_dir).is_done("QualityGateStep")
    assert not RunState(fixture.output_dir).is_done("DedupeStep")


def test_mock_quality_gate_fixture_includes_reviewable_good_and_bad_images(tmp_path):
    fixture = create_mock_ui_fixture("QualityGateStep", root=tmp_path / "mock")
    quality_config = fixture.project.pipeline[0].config

    assert len(list(fixture.input_dir.glob("*.png"))) == 5
    assert len(list((fixture.output_dir / "dataset").glob("*.png"))) == 5
    assert quality_config.auto_only is False
    assert [(s.name, s.op, s.threshold) for s in quality_config.scorers] == [
        ("min_side", "lt", 1024.0)
    ]


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


def test_mock_project_quality_gate_runs_with_good_and_bad_images(tmp_path, monkeypatch):
    import prepare_lora_kit.ui.runner as runner

    class FakeInteractionProvider:
        def __init__(self, job, media_base_url=None):
            self.job = job
            self.media_base_url = media_base_url

        def source_review(self, scored):
            return {
                str(path): "reject" if info["auto_reject"] else "keep"
                for path, info in scored
            }

    fixture = create_mock_ui_fixture("QualityGateStep", root=tmp_path / "mock")
    manager = JobManager(projects={fixture.project.name: fixture.project})
    job = PipelineJob(manager, "mock-job")
    monkeypatch.setattr(runner, "UiInteractionProvider", FakeInteractionProvider)

    manager._execute(
        job,
        {
            "input_dir": str(fixture.input_dir),
            "output_dir": str(fixture.output_dir),
            "project": fixture.project.name,
            "token": fixture.token,
            "force": True,
            "mock_runtime": True,
            "steps": ["QualityGateStep"],
        },
    )

    report_path = fixture.output_dir / "reports" / "QualityGateStep_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    bad_entry = next(
        entry
        for path, entry in report.items()
        if path.endswith("mock_bad_too_small.png")
    )

    assert job.snapshot()["status"] == "completed"
    assert {entry["decision"] for entry in report.values()} == {"keep", "reject"}
    assert bad_entry["kept"] is False
    assert "min_side" in bad_entry["reason"]
    assert not (fixture.output_dir / "dataset" / "mock_bad_too_small.png").exists()
    assert len(list((fixture.output_dir / "dataset").glob("*.png"))) == 4


def test_mock_vae_gate_decisions_apply_only_to_original_dataset_images(tmp_path):
    from prepare_lora_kit.invoke import _mock_vae_gate

    working_dir = tmp_path / "run" / "dataset"
    output_dir = tmp_path / "run"
    working_dir.mkdir(parents=True)
    first = working_dir / "first.png"
    second = working_dir / "second.png"
    make_image(first)
    make_image(second)

    class FakeInteraction:
        def vae_review(self, items):
            assert all(
                str(output_dir / "reports" / "VaeGateStep_previews") in item["views"]["vae"]
                for item in items
            )
            return {
                str(first.resolve()): "drop",
                str(second.resolve()): "replace",
            }

    report = _mock_vae_gate(working_dir, output_dir, interaction=FakeInteraction())

    assert not first.exists()
    assert second.exists()
    assert report["needs_replacement"] == [str(second)]
    assert not list(working_dir.glob("vae.png"))
    assert list((output_dir / "reports" / "VaeGateStep_previews").glob("*/vae.png"))


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


def make_image(path):
    from PIL import Image

    Image.new("RGB", (32, 24), (80, 120, 160)).save(path)
