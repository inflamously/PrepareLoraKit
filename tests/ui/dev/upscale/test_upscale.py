import json
from pathlib import Path

from prepare_lora_kit.steps.upscale import step as upscale_step
from prepare_lora_kit_ui.e2e import create_mock_ui_fixture
from prepare_lora_kit_ui.runner import JobManager, PipelineJob


def test_mock_upscale_review_flags_and_converts_jpeg_to_png(tmp_path, monkeypatch):
    import prepare_lora_kit_ui.runner as runner

    captured = {}

    class FakeInteractionProvider:
        def __init__(self, job, media_base_url=None):
            self.job = job
            self.media_base_url = media_base_url

        def upscale_review(self, items):
            captured["items"] = items
            return {item["path"]: "upscale" for item in items}

    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)
    monkeypatch.setattr(runner, "UiInteractionProvider", FakeInteractionProvider)

    fixture = create_mock_ui_fixture("UpscaleStep", root=tmp_path / "mock")
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
            "steps": ["UpscaleStep"],
        },
    )

    assert job.snapshot()["status"] == "completed"

    # The mock project upscales with Lanczos (no SeedVR2 needed in CI). The JPEG
    # is flagged, upscaled, and converted to a clean PNG.
    items_by_name = {item["name"]: item for item in captured["items"]}
    assert items_by_name["mock_artifact_jpeg.jpg"]["planned_action"] == "upscale"
    assert items_by_name["mock_artifact_jpeg.jpg"]["is_jpeg"] is True
    assert items_by_name["mock_square.png"]["planned_action"] == "upscale"
    assert items_by_name["mock_square.png"]["is_jpeg"] is False

    dataset_dir = fixture.output_dir / "dataset"
    report = json.loads(
        (fixture.output_dir / "reports" / "UpscaleStep_report.json").read_text(encoding="utf-8")
    )
    assert {Path(entry["original"]).name for entry in report["upscaled"]} == {
        "mock_square.png",
        "mock_square_duplicate.png",
        "mock_landscape.png",
        "mock_portrait.png",
        "mock_artifact_jpeg.jpg",
    }
    # The JPEG was rewritten as a PNG with the original removed — no stray .jpg.
    assert (dataset_dir / "mock_artifact_jpeg.png").exists()
    assert not (dataset_dir / "mock_artifact_jpeg.jpg").exists()
