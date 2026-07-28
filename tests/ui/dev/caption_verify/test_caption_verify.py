"""Tests for the caption-verify UI provider, bridge RPC and mock runtime."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PIL import Image

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit_ui.runner.interactions import UiInteractionProvider


class FakeJob:
    """Minimal PipelineJob stand-in: records the pending request, answers it."""

    def __init__(self, answer=None, on_request=None):
        self.answer = answer if answer is not None else {}
        self.on_request = on_request
        self.requests: list[tuple[str, dict]] = []
        self.cancelled = False

    def request_input(self, kind, payload):
        self.requests.append((kind, payload))
        if self.on_request is not None:
            return self.on_request(payload)
        return self.answer

    def raise_if_cancelled(self):
        if self.cancelled:
            raise CancelledRun("Run cancelled")


@pytest.fixture
def dataset(tmp_path):
    root = tmp_path / "dataset"
    root.mkdir()
    Image.new("RGB", (32, 24), "red").save(root / "one.png")
    (root / "one.txt").write_text("tok, a red cube", encoding="utf-8")
    return root


def _items(dataset):
    return [{
        "path": dataset / "one.png",
        "name": "one.png",
        "caption": "tok, a red cube",
        "caption_path": dataset / "one.txt",
    }]


def _provider(job):
    return UiInteractionProvider(job, media_base_url="http://127.0.0.1:9999/media")


# --- payload ---------------------------------------------------------------

def test_caption_verify_emits_the_expected_payload(dataset):
    job = FakeJob()
    provider = _provider(job)

    provider.caption_verify(_items(dataset))

    kind, payload = job.requests[0]
    assert kind == "caption_verify"
    assert payload["verdicts"] == ["correct", "generic", "wrong"]
    item = payload["items"][0]
    assert item["path"] == str((dataset / "one.png").resolve())
    assert item["caption"] == "tok, a red cube"
    assert item["caption_path"] == str((dataset / "one.txt").resolve())
    assert item["has_caption"] is True
    assert item["initial_verdict"] == "correct"
    assert (item["width"], item["height"]) == (32, 24)
    assert item["thumb_uri"].startswith("http://127.0.0.1:9999/media")


def test_initial_verdict_echoes_what_the_step_seeded(dataset):
    """The step reads the ledger; the provider only forwards its answer."""
    job = FakeJob()
    items = _items(dataset)
    items[0]["initial_verdict"] = "wrong"

    _provider(job).caption_verify(items)

    assert job.requests[0][1]["items"][0]["initial_verdict"] == "wrong"


def test_initial_verdict_falls_back_on_an_unknown_value(dataset):
    job = FakeJob()
    items = _items(dataset)
    items[0]["initial_verdict"] = "banana"

    _provider(job).caption_verify(items)

    assert job.requests[0][1]["items"][0]["initial_verdict"] == "correct"


def test_caption_verify_marks_blank_captions(dataset):
    (dataset / "one.txt").write_text("", encoding="utf-8")
    job = FakeJob()
    items = _items(dataset)
    items[0]["caption"] = ""

    _provider(job).caption_verify(items)

    assert job.requests[0][1]["items"][0]["has_caption"] is False


# --- answer parsing --------------------------------------------------------

def test_answer_normalizes_unknown_verdicts(dataset):
    key = str((dataset / "one.png").resolve())
    job = FakeJob(answer={"items": {key: {"verdict": "banana", "caption": "x"}}})

    result = _provider(job).caption_verify(_items(dataset))

    assert result[key]["verdict"] == "correct"


def test_answer_recomputes_edited_server_side(dataset):
    """The frontend's own 'edited' flag is never trusted."""
    key = str((dataset / "one.png").resolve())
    job = FakeJob(answer={"items": {
        key: {"verdict": "wrong", "caption": "a red cube", "edited": False},
    }})

    result = _provider(job).caption_verify(_items(dataset))

    assert result[key]["edited"] is True


def test_answer_marks_unchanged_captions_as_not_edited(dataset):
    key = str((dataset / "one.png").resolve())
    job = FakeJob(answer={"items": {
        key: {"verdict": "correct", "caption": "tok, a red cube", "edited": True},
    }})

    result = _provider(job).caption_verify(_items(dataset))

    assert result[key]["edited"] is False


