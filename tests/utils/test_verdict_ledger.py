"""Tests for the caption verdict ledger.

The ledger is the only thing that carries a caption verdict from one pipeline
run to the next, and both CaptionVerifierStep (writer) and CaptionBboxStep
(reader) key into it by absolute image path. So the scrutiny goes to the two
ways it can silently lose work: a key that fails to match, and a malformed file
that takes a step down instead of degrading.
"""
from __future__ import annotations

import json

from prepare_lora_kit.utils.verdict_ledger import VerdictLedger


def _write_raw(reports_dir, doc) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "caption_verdicts.json").write_text(
        json.dumps(doc), encoding="utf-8",
    )


# --- loading ---------------------------------------------------------------

def test_missing_file_loads_as_an_empty_ledger(tmp_path):
    ledger = VerdictLedger(tmp_path / "reports")

    assert ledger.entry_for(tmp_path / "a.png") is None
    assert ledger.is_flagged(tmp_path / "a.png") is False


def test_corrupt_json_is_tolerated_rather_than_raising(tmp_path):
    """A diagnostic file must never take a step down."""
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "caption_verdicts.json").write_text("{not json", encoding="utf-8")

    ledger = VerdictLedger(reports)

    assert ledger.entry_for(tmp_path / "a.png") is None
    # Marked dirty on a bad read, so the next save rewrites a clean document.
    ledger.save()
    assert json.loads((reports / "caption_verdicts.json").read_text())["entries"] == {}


def test_top_level_list_is_tolerated(tmp_path):
    _write_raw(tmp_path / "reports", ["not", "a", "mapping"])

    assert VerdictLedger(tmp_path / "reports").entry_for(tmp_path / "a.png") is None


def test_unknown_verdict_drops_only_that_row(tmp_path):
    good = tmp_path / "good.png"
    bad = tmp_path / "bad.png"
    _write_raw(tmp_path / "reports", {
        "version": 1,
        "entries": {
            str(good.resolve()): {"verdict": "wrong"},
            str(bad.resolve()): {"verdict": "banana"},
        },
    })

    ledger = VerdictLedger(tmp_path / "reports")

    assert ledger.verdict_for(good) == "wrong"
    assert ledger.entry_for(bad) is None


def test_legacy_flat_document_loads_and_is_rewritten_wrapped(tmp_path):
    image = tmp_path / "a.png"
    _write_raw(tmp_path / "reports", {str(image.resolve()): {"verdict": "generic"}})

    ledger = VerdictLedger(tmp_path / "reports")
    assert ledger.verdict_for(image) == "generic"

    ledger.save()
    doc = json.loads((tmp_path / "reports" / "caption_verdicts.json").read_text())
    assert doc["version"] == 1
    assert doc["entries"][str(image.resolve())]["verdict"] == "generic"


# --- recording -------------------------------------------------------------

def test_record_merges_without_disturbing_other_entries(tmp_path):
    reports = tmp_path / "reports"
    a, b = tmp_path / "a.png", tmp_path / "b.png"

    first = VerdictLedger(reports)
    first.record(a, "wrong", caption="cap a")
    first.record(b, "generic", caption="cap b")
    first.save()
    b_stamp = VerdictLedger(reports).entry_for(b).updated_at

    second = VerdictLedger(reports)
    second.record(a, "correct", caption="cap a2")
    second.save()

    reloaded = VerdictLedger(reports)
    assert reloaded.verdict_for(a) == "correct"
    # b was not re-judged this run: verdict, caption and timestamp all survive.
    assert reloaded.verdict_for(b) == "generic"
    assert reloaded.entry_for(b).caption_at_verdict == "cap b"
    assert reloaded.entry_for(b).updated_at == b_stamp


def test_record_resets_resolved_and_refreshes_the_caption(tmp_path):
    reports = tmp_path / "reports"
    image = tmp_path / "a.png"

    ledger = VerdictLedger(reports)
    ledger.record(image, "wrong", caption="old")
    ledger.mark_resolved([image])
    assert ledger.entry_for(image).resolved is True

    ledger.record(image, "generic", caption="new")

    entry = ledger.entry_for(image)
    assert entry.resolved is False
    assert entry.caption_at_verdict == "new"


def test_record_can_store_an_already_resolved_verdict(tmp_path):
    """flag + edit in the same modal: the fix already landed, so nothing reopens."""
    image = tmp_path / "a.png"
    ledger = VerdictLedger(tmp_path / "reports")

    ledger.record(image, "wrong", caption="edited by hand", resolved=True)

    assert ledger.entry_for(image).verdict == "wrong"
    assert ledger.is_flagged(image) is False


# --- the flag predicate ----------------------------------------------------

