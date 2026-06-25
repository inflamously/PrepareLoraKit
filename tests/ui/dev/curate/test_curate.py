import json

import pytest

from prepare_lora_kit.ui.e2e import create_mock_ui_fixture
from prepare_lora_kit.ui.runner import JobManager, PipelineJob


def test_mock_project_curate_runs_through_job_manager(
    tmp_path, monkeypatch, recording_curate_provider
):
    import prepare_lora_kit.ui.runner as runner

    fixture = create_mock_ui_fixture("CurateStep", root=tmp_path / "mock")
    manager = JobManager(projects={fixture.project.name: fixture.project})
    job = PipelineJob(manager, "mock-job")
    monkeypatch.setattr(runner, "UiInteractionProvider", recording_curate_provider)

    manager._execute(
        job,
        {
            "input_dir": str(fixture.input_dir),
            "output_dir": str(fixture.output_dir),
            "project": fixture.project.name,
            "token": fixture.token,
            "force": True,
            "mock_runtime": True,
            "steps": ["CurateStep"],
        },
    )

    snapshot = job.snapshot()
    assert snapshot["status"] == "completed"
    assert snapshot["completed_steps"] == ["CurateStep"]
    report_path = fixture.output_dir / "reports" / "CurateStep_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    coverage_path = fixture.output_dir / "reports" / "coverage_pca.png"
    assert report_path.exists()
    assert coverage_path.exists()
    assert report["coverage_image"] == str(coverage_path)
    assert report["coverage"]["method"] == "pca"
    assert job.curate_report["coverage"]["method"] == "pca"
    assert job.curate_report_path == fixture.output_dir / "reports" / "CurateStep_report.json"


@pytest.mark.parametrize(
    ("coverage_mode", "expected_method"),
    [
        ("pca", "pca"),
        ("umap", "umap"),
    ],
)
def test_mock_project_curate_writes_requested_coverage_plot(
    tmp_path,
    monkeypatch,
    recording_curate_provider,
    coverage_mode,
    expected_method,
):
    import prepare_lora_kit.ui.runner as runner

    fixture = create_mock_ui_fixture(
        "CurateStep",
        root=tmp_path / "mock",
        curate_coverage=coverage_mode,
    )
    manager = JobManager(projects={fixture.project.name: fixture.project})
    job = PipelineJob(manager, "mock-job")
    monkeypatch.setattr(runner, "UiInteractionProvider", recording_curate_provider)

    manager._execute(
        job,
        {
            "input_dir": str(fixture.input_dir),
            "output_dir": str(fixture.output_dir),
            "project": fixture.project.name,
            "token": fixture.token,
            "force": True,
            "mock_runtime": True,
            "mock_curate_coverage": fixture.curate_coverage,
            "steps": ["CurateStep"],
        },
    )

    report_path = fixture.output_dir / "reports" / "CurateStep_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    coverage_path = fixture.output_dir / "reports" / f"coverage_{expected_method}.png"

    assert job.snapshot()["status"] == "completed"
    assert report["coverage"]["method"] == expected_method
    assert report["coverage_image"] == str(coverage_path)
    assert coverage_path.exists()
    assert job.curate_report["coverage"]["method"] == expected_method


def test_mock_project_curate_auto_uses_umap_above_threshold(
    tmp_path, monkeypatch, recording_curate_provider
):
    import prepare_lora_kit.ui.runner as runner

    fixture = create_mock_ui_fixture(
        "CurateStep",
        root=tmp_path / "mock",
        curate_coverage="umap",
    )
    initial_image_count = len(list((fixture.output_dir / "dataset").glob("*.png")))
    manager = JobManager(projects={fixture.project.name: fixture.project})
    job = PipelineJob(manager, "mock-job")
    monkeypatch.setattr(runner, "UiInteractionProvider", recording_curate_provider)

    manager._execute(
        job,
        {
            "input_dir": str(fixture.input_dir),
            "output_dir": str(fixture.output_dir),
            "project": fixture.project.name,
            "token": fixture.token,
            "force": True,
            "mock_runtime": True,
            "mock_curate_coverage": "auto",
            "steps": ["CurateStep"],
        },
    )

    report_path = fixture.output_dir / "reports" / "CurateStep_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    coverage_path = fixture.output_dir / "reports" / "coverage_umap.png"
    curate_config = next(
        step.config for step in fixture.project.pipeline if step.type == "CurateStep"
    )

    assert job.snapshot()["status"] == "completed"
    assert report["dropped_duplicates"] == []
    assert len(report["kept_images"]) == initial_image_count
    assert len(list((fixture.output_dir / "dataset").glob("*.png"))) == initial_image_count
    assert len(report["kept_images"]) > curate_config.pca_umap_switch_threshold
    assert report["coverage"]["method"] == "umap"
    assert report["coverage_image"] == str(coverage_path)
    assert coverage_path.exists()
