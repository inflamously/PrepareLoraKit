"""Contract tests for ``CaptionVerifierStep.run``.

No model is ever loaded: ``T2IRuntime`` is replaced wholesale. What is under
test is the orchestration contract — skip reasons, caption write-back gating,
report shape, cancellation, and the guarantee that probe renders never leak
into the working dataset.
"""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest
from PIL import Image

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.steps.caption_verifier import step as verifier_step
from prepare_lora_kit.utils import image as img_utils
from prepare_lora_kit.utils.verdict_ledger import VerdictLedger


class FakeRuntime:
    """Stands in for T2IRuntime; renders a tiny solid image per call."""

    instances: list["FakeRuntime"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.unloaded = 0
        self.calls: list[str] = []
        FakeRuntime.instances.append(self)

    def generate(self, prompt, *, seed=None, width=None, height=None,
                 steps=None, guidance=None, cancel_check=None):
        self.calls.append(prompt)
        return types.SimpleNamespace(
            image=Image.new("RGB", (8, 8), "green"),
            seed=int(seed or 0),
            prompt=prompt,
            as_dict=lambda: {
                "seed": int(seed or 0), "width": 8, "height": 8, "steps": 4,
                "guidance": 1.0, "elapsed_ms": 5, "model_id": "fake",
                "truncated": False, "token_count": 3,
            },
        )

    def unload(self):
        self.unloaded += 1

    @property
    def metadata(self):
        return {"model_id": "fake", "family": "sdxl", "loaded": True}

    @property
    def status(self):
        return {"phase": "ready", "message": "ok"}


@pytest.fixture(autouse=True)
def _patch_runtime(monkeypatch):
    FakeRuntime.instances = []
    monkeypatch.setattr(verifier_step, "T2IRuntime", FakeRuntime)
    yield


@pytest.fixture
def dataset(tmp_path):
    root = tmp_path / "dataset"
    root.mkdir()
    for name, caption in (("one", "tok, a red cube"), ("two", "tok, a blue sphere")):
        Image.new("RGB", (16, 16), "red").save(root / f"{name}.png")
        (root / f"{name}.txt").write_text(caption, encoding="utf-8")
    return root


class Provider:
    """Interaction provider stub that drives the generator then answers."""

    def __init__(self, results=None, *, generate_for=(), raises=None):
        self.results = results or {}
        self.generate_for = generate_for
        self.raises = raises
        self.received: list[dict] = []

    def caption_verify(self, items, *, generator=None, preview_dir=None, settings=None):
        self.received = items
        if self.raises:
            raise self.raises
        for item in items:
            if item["name"] in self.generate_for:
                generator(item["caption"], {"source_path": str(item["path"])})
        return self.results


def _run(dataset, tmp_path, provider, **kwargs):
    reports_dir = tmp_path / "reports"
    return verifier_step.run(
        dataset,
        output_dir=dataset,
        report_path=reports_dir / "CaptionVerifierStep_report.json",
        interaction=provider,
        **kwargs,
    )


# --- skip paths ------------------------------------------------------------

def test_run_skips_when_there_are_no_captioned_images(tmp_path):
    empty = tmp_path / "dataset"
    empty.mkdir()

    report = _run(empty, tmp_path, Provider())

    assert report["skipped"] is True
    assert report["reason"] == "no captioned images"


def test_run_skips_without_an_interaction_provider(dataset, tmp_path):
    report = _run(dataset, tmp_path, None)

    assert report["skipped"] is True
    assert "provider" in report["reason"]


def test_run_skips_when_the_provider_cannot_verify_captions(dataset, tmp_path):
    """CliInteractionProvider-shaped objects without the method must not crash."""
    report = _run(dataset, tmp_path, object())

    assert report["skipped"] is True
    assert "provider" in report["reason"]


def test_run_skips_when_the_verify_substep_is_disabled(dataset, tmp_path):
    report = _run(dataset, tmp_path, Provider(), enabled_substeps=["apply_caption_edits"])

    assert report["skipped"] is True
    assert "disabled" in report["reason"]


# --- happy path ------------------------------------------------------------

def test_run_writes_edited_captions_and_records_verdicts(dataset, tmp_path):
    provider = Provider(
        results={
            str(dataset / "one.png"): {"verdict": "wrong", "caption": "a red cube"},
            str(dataset / "two.png"): {"verdict": "correct", "caption": "tok, a blue sphere"},
        },
        generate_for=("one.png",),
    )

    report = _run(dataset, tmp_path, provider)

    assert (dataset / "one.txt").read_text(encoding="utf-8") == "a red cube"
    assert (dataset / "two.txt").read_text(encoding="utf-8") == "tok, a blue sphere"
    assert report["skipped"] is False
    assert report["verdict_counts"] == {"correct": 1, "generic": 0, "wrong": 1}
    assert report["statistics"]["captions_edited"] == 1
    assert report["statistics"]["generated"] == 1


def test_run_persists_the_report_to_disk(dataset, tmp_path):
    provider = Provider(results={str(dataset / "one.png"): {"verdict": "generic"}})

    _run(dataset, tmp_path, provider)

    saved = json.loads(
        (tmp_path / "reports" / "CaptionVerifierStep_report.json").read_text()
    )
    assert saved["verdict_counts"]["generic"] == 1


def test_unreviewed_images_appear_with_a_null_verdict(dataset, tmp_path):
    provider = Provider(results={str(dataset / "one.png"): {"verdict": "correct"}})

    report = _run(dataset, tmp_path, provider)

    verdicts = {entry["name"]: entry["verdict"] for entry in report["items"]}
    assert verdicts == {"one.png": "correct", "two.png": None}
    assert report["statistics"]["unverified"] == 1


def test_run_does_not_write_captions_when_the_apply_substep_is_disabled(dataset, tmp_path):
    provider = Provider(
        results={str(dataset / "one.png"): {"verdict": "wrong", "caption": "rewritten"}},
    )

    report = _run(dataset, tmp_path, provider, enabled_substeps=["verify_captions"])

    assert (dataset / "one.txt").read_text(encoding="utf-8") == "tok, a red cube"
    assert report["statistics"]["captions_edited"] == 0
    assert report["substeps"]["apply_caption_edits"]["enabled"] is False


# --- the verdict ledger ----------------------------------------------------
#
# The report is rebuilt from scratch every run, so it cannot carry a verdict
# into the next one. The ledger is what CaptionBboxStep later reads to decide
# which captioned images to reopen, which makes these the tests that keep the
# verify → fix loop working.

def test_run_writes_verdicts_to_the_ledger(dataset, tmp_path):
    provider = Provider(results={
        str(dataset / "one.png"): {"verdict": "wrong"},
        str(dataset / "two.png"): {"verdict": "correct"},
    })

    _run(dataset, tmp_path, provider)

    ledger = VerdictLedger(tmp_path / "reports")
    assert ledger.verdict_for(dataset / "one.png") == "wrong"
    assert ledger.verdict_for(dataset / "two.png") == "correct"
    assert ledger.is_flagged(dataset / "one.png") is True
    assert ledger.is_flagged(dataset / "two.png") is False


def test_an_image_not_re_judged_keeps_its_earlier_verdict(dataset, tmp_path):
    """A second pass that judges only one image must not wipe the other."""
    _run(dataset, tmp_path, Provider(results={
        str(dataset / "one.png"): {"verdict": "wrong"},
        str(dataset / "two.png"): {"verdict": "generic"},
    }))

    _run(dataset, tmp_path, Provider(results={
        str(dataset / "one.png"): {"verdict": "correct"},
    }))

    ledger = VerdictLedger(tmp_path / "reports")
    assert ledger.verdict_for(dataset / "one.png") == "correct"
    assert ledger.verdict_for(dataset / "two.png") == "generic"


def test_a_flag_edited_in_the_same_review_is_recorded_resolved(dataset, tmp_path):
    """flag + edit means the user already fixed it by hand.

    Leaving it flagged would send CaptionBboxStep back to overwrite the text
    they typed — the one place the app lets a human write training data.
    """
    provider = Provider(results={
        str(dataset / "one.png"): {"verdict": "wrong", "caption": "a red cube"},
    })

    _run(dataset, tmp_path, provider)

    entry = VerdictLedger(tmp_path / "reports").entry_for(dataset / "one.png")
    assert entry.verdict == "wrong"
    assert entry.resolved is True
    assert entry.caption_at_verdict == "a red cube"


def test_a_flag_without_an_edit_stays_unresolved(dataset, tmp_path):
    provider = Provider(results={str(dataset / "one.png"): {"verdict": "wrong"}})

    _run(dataset, tmp_path, provider)

    entry = VerdictLedger(tmp_path / "reports").entry_for(dataset / "one.png")
    assert entry.resolved is False
    assert entry.caption_at_verdict == "tok, a red cube"


def test_ledger_records_the_original_caption_when_edits_are_disabled(dataset, tmp_path):
    """Nothing was written, so the verdict still describes the on-disk text."""
    provider = Provider(results={
        str(dataset / "one.png"): {"verdict": "wrong", "caption": "rewritten"},
    })

    _run(dataset, tmp_path, provider, enabled_substeps=["verify_captions"])

    entry = VerdictLedger(tmp_path / "reports").entry_for(dataset / "one.png")
    assert entry.caption_at_verdict == "tok, a red cube"
    assert entry.resolved is False


def test_no_ledger_is_written_when_the_step_skips(dataset, tmp_path):
    _run(dataset, tmp_path, None)

    assert not (tmp_path / "reports" / "caption_verdicts.json").exists()


# --- artifact containment --------------------------------------------------

def test_generated_previews_never_land_in_the_working_dataset(dataset, tmp_path):
    """iter_images recurses, so a probe inside dataset/ would become training data.

    AuditStep, BucketPoolsCheckStep and ExportStep all sweep the working
    dataset; a leaked render would be exported as if a human had curated it.
    """
    before = len(img_utils.iter_images(dataset))
    provider = Provider(
        results={str(dataset / "one.png"): {"verdict": "correct"}},
        generate_for=("one.png", "two.png"),
    )

    report = _run(dataset, tmp_path, provider)

    assert report["statistics"]["generated"] == 2
    assert len(img_utils.iter_images(dataset)) == before
    previews = list((tmp_path / "reports" / "CaptionVerifierStep_previews").rglob("*.png"))
    assert len(previews) == 2


def test_keep_previews_false_removes_renders_and_their_report_paths(dataset, tmp_path):
    provider = Provider(
        results={str(dataset / "one.png"): {"verdict": "correct"}},
        generate_for=("one.png",),
    )

    report = _run(dataset, tmp_path, provider, keep_previews=False)

    previews = list((tmp_path / "reports" / "CaptionVerifierStep_previews").rglob("*.png"))
    assert previews == []
    generations = report["items"][0]["generations"]
    assert generations and generations[0]["path"] is None


def test_caption_backups_survive_preview_pruning(dataset, tmp_path):
    """Backups are recovery data for hand-typed edits, not diagnostics."""
    provider = Provider(
        results={str(dataset / "one.png"): {"verdict": "wrong", "caption": "edited"}},
    )

    _run(dataset, tmp_path, provider, keep_previews=False)

    backup = (
        tmp_path / "reports" / "CaptionVerifierStep_previews"
        / "captions_before" / "one.txt"
    )
    assert backup.read_text(encoding="utf-8") == "tok, a red cube"


# --- failure and cancellation ---------------------------------------------

def test_run_records_a_provider_failure_without_raising(dataset, tmp_path):
    provider = Provider(raises=RuntimeError("model exploded"))

    report = _run(dataset, tmp_path, provider)

    assert "model exploded" in report["reason"]
    assert report["failures"][0]["stage"] == "review"


def test_run_propagates_cancelled_run(dataset, tmp_path):
    """CancelledRun must not be swallowed by the broad failure handler."""
    provider = Provider(raises=CancelledRun("Run cancelled"))

    with pytest.raises(CancelledRun):
        _run(dataset, tmp_path, provider)


def test_run_unloads_the_runtime_even_when_the_provider_raises(dataset, tmp_path):
    provider = Provider(raises=RuntimeError("boom"))

    _run(dataset, tmp_path, provider)

    assert FakeRuntime.instances[-1].unloaded == 1


def test_run_unloads_the_runtime_on_success(dataset, tmp_path):
    _run(dataset, tmp_path, Provider())

    assert FakeRuntime.instances[-1].unloaded == 1


def test_generation_failures_are_recorded_and_surfaced(dataset, tmp_path):
    class Exploding(Provider):
        def caption_verify(self, items, *, generator=None, preview_dir=None, settings=None):
            with pytest.raises(RuntimeError):
                generator("prompt", {"source_path": str(items[0]["path"])})
            return {}

    def boom(self, *a, **kw):
        raise RuntimeError("CUDA out of memory")

    FakeRuntime.generate = boom
    try:
        report = _run(dataset, tmp_path, Exploding())
    finally:
        del FakeRuntime.generate

    assert report["statistics"]["generation_failures"] == 1
    assert "CUDA out of memory" in report["failures"][0]["error"]


# --- report shape ----------------------------------------------------------

def test_success_and_skipped_reports_share_a_top_level_key_set(dataset, tmp_path):
    """The UI report renderer must never need .get() guards."""
    empty = tmp_path / "empty"
    empty.mkdir()

    success = _run(dataset, tmp_path, Provider(results={}))
    skipped = _run(empty, tmp_path, Provider())

    assert skipped["skipped"] is True
    assert set(success) == set(skipped)


def test_report_lists_every_substep(dataset, tmp_path):
    report = _run(dataset, tmp_path, Provider())

    assert set(report["substeps"]) == {"verify_captions", "apply_caption_edits"}