@pytest.mark.parametrize("answer", [None, {}, {"items": "nope"}, "garbage"])
def test_malformed_answers_yield_no_results(dataset, answer):
    result = _provider(FakeJob(answer=answer)).caption_verify(_items(dataset))

    assert result == {}


# --- the live generation RPC ----------------------------------------------

def _generating_job(dataset, calls, result=None):
    """A job whose request_input drives the generator, like the real modal."""

    def on_request(payload):
        provider = calls["provider"]
        calls["result"] = provider.generate_caption_preview(
            str(dataset / "one.png"), "a red cube", calls.get("options") or {},
        )
        return {}

    return FakeJob(on_request=on_request)


def test_generate_returns_a_media_payload(dataset, tmp_path):
    calls: dict = {}
    job = _generating_job(dataset, calls)
    provider = calls["provider"] = _provider(job)
    rendered = tmp_path / "gen_1_000.png"
    Image.new("RGB", (8, 8), "blue").save(rendered)

    def generator(prompt, options):
        return {"path": str(rendered), "seed": 7, "elapsed_ms": 12, "steps": 4,
                "guidance": 1.0, "width": 8, "height": 8, "model_id": "mock",
                "truncated": False, "token_count": 3}

    provider.caption_verify(_items(dataset), generator=generator)

    payload = calls["result"]
    assert payload["seed"] == 7
    assert payload["caption"] == "a red cube"
    assert payload["uri"].startswith("http://127.0.0.1:9999/media")


def test_generate_forwards_the_reroll_flag_and_source_path(dataset, tmp_path):
    calls: dict = {"options": {"reroll": True}}
    job = _generating_job(dataset, calls)
    provider = calls["provider"] = _provider(job)
    seen: list[dict] = []

    def generator(prompt, options):
        seen.append(options)
        return {"path": None, "seed": 1}

    provider.caption_verify(_items(dataset), generator=generator, settings={"steps": 4})

    assert seen[0]["reroll"] is True
    assert seen[0]["source_path"] == str((dataset / "one.png").resolve())
    assert seen[0]["steps"] == 4


def test_generate_requires_an_active_request(dataset):
    provider = _provider(FakeJob())

    with pytest.raises(RuntimeError, match="No active caption verification request"):
        provider.generate_caption_preview(str(dataset / "one.png"), "prompt")


def test_generate_rejects_images_outside_the_active_batch(dataset, tmp_path):
    calls: dict = {}
    outside = tmp_path / "elsewhere.png"
    Image.new("RGB", (8, 8), "red").save(outside)

    def on_request(payload):
        with pytest.raises(RuntimeError, match="not in the active caption verification batch"):
            calls["provider"].generate_caption_preview(str(outside), "prompt")
        return {}

    provider = calls["provider"] = _provider(FakeJob(on_request=on_request))
    provider.caption_verify(_items(dataset), generator=lambda p, o: {})


@pytest.mark.parametrize("caption", ["", "   ", "x" * 5000])
def test_generate_rejects_unusable_captions(dataset, caption):
    calls: dict = {}

    def on_request(payload):
        with pytest.raises(ValueError):
            calls["provider"].generate_caption_preview(str(dataset / "one.png"), caption)
        return {}

    provider = calls["provider"] = _provider(FakeJob(on_request=on_request))
    provider.caption_verify(_items(dataset), generator=lambda p, o: {})


def test_generate_rejects_concurrent_requests(dataset):
    """A queued second render would hold a thread then draw a stale caption."""
    calls: dict = {}

    def on_request(payload):
        calls["provider"]._generate_lock.acquire()
        try:
            with pytest.raises(RuntimeError, match="already being generated"):
                calls["provider"].generate_caption_preview(
                    str(dataset / "one.png"), "prompt",
                )
        finally:
            calls["provider"]._generate_lock.release()
        return {}

    provider = calls["provider"] = _provider(FakeJob(on_request=on_request))
    provider.caption_verify(_items(dataset), generator=lambda p, o: {})


