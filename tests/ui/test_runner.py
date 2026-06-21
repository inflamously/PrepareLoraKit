import pytest
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import urlopen

from prepare_lora_kit.cli.ui import _static_server
from prepare_lora_kit.project.base import ProjectConfig, PipelineStep
from prepare_lora_kit.project.configs import (
    AuditConfig,
    CaptionConfig,
    ConfigGenConfig,
    QualityGateConfig,
)
from prepare_lora_kit.ui.runner import (
    JobManager,
    PipelineJob,
    _LogStream,
    _image_payload,
    project_payload,
)
from prepare_lora_kit.utils.state import RunState


def _project() -> ProjectConfig:
    return ProjectConfig(
        name="test",
        network="flux-klein-9b",
        pipeline=[
            PipelineStep("QualityGateStep", QualityGateConfig(auto_only=True)),
            PipelineStep("CaptionStep", CaptionConfig()),
            PipelineStep("AuditStep", AuditConfig()),
            PipelineStep("ConfigGenStep", ConfigGenConfig()),
        ],
    )


def test_validate_selection_requires_caption_for_audit(tmp_path):
    manager = JobManager()

    with pytest.raises(ValueError, match="AuditStep requires"):
        manager._validate_selection(_project(), ["AuditStep"], tmp_path / "out")


def test_validate_selection_accepts_completed_prerequisite(tmp_path):
    out = tmp_path / "out"
    (out / "dataset").mkdir(parents=True)
    RunState(out).mark_done("CaptionStep")

    manager = JobManager()
    manager._validate_selection(_project(), ["AuditStep"], out)


def test_project_payload_includes_run_state(tmp_path):
    out = tmp_path / "out"
    RunState(out).mark_done("QualityGateStep")

    payload = project_payload(_project(), out)

    statuses = {step["type"]: step["status"] for step in payload["steps"]}
    assert statuses["QualityGateStep"] == "done"
    assert statuses["CaptionStep"] == "pending"


def test_image_payload_uses_media_endpoint_when_available(tmp_path):
    image = tmp_path / "source image.png"

    payload = _image_payload(image, "http://127.0.0.1:1234/media")

    parsed = urlparse(payload["uri"])
    assert parsed.scheme == "http"
    assert parsed.netloc == "127.0.0.1:1234"
    assert parsed.path == "/media"
    assert parse_qs(parsed.query)["path"] == [str(image.resolve())]


def test_static_server_serves_local_image_media(tmp_path):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    image = tmp_path / "preview.png"
    image.write_bytes(b"png-bytes")
    server = _static_server(static_dir)

    try:
        host, port = server.server_address
        media_url = (
            f"http://{host}:{port}/media?"
            f"path={quote(str(image.resolve()), safe='')}"
        )
        with urlopen(media_url, timeout=2) as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "image/png"
            assert response.read() == b"png-bytes"
    finally:
        server.shutdown()
        server.server_close()


def test_log_stream_accepts_unicode_output():
    job = PipelineJob(JobManager(), "test-job")
    stream = _LogStream(job)

    assert stream.encoding == "utf-8"
    assert stream.errors == "replace"
    assert not stream.isatty()

    stream.write("Saved \u2192 output \u2713\n")

    assert job.snapshot()["logs"] == ["Saved \u2192 output \u2713"]


def test_log_stream_strips_ansi_escape_sequences():
    job = PipelineJob(JobManager(), "test-job")
    stream = _LogStream(job)

    stream.write("\x1b[92mStep \x1b[1;36m4\x1b[0m: VAE\x1b[0m\n")

    assert job.snapshot()["logs"] == ["Step 4: VAE"]


def test_ui_job_uses_plain_rich_console(monkeypatch):
    manager = JobManager()
    job = PipelineJob(manager, "test-job")

    def fake_execute(job_arg, request):
        from prepare_lora_kit.utils import report as rpt

        rpt.step_header(4, "VAE Reconstruction Gate")
        rpt.info("Loading VAE from black-forest-labs/FLUX.2-klein-base-9B ...")
        print("\x1b[31mexternal framework warning\x1b[0m")

    monkeypatch.setattr(manager, "_execute", fake_execute)

    manager._run_job(job, {})

    logs = job.snapshot()["logs"]
    assert all("\x1b" not in line for line in logs)
    assert any("Step 4: VAE Reconstruction Gate" in line for line in logs)
    assert "external framework warning" in logs


def test_cancel_updates_visible_job_status():
    job = PipelineJob(JobManager(), "test-job")
    job.set_status("running", current_step="CaptionStep")

    job.cancel()

    snapshot = job.snapshot()
    assert snapshot["cancel_requested"] is True
    assert snapshot["status"] == "cancelling"
    assert snapshot["current_step"] == "CaptionStep"
