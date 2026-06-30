import threading
import time
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import ProxyHandler, build_opener

from PIL import Image
import pytest

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.cli.ui import _static_server
from prepare_lora_kit.project.base import ProjectConfig, PipelineStep
from prepare_lora_kit.project.configs import (
    AuditConfig,
    CaptionConfig,
    ConfigGenConfig,
    CurateConfig,
    ImportConfig,
    QualityGateConfig,
    UpscaleConfig,
    VaeGateConfig,
)
from prepare_lora_kit.ui.runner import (
    JobManager,
    PipelineJob,
    UiInteractionProvider,
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
            PipelineStep("ImportStep", ImportConfig()),
            PipelineStep("QualityGateStep", QualityGateConfig(auto_only=True)),
            PipelineStep("CurateStep", CurateConfig()),
            PipelineStep("UpscaleStep", UpscaleConfig()),
            PipelineStep("CaptionStep", CaptionConfig()),
            PipelineStep("VaeGateStep", VaeGateConfig()),
            PipelineStep("AuditStep", AuditConfig()),
            PipelineStep("ConfigGenStep", ConfigGenConfig()),
        ],
    )


def _active_step_types() -> list[str]:
    return [
        "ImportStep",
        "QualityGateStep",
        "CurateStep",
        "CaptionStep",
        "VaeGateStep",
        "AuditStep",
        "ConfigGenStep",
    ]


def _run_request(tmp_path, output_dir, *, force: bool = False) -> dict:
    return {
        "input_dir": str(tmp_path / "input"),
        "output_dir": str(output_dir),
        "project": "test",
        "token": "sks",
        "force": force,
        "steps": _active_step_types(),
        "substeps": {},
    }


def _invoke_map(calls: list[str]) -> dict[str, MagicMock]:
    invokes = {}
    for step_type in _active_step_types():
        invoke = MagicMock(name=step_type)
        def side_effect(*args, _step_type=step_type, **kwargs):
            calls.append(_step_type)
            return {"pass": True} if _step_type == "AuditStep" else None
        invoke.side_effect = side_effect
        invokes[step_type] = invoke
    return invokes


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


def test_validate_selection_requires_import_for_quality_gate(tmp_path):
    manager = JobManager()

    with pytest.raises(ValueError, match="QualityGateStep requires"):
        manager._validate_selection(_project(), ["QualityGateStep"], tmp_path / "out")


def test_validate_selection_accepts_existing_dataset_for_import_prerequisite(tmp_path):
    out = tmp_path / "out"
    (out / "dataset").mkdir(parents=True)

    manager = JobManager()
    manager._validate_selection(_project(), ["QualityGateStep"], out)


def test_validate_selection_allows_caption_without_optional_upscale_when_curate_done(tmp_path):
    out = tmp_path / "out"
    (out / "dataset").mkdir(parents=True)
    state = RunState(out)
    state.mark_done("ImportStep")
    state.mark_done("QualityGateStep")
    state.mark_done("CurateStep")

    manager = JobManager()
    manager._validate_selection(_project(), ["CaptionStep"], out)


def test_project_payload_includes_run_state(tmp_path):
    out = tmp_path / "out"
    RunState(out).mark_done("ImportStep")
    RunState(out).mark_done("QualityGateStep")

    payload = project_payload(_project(), out)

    statuses = {step["type"]: step["status"] for step in payload["steps"]}
    assert statuses["ImportStep"] == "done"
    assert statuses["QualityGateStep"] == "done"
    assert statuses["CaptionStep"] == "pending"


def test_project_payload_includes_optional_step_metadata(tmp_path):
    payload = project_payload(_project(), tmp_path / "out")
    optional = {step["type"]: step["optional"] for step in payload["steps"]}

    assert optional["UpscaleStep"] is True
    assert optional["VaeGateStep"] is False


def test_project_payload_includes_substeps(tmp_path):
    payload = project_payload(_project(), tmp_path / "out")
    substeps = {step["type"]: step["substeps"] for step in payload["steps"]}

    assert [substep["id"] for substep in substeps["CurateStep"]] == [
        "s2_1_dupecheck",
        "s2_2_clipscan",
        "s2_3_drop_images",
    ]


def _project_with_input(input_dir) -> ProjectConfig:
    project = _project()
    project.input_dir = str(input_dir)
    return project


def _png(path, size=(4000, 4000)):
    Image.new("RGB", size, "red").save(path)