def test_flag_predicate_matrix(tmp_path):
    ledger = VerdictLedger(tmp_path / "reports")
    generic, wrong, correct, done = (
        tmp_path / "generic.png",
        tmp_path / "wrong.png",
        tmp_path / "correct.png",
        tmp_path / "done.png",
    )
    ledger.record(generic, "generic", caption="c")
    ledger.record(wrong, "wrong", caption="c")
    ledger.record(correct, "correct", caption="c")
    ledger.record(done, "wrong", caption="c")
    ledger.mark_resolved([done])

    assert ledger.is_flagged(generic) is True
    assert ledger.is_flagged(wrong) is True
    assert ledger.is_flagged(correct) is False
    assert ledger.is_flagged(done) is False
    assert ledger.is_flagged(tmp_path / "unknown.png") is False


def test_flagged_returns_the_callers_own_path_objects(tmp_path):
    """CaptionBboxStep does `path in flagged` with its own Paths, unresolved."""
    ledger = VerdictLedger(tmp_path / "reports")
    ledger.record(tmp_path / "a.png", "wrong", caption="c")
    ledger.record(tmp_path / "b.png", "correct", caption="c")

    images = [tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"]
    flagged = ledger.flagged(images)

    assert flagged == {tmp_path / "a.png": "wrong"}
    assert images[0] in flagged


def test_verdict_for_hides_a_resolved_verdict(tmp_path):
    ledger = VerdictLedger(tmp_path / "reports")
    image = tmp_path / "a.png"
    ledger.record(image, "wrong", caption="c")
    ledger.mark_resolved([image])

    assert ledger.verdict_for(image) is None
    # ...but the entry keeps it for history.
    assert ledger.entry_for(image).verdict == "wrong"


# --- resolution ------------------------------------------------------------

def test_mark_resolved_keeps_the_verdict_and_returns_a_count(tmp_path):
    ledger = VerdictLedger(tmp_path / "reports")
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    ledger.record(a, "wrong", caption="c")
    ledger.record(b, "generic", caption="c")

    assert ledger.mark_resolved([a, b]) == 2
    assert ledger.entry_for(a).verdict == "wrong"
    assert ledger.entry_for(a).resolved is True


def test_mark_resolved_never_creates_entries(tmp_path):
    ledger = VerdictLedger(tmp_path / "reports")

    assert ledger.mark_resolved([tmp_path / "unknown.png"]) == 0
    assert ledger.entry_for(tmp_path / "unknown.png") is None


def test_mark_resolved_is_idempotent(tmp_path):
    ledger = VerdictLedger(tmp_path / "reports")
    image = tmp_path / "a.png"
    ledger.record(image, "wrong", caption="c")

    assert ledger.mark_resolved([image]) == 1
    assert ledger.mark_resolved([image]) == 0


# --- key matching ----------------------------------------------------------

def test_keys_normalize_so_an_unresolved_path_still_matches(tmp_path):
    (tmp_path / "sub").mkdir()
    ledger = VerdictLedger(tmp_path / "reports")
    ledger.record(tmp_path / "a.png", "wrong", caption="c")

    assert ledger.verdict_for(tmp_path / "sub" / ".." / "a.png") == "wrong"


def test_basename_fallback_matches_a_moved_output_dir(tmp_path):
    """The ledger survives a re-imported dataset under a different root."""
    _write_raw(tmp_path / "reports", {
        "version": 1,
        "entries": {"/somewhere/else/dataset/a.png": {"verdict": "wrong"}},
    })

    ledger = VerdictLedger(tmp_path / "reports")

    assert ledger.verdict_for(tmp_path / "dataset" / "a.png") == "wrong"


def test_basename_fallback_refuses_an_ambiguous_name(tmp_path):
    """Mirrored subdirs can hold two `a.png`; guessing would flag the wrong one."""
    _write_raw(tmp_path / "reports", {
        "version": 1,
        "entries": {
            "/elsewhere/one/a.png": {"verdict": "wrong"},
            "/elsewhere/two/a.png": {"verdict": "generic"},
        },
    })

    ledger = VerdictLedger(tmp_path / "reports")

    assert ledger.verdict_for(tmp_path / "a.png") is None


# --- persistence -----------------------------------------------------------

def test_save_is_a_no_op_when_nothing_changed(tmp_path):
    reports = tmp_path / "reports"
    VerdictLedger(reports).save()

    assert not (reports / "caption_verdicts.json").exists()


def test_save_leaves_no_temp_file_behind(tmp_path):
    reports = tmp_path / "reports"
    ledger = VerdictLedger(reports)
    ledger.record(tmp_path / "a.png", "wrong", caption="c")
    ledger.save()

    assert [p.name for p in reports.iterdir()] == ["caption_verdicts.json"]


def test_save_creates_the_reports_dir(tmp_path):
    reports = tmp_path / "nested" / "reports"
    ledger = VerdictLedger(reports)
    ledger.record(tmp_path / "a.png", "wrong", caption="c")
    ledger.save()

    assert (reports / "caption_verdicts.json").is_file()