def test_generate_raises_when_the_run_is_cancelled(dataset):
    calls: dict = {}

    def on_request(payload):
        calls["provider"]._job.cancelled = True
        with pytest.raises(CancelledRun):
            calls["provider"].generate_caption_preview(str(dataset / "one.png"), "prompt")
        return {}

    provider = calls["provider"] = _provider(FakeJob(on_request=on_request))
    provider.caption_verify(_items(dataset), generator=lambda p, o: {})


def test_generator_is_cleared_after_the_review_closes(dataset):
    provider = _provider(FakeJob())

    provider.caption_verify(_items(dataset), generator=lambda p, o: {})

    assert provider._verify_generator is None
    assert provider._verify_paths == set()


def test_generator_is_cleared_even_when_the_review_raises(dataset):
    def on_request(payload):
        raise RuntimeError("modal exploded")

    provider = _provider(FakeJob(on_request=on_request))

    with pytest.raises(RuntimeError):
        provider.caption_verify(_items(dataset), generator=lambda p, o: {})

    assert provider._verify_generator is None


def test_state_lock_is_not_held_across_a_render(dataset):
    """Holding _verify_lock for a 30s render would block teardown and cancel."""
    calls: dict = {}
    observed: dict = {}

    def generator(prompt, options):
        observed["free"] = calls["provider"]._verify_lock.acquire(blocking=False)
        if observed["free"]:
            calls["provider"]._verify_lock.release()
        return {"path": None, "seed": 1}

    def on_request(payload):
        calls["provider"].generate_caption_preview(str(dataset / "one.png"), "prompt")
        return {}

    provider = calls["provider"] = _provider(FakeJob(on_request=on_request))
    provider.caption_verify(_items(dataset), generator=generator)

    assert observed["free"] is True


# --- bridge ---------------------------------------------------------------

class FakeJobs:
    def __init__(self, provider=None):
        self.provider = provider

    def active_interaction_provider(self, job_id):
        return self.provider


def _bridge(provider):
    from prepare_lora_kit_ui.bridge import UiBridge

    bridge = UiBridge.__new__(UiBridge)
    bridge.jobs = FakeJobs(provider)
    return bridge


def test_bridge_requires_an_active_provider():
    with pytest.raises(RuntimeError, match="No active UI interaction provider"):
        _bridge(None).generate_caption_preview("job-1", "/img.png", "caption")


def test_bridge_delegates_and_defaults_options_to_a_dict():
    seen: list[tuple] = []

    class Stub:
        def generate_caption_preview(self, image_path, caption, options):
            seen.append((image_path, caption, options))
            return {"ok": True}

    result = _bridge(Stub()).generate_caption_preview("job-1", "/img.png", "caption")

    assert result == {"ok": True}
    assert seen == [("/img.png", "caption", {})]


# --- mock runtime ----------------------------------------------------------

def test_mock_runtime_writes_back_edits_and_reports_verdicts(dataset, tmp_path):
    from prepare_lora_kit.invoke.mock_caption_verifier import _mock_caption_verifier

    key = str(dataset / "one.png")

    class Provider:
        def caption_verify(self, items, *, generator=None, preview_dir=None, settings=None):
            generator(items[0]["caption"], {"source_path": str(items[0]["path"])})
            return {key: {"verdict": "wrong", "caption": "a red cube"}}

    report = _mock_caption_verifier(dataset, tmp_path, interaction=Provider())

    assert report["mock_runtime"] is True
    assert (dataset / "one.txt").read_text(encoding="utf-8") == "a red cube"
    assert report["verdict_counts"]["wrong"] == 1
    assert report["statistics"]["generated"] == 1


def test_mock_renders_are_deterministic_per_prompt_and_seed(tmp_path):
    from prepare_lora_kit.invoke.mock_caption_verifier import _plate

    first = _plate("a red cube", 42).tobytes()
    again = _plate("a red cube", 42).tobytes()
    other_seed = _plate("a red cube", 43).tobytes()
    other_prompt = _plate("a blue sphere", 42).tobytes()

    assert first == again
    assert first != other_seed
    assert first != other_prompt


def test_mock_runtime_skips_cleanly_without_a_provider(dataset, tmp_path):
    from prepare_lora_kit.invoke.mock_caption_verifier import _mock_caption_verifier

    report = _mock_caption_verifier(dataset, tmp_path, interaction=None)

    assert report["skipped"] is True
    assert "provider" in report["reason"]