def test_project_payload_flags_upscale_attention_for_undersized_input(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _png(input_dir / "small.png", (1000, 1000))

    payload = project_payload(_project_with_input(input_dir), tmp_path / "out")
    steps = {step["type"]: step for step in payload["steps"]}

    assert steps["UpscaleStep"]["needs_attention"] is True
    assert steps["UpscaleStep"]["attention"]["undersized"] == 1
    # Only the UpscaleStep is data-driven today; others carry no attention flag.
    assert "needs_attention" not in steps["CurateStep"]


def test_project_payload_no_attention_for_clean_dataset(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _png(input_dir / "big.png", (4000, 4000))

    payload = project_payload(_project_with_input(input_dir), tmp_path / "out")
    upscale = next(s for s in payload["steps"] if s["type"] == "UpscaleStep")

    assert upscale["needs_attention"] is False


def test_project_payload_prefers_working_dataset_over_input(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _png(input_dir / "small.png", (1000, 1000))  # input still has a small image

    out = tmp_path / "out"
    working = out / "dataset"
    working.mkdir(parents=True)
    _png(working / "done.png", (4000, 4000))  # working dataset is already clean

    payload = project_payload(_project_with_input(input_dir), out)
    upscale = next(s for s in payload["steps"] if s["type"] == "UpscaleStep")

    # The working dataset (post-run) wins, so the glow self-clears.
    assert upscale["needs_attention"] is False


def test_validate_selection_rejects_substep_without_local_prerequisite(tmp_path):
    manager = JobManager()

    with pytest.raises(ValueError, match="s1_2_decide requires"):
        manager._validate_selection(
            _project(),
            ["ImportStep", "QualityGateStep"],
            tmp_path / "out",
            {"ImportStep": ["s0_import"], "QualityGateStep": ["s1_2_decide"]},
        )


def test_resolve_selected_substeps_accepts_request_override(tmp_path):
    manager = JobManager()

    resolved = manager._resolve_selected_substeps(
        _project(),
        ["CurateStep"],
        {"CurateStep": ["s2_1_dupecheck", "s2_3_drop_images"]},
    )

    assert resolved["CurateStep"] == ["s2_1_dupecheck", "s2_3_drop_images"]


def test_ui_run_starts_at_first_pending_active_step(tmp_path):
    out = tmp_path / "out"
    state = RunState(out)
    state.mark_done("ImportStep")
    state.mark_done("QualityGateStep")
    calls: list[str] = []
    invoke_map = _invoke_map(calls)
    manager = JobManager(projects={"test": _project()})
    job = PipelineJob(manager, "test-job")

    with patch("prepare_lora_kit.networks.registry.load", return_value=MagicMock()), \
            patch.dict("prepare_lora_kit.ui.runner.STEP_INVOKE_MAP", invoke_map, clear=True):
        manager._execute(job, _run_request(tmp_path, out))

    assert calls == ["CurateStep", "CaptionStep", "VaeGateStep", "AuditStep", "ConfigGenStep"]
    assert job.snapshot()["skipped_steps"] == ["ImportStep", "QualityGateStep"]
    assert RunState(out).is_done("ConfigGenStep")


def test_ui_force_run_starts_active_pipeline_from_beginning(tmp_path):
    out = tmp_path / "out"
    state = RunState(out)
    state.mark_done("ImportStep")
    state.mark_done("QualityGateStep")
    calls: list[str] = []
    invoke_map = _invoke_map(calls)
    manager = JobManager(projects={"test": _project()})
    job = PipelineJob(manager, "test-job")

    with patch("prepare_lora_kit.networks.registry.load", return_value=MagicMock()), \
            patch.dict("prepare_lora_kit.ui.runner.STEP_INVOKE_MAP", invoke_map, clear=True):
        manager._execute(job, _run_request(tmp_path, out, force=True))

    assert calls == _active_step_types()
    assert job.snapshot()["skipped_steps"] == []


def _wait_for_pending(job, kind, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        pending = job.snapshot()["pending_input"]
        if pending and pending["kind"] == kind:
            return pending
        time.sleep(0.02)
    raise AssertionError(f"pending input {kind!r} not seen within {timeout}s")


def test_ui_run_pauses_for_step_config_and_applies_overrides(tmp_path):
    out = tmp_path / "out"
    project = ProjectConfig(
        name="test",
        network="flux-klein-9b",
        pipeline=[
            PipelineStep("ImportStep", ImportConfig()),
            PipelineStep("QualityGateStep", QualityGateConfig(auto_only=False)),
        ],
    )
    captured: dict[str, object] = {}
    invoke_map: dict[str, MagicMock] = {}
    for step_type in ("ImportStep", "QualityGateStep"):
        def side_effect(working_dir, output_dir, cfg, *args, _t=step_type, **kwargs):
            captured[_t] = cfg
            return None
        invoke_map[step_type] = MagicMock(name=step_type, side_effect=side_effect)

    manager = JobManager(projects={"test": project})
    job = PipelineJob(manager, "test-job")
    request = _run_request(tmp_path, out)
    request["steps"] = ["ImportStep", "QualityGateStep"]
    request["pause_for_config"] = True

    errors: list[Exception] = []

    def run():
        try:
            with patch("prepare_lora_kit.networks.registry.load", return_value=MagicMock()), \
                    patch.dict("prepare_lora_kit.ui.runner.STEP_INVOKE_MAP", invoke_map, clear=True):
                manager._execute(job, request)
        except Exception as exc:  # pragma: no cover - surfaced via assertion
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        pending = _wait_for_pending(job, "step_config")
        assert pending["payload"]["step_type"] == "QualityGateStep"
        assert any(f["name"] == "auto_only" for f in pending["payload"]["fields"])
        assert job.submit_input(pending["id"], {"overrides": {"auto_only": True}})
    finally:
        thread.join(timeout=5)

    assert not errors
    assert not thread.is_alive()
    # ImportStep has no schema, so only QualityGateStep paused; the override applied.
    assert captured["QualityGateStep"].auto_only is True


def test_validate_selection_rejects_deactivated_unmet_prerequisite(tmp_path):
    manager = JobManager()

    with pytest.raises(ValueError, match="CurateStep requires"):
        manager._validate_selection(
            _project(),
            ["ImportStep", "CurateStep"],
            tmp_path / "out",
        )


def test_ui_run_failure_stops_before_downstream_steps(tmp_path):
    out = tmp_path / "out"
    calls: list[str] = []
    invoke_map = _invoke_map(calls)

    def fail_quality_gate(*args, **kwargs):
        calls.append("QualityGateStep")
        raise RuntimeError("quality failed")

    invoke_map["QualityGateStep"].side_effect = fail_quality_gate
    manager = JobManager(projects={"test": _project()})
    job = PipelineJob(manager, "test-job")
    request = _run_request(tmp_path, out)
    request["steps"] = ["ImportStep", "QualityGateStep", "CurateStep"]

    with patch("prepare_lora_kit.networks.registry.load", return_value=MagicMock()), \
            patch.dict("prepare_lora_kit.ui.runner.STEP_INVOKE_MAP", invoke_map, clear=True), \
            pytest.raises(RuntimeError, match="quality failed"):
        manager._execute(job, request)

    assert calls == ["ImportStep", "QualityGateStep"]
    run_state = RunState(out)
    assert run_state.is_done("ImportStep")
    assert not run_state.is_done("QualityGateStep")
    assert not run_state.is_done("CurateStep")


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
        # Bypass any system/env proxy so the loopback request isn't routed
        # through a proxy (which silently times out on some Windows setups).
        opener = build_opener(ProxyHandler({}))
        with opener.open(media_url, timeout=2) as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "image/png"
            assert response.read() == b"png-bytes"
    finally:
        server.shutdown()
        server.server_close()


def test_static_server_uses_fast_shutdown_thread_settings(tmp_path):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    server = _static_server(static_dir)

    try:
        assert server.daemon_threads is True
        assert server.block_on_close is False
    finally:
        server.shutdown()
        server.server_close()


def test_ui_interaction_provider_emits_vae_review_payload(tmp_path):
    original = tmp_path / "input.png"
    vae = tmp_path / "vae.png"
    diff = tmp_path / "diff.png"
    hard = tmp_path / "hard.png"
    for path in [original, vae, diff, hard]:
        path.write_bytes(b"png")

    class FakeJob:
        def request_input(self, kind, payload):
            self.kind = kind
            self.payload = payload
            return {"decisions": {payload["items"][0]["path"]: "drop"}}

    from prepare_lora_kit.ui.runner import UiInteractionProvider

    job = FakeJob()
    provider = UiInteractionProvider(job, media_base_url="http://127.0.0.1:9999/media")

    decisions = provider.vae_review([
        {
            "path": str(original),
            "name": original.name,
            "width": 32,
            "height": 24,
            "hf_loss": 0.25,
            "threshold": 0.2,
            "diff_threshold": 12.0,
            "flagged": True,
            "initial_decision": "replace",
            "views": {
                "original": str(original),
                "vae": str(vae),
                "diff": str(diff),
                "hard": str(hard),
            },
        }
    ])

    item = job.payload["items"][0]
    assert job.kind == "vae_review"
    assert item["path"] == str(original.resolve())
    assert set(item["views"]) == {"original", "vae", "diff", "hard"}
    assert item["views"]["hard"]["uri"].startswith("http://127.0.0.1:9999/media")
    assert decisions == {str(original.resolve()): "drop"}


def test_ui_interaction_provider_emits_curate_details_payload(tmp_path):
    coverage = tmp_path / "coverage_umap.png"
    coverage.write_bytes(b"png")
    report = {
        "duplicate_pairs": [("a.png", "b.png", 4)],
        "dropped_duplicates": ["b.png"],
        "kept_images": ["a.png", "c.png"],
        "coverage_image": str(coverage),
        "coverage": {
            "method": "umap",
            "preprocess": "pca",
            "pca_components": 50,
        },
    }
    report_path = tmp_path / "CurateStep_report.json"

    class FakeJob:
        def request_input(self, kind, payload):
            self.kind = kind
            self.payload = payload
            return {"confirmed": True}

    from prepare_lora_kit.ui.runner import UiInteractionProvider

    job = FakeJob()
    provider = UiInteractionProvider(job, media_base_url="http://127.0.0.1:9999/media")

    assert provider.curate_details(report, report_path) is True

    assert job.kind == "curate_details"
    assert job.payload["report_path"] == str(report_path.resolve())
    assert job.payload["coverage_image"]["uri"].startswith("http://127.0.0.1:9999/media")
    assert job.payload["coverage_method"] == "umap"
    assert job.payload["coverage"]["pca_components"] == 50
    assert job.payload["summary"] == {
        "kept_images": 2,
        "duplicate_pairs": 1,
        "dropped_duplicates": 1,
    }


def test_ui_interaction_provider_resolves_coverage_points_to_media_uris(tmp_path):
    coverage = tmp_path / "coverage_pca.png"
    coverage.write_bytes(b"png")
    point_a = tmp_path / "a.png"
    point_a.write_bytes(b"png")
    missing = tmp_path / "missing.png"
    report = {
        "kept_images": ["a.png"],
        "coverage_image": str(coverage),
        "coverage": {
            "method": "pca",
            "pca_components": 2,
            "points": [
                {"path": str(point_a), "x_pct": 12.5, "y_pct": 87.25},
                {"path": str(missing), "x_pct": 50.0, "y_pct": 50.0},
            ],
        },
    }
    report_path = tmp_path / "CurateStep_report.json"

    class FakeJob:
        def request_input(self, kind, payload):
            self.kind = kind
            self.payload = payload
            return {"confirmed": True}

    from prepare_lora_kit.ui.runner import UiInteractionProvider

    job = FakeJob()
    provider = UiInteractionProvider(job, media_base_url="http://127.0.0.1:9999/media")

    assert provider.curate_details(report, report_path) is True

    points = job.payload["coverage"]["points"]
    assert len(points) == 1
    assert points[0]["uri"].startswith("http://127.0.0.1:9999/media")
    assert points[0]["name"] == "a.png"
    assert points[0]["x_pct"] == 12.5
    assert points[0]["y_pct"] == 87.25


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


def test_cancelled_run_sets_clean_cancelled_status_without_traceback(monkeypatch):
    manager = JobManager()
    job = PipelineJob(manager, "test-job")

    def fake_execute(job_arg, request):
        raise CancelledRun("Run cancelled")

    monkeypatch.setattr(manager, "_execute", fake_execute)

    manager._run_job(job, {})

    snapshot = job.snapshot()
    assert snapshot["status"] == "cancelled"
    assert snapshot["error"] == "Run cancelled"
    assert not any("Traceback" in line for line in snapshot["logs"])


def test_cancel_updates_visible_job_status():
    job = PipelineJob(JobManager(), "test-job")
    job.set_status("running", current_step="CaptionStep")

    job.cancel()

    snapshot = job.snapshot()
    assert snapshot["cancel_requested"] is True
    assert snapshot["status"] == "cancelling"
    assert snapshot["current_step"] == "CaptionStep"


def test_job_snapshot_includes_caption_status():
    job = PipelineJob(JobManager(), "test-job")

    job.set_caption_status({
        "phase": "loading",
        "message": "Loading caption model fake/model",
        "model_id": "fake/model",
    })

    snapshot = job.snapshot()
    assert snapshot["caption_status"]["phase"] == "loading"
    assert snapshot["caption_status"]["model_id"] == "fake/model"


def test_cancel_active_marks_active_job_cancelling():
    manager = JobManager()
    job = PipelineJob(manager, "test-job")
    job.set_status("running", current_step="CaptionStep")
    manager._jobs[job.id] = job
    manager._active_job_id = job.id

    assert manager.cancel_active() is True

    snapshot = job.snapshot()
    assert snapshot["cancel_requested"] is True
    assert snapshot["status"] == "cancelling"


def test_caption_region_normalizes_box_and_crops_active_image(tmp_path):
    image_path = tmp_path / "active.png"
    Image.new("RGB", (20, 10), "blue").save(image_path)
    job = PipelineJob(JobManager(), "test-job")
    provider = UiInteractionProvider(job)
    captured = {}

    def captioner(crop, metadata):
        captured["size"] = crop.size
        captured["metadata"] = metadata
        return {"caption": " cropped subject "}

    provider._captioner = captioner
    provider._batch_paths = {image_path.resolve()}

    result = provider.caption_region(
        str(image_path),
        {"x1": 1.4, "y1": 0.8, "x2": 0.25, "y2": -0.2},
    )

    assert result == {"caption": "cropped subject"}
    assert captured["size"] == (15, 8)
    assert captured["metadata"]["source_path"] == str(image_path.resolve())


def test_caption_region_rejects_image_outside_batch(tmp_path):
    image_path = tmp_path / "active.png"
    Image.new("RGB", (20, 10), "blue").save(image_path)
    job = PipelineJob(JobManager(), "test-job")
    provider = UiInteractionProvider(job)
    provider._captioner = lambda crop, metadata: {"caption": "x"}
    provider._batch_paths = {image_path.resolve()}

    with pytest.raises(RuntimeError, match="not in the active annotation batch"):
        provider.caption_region(
            str(tmp_path / "other.png"),
            {"x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5},
        )


def test_annotate_dataset_sends_batch_and_parses_decisions(tmp_path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    Image.new("RGB", (8, 8), "blue").save(a)
    Image.new("RGB", (8, 8), "red").save(b)
    job = PipelineJob(JobManager(), "batch-job")
    provider = UiInteractionProvider(job)

    captured = {}

    def fake_request_input(kind, payload):
        captured["kind"] = kind
        captured["payload"] = payload
        # While paused, region captioning is allowed for any batch image.
        captured["batch_paths"] = set(provider._batch_paths)
        return {
            "images": {
                str(a): {"annotations": [{"x1": 0, "y1": 0, "x2": 1, "y2": 1, "label": "cat"}],
                         "skipped": False},
                str(b): {"annotations": [], "skipped": True},
            },
            "skip_all": True,
        }

    job.request_input = fake_request_input  # type: ignore[assignment]

    descriptors = [
        {"path": a, "name": "a.png", "annotations": [], "done": False},
        {"path": b, "name": "b.png",
         "annotations": [{"x1": 0.1, "y1": 0.1, "x2": 0.4, "y2": 0.4, "label": "old"}],
         "done": True},
    ]
    decisions, skip_all = provider.annotate_dataset(descriptors, captioner=lambda *a, **k: {})

    assert captured["kind"] == "bbox_annotation"
    assert {item["name"] for item in captured["payload"]["images"]} == {"a.png", "b.png"}
    # Reloaded boxes + done flag travel to the UI.
    b_item = next(i for i in captured["payload"]["images"] if i["name"] == "b.png")
    assert b_item["done"] is True
    assert b_item["annotations"][0]["label"] == "old"
    assert captured["batch_paths"] == {a.resolve(), b.resolve()}
    # Cleared again after the interaction.
    assert provider._batch_paths == set()

    assert skip_all is True
    assert decisions[str(a)] == {
        "annotations": [{"x1": 0, "y1": 0, "x2": 1, "y2": 1, "label": "cat"}],
        "skipped": False,
    }
    assert decisions[str(b)] == {"annotations": [], "skipped": True}
