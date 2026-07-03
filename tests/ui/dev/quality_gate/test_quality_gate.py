import json

from prepare_lora_kit_ui.e2e import create_mock_ui_fixture
from prepare_lora_kit_ui.runner import JobManager, PipelineJob


def test_mock_project_quality_gate_runs_with_good_and_bad_images(tmp_path, monkeypatch):
    import prepare_lora_kit_ui.runner as runner

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
