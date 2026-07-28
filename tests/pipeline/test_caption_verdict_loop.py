"""The verify → reopen → fix loop, across both steps and both mock runtimes.

The per-step tests each pick their own report path, so they cannot catch the two
steps disagreeing about *where* the ledger lives — and they derive it
differently (``target_report.parent`` vs ``_resolved_report_path(...).parent``).
These run the real invoke adapters end to end, which is the only place that
agreement is actually load-bearing.
"""
from pathlib import Path

from PIL import Image

from prepare_lora_kit import invoke
from prepare_lora_kit.utils.verdict_ledger import VerdictLedger


class _Verifier:
    """Answers the caption review with a fixed verdict per image name."""

    def __init__(self, verdicts, captions=None):
        self._verdicts = verdicts
        self._captions = captions or {}
        self.received: list[dict] = []

    def caption_verify(self, items, *, generator=None, preview_dir=None, settings=None):
        self.received = items
        answer = {}
        for item in items:
            verdict = self._verdicts.get(item["name"])
            if verdict is None:
                continue
            entry = {"verdict": verdict}
            if item["name"] in self._captions:
                entry["caption"] = self._captions[item["name"]]
            answer[str(item["path"])] = entry
        return answer


class _Annotator:
    """Captions every image the workspace is handed."""

    def __init__(self):
        self.seen: list[dict] = []

    def annotate_dataset(self, images, *, captioner=None):
        self.seen = [dict(d) for d in images]
        return {str(d["path"]): {"annotations": [], "skipped": False} for d in images}, False


def _project(tmp_path):
    """An output dir laid out the way the pipeline engine builds one."""
    out = tmp_path / "out"
    dataset = out / "dataset"
    dataset.mkdir(parents=True)
    for name in ("good.png", "bad.png"):
        Image.new("RGB", (16, 12), "blue").save(dataset / name)
    return out, dataset


def _caption(out, dataset, provider, *, force=False):
    return invoke._mock_caption(
        dataset, out, concept_token="tok", force=force, interaction=provider,
    )


def _verify(out, dataset, provider):
    return invoke._mock_caption_verifier(dataset, out, interaction=provider)


def test_a_flagged_caption_survives_into_the_annotator_and_is_fixed(tmp_path):
    out, dataset = _project(tmp_path)
    _caption(out, dataset, _Annotator())

    _verify(out, dataset, _Verifier({"bad.png": "wrong", "good.png": "correct"}))

    # The mock captioner is deterministic, so a re-caption would be
    # indistinguishable from "left alone". Stamp the file to tell them apart.
    (dataset / "bad.txt").write_text("SENTINEL", encoding="utf-8")

    # Both steps must have agreed on one location for this to be found at all.
    ledger_file = out / "reports" / "caption_verdicts.json"
    assert ledger_file.is_file()

    # A plain re-run — no --force — reopens the flagged image and only that one.
    second = _Annotator()
    _caption(out, dataset, second)
    assert [Path(d["path"]).name for d in second.seen] == ["bad.png"]
    assert second.seen[0]["verdict"] == "wrong"
    assert second.seen[0]["done"] is False

    # It was actually re-captioned, and the flag retired.
    assert (dataset / "bad.txt").read_text(encoding="utf-8") != "SENTINEL"
    assert VerdictLedger(out / "reports").is_flagged(dataset / "bad.png") is False

    # ...so a third run has nothing left to do. Without this the loop never ends.
    third = _Annotator()
    _caption(out, dataset, third)
    assert third.seen == []


def test_the_next_review_opens_on_the_remembered_verdicts(tmp_path):
    out, dataset = _project(tmp_path)
    _caption(out, dataset, _Annotator())
    _verify(out, dataset, _Verifier({"good.png": "generic"}))

    second = _Verifier({})
    _verify(out, dataset, second)

    seeded = {item["name"]: item["initial_verdict"] for item in second.received}
    assert seeded["good.png"] == "generic"
    # Never judged, so it stays on the no-op default.
    assert seeded["bad.png"] == "correct"


def test_a_caption_edited_during_the_review_is_not_reopened(tmp_path):
    """The user already fixed it by hand; the VLM must not overwrite that."""
    out, dataset = _project(tmp_path)
    _caption(out, dataset, _Annotator())

    _verify(out, dataset, _Verifier(
        {"bad.png": "wrong"}, captions={"bad.png": "a hand-written caption"},
    ))

    second = _Annotator()
    _caption(out, dataset, second)

    assert second.seen == []
    assert (dataset / "bad.txt").read_text(encoding="utf-8") == "a hand-written caption"
