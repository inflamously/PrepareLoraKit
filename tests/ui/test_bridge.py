from pathlib import Path

import yaml

from prepare_lora_kit.project import project_registry
from prepare_lora_kit_ui.bridge import UiBridge
from prepare_lora_kit_ui.runner import PipelineJob


def test_bridge_folder_first_creates_missing_project(tmp_path, monkeypatch):
    configs_dir = tmp_path / "configs" / "projects"
    monkeypatch.setattr(project_registry._registry, "configs_dir", configs_dir)
    input_dir = tmp_path / "new-dataset"
    input_dir.mkdir()

    result = UiBridge().load_or_create_project_for_input(str(input_dir))
    data = yaml.safe_load((configs_dir / "new_dataset.yaml").read_text())

    assert result["project_name"] == "new-dataset"
    assert result["input_dir"] == str(input_dir.resolve())
    assert result["project"]["input_dir"] == str(input_dir.resolve())
    assert Path(result["output_dir"]).parts[-2:] == ("outputs", "new-dataset")
    assert data["input_dir"] == str(input_dir.resolve())


def test_bridge_folder_first_updates_existing_project_without_losing_pipeline(tmp_path, monkeypatch):
    configs_dir = tmp_path / "configs" / "projects"
    configs_dir.mkdir(parents=True)
    monkeypatch.setattr(project_registry._registry, "configs_dir", configs_dir)
    input_dir = tmp_path / "existing"
    input_dir.mkdir()
    project_path = configs_dir / "existing.yaml"
    project_path.write_text("""\
name: existing
pipeline:
  - type: QualityGateStep
    auto_only: true
  - type: CurateStep
  - type: UpscaleStep
  - type: CaptionBboxStep
  - type: VaeGateStep
  - type: AuditStep
""")

    result = UiBridge().load_or_create_project_for_input(str(input_dir))
    data = yaml.safe_load(project_path.read_text())

    assert result["project_name"] == "existing"
    assert result["project"]["input_dir"] == str(input_dir.resolve())
    assert [step["type"] for step in data["pipeline"]] == [
        "QualityGateStep",
        "CurateStep",
        "UpscaleStep",
        "CaptionBboxStep",
        "VaeGateStep",
        "AuditStep",
    ]
    assert result["project"]["steps"][0]["type"] == "ImportStep"
    assert data["pipeline"][0]["auto_only"] is True


def test_bridge_load_project_returns_saved_input_dir_and_default_output(tmp_path, monkeypatch):
    configs_dir = tmp_path / "configs" / "projects"
    configs_dir.mkdir(parents=True)
    monkeypatch.setattr(project_registry._registry, "configs_dir", configs_dir)
    input_dir = tmp_path / "saved-dataset"
    input_dir.mkdir()
    project_path = configs_dir / "saved.yaml"
    project_path.write_text(f"""\
name: saved
input_dir: {input_dir}
pipeline: []
""")

    result = UiBridge().load_project("saved")

    assert result["input_dir"] == str(input_dir)
    assert result["project"]["input_dir"] == str(input_dir)
    assert Path(result["output_dir"]).parts[-2:] == ("outputs", "saved-dataset")


def test_bridge_shutdown_cancels_active_job():
    bridge = UiBridge()
    job = PipelineJob(bridge.jobs, "active-job")
    job.set_status("running", current_step="CaptionBboxStep")
    bridge.jobs._jobs[job.id] = job
    bridge.jobs._active_job_id = job.id

    result = bridge.shutdown()

    assert result == {"cancel_requested": True}
    assert job.snapshot()["status"] == "cancelling"


def test_bridge_does_not_cancel_completed_job():
    bridge = UiBridge()
    job = PipelineJob(bridge.jobs, "completed-job")
    job.set_status("completed")
    bridge.jobs._jobs[job.id] = job

    assert bridge.cancel_job(job.id) == {"cancel_requested": False}
    assert job.snapshot()["status"] == "completed"
