"""Run-state manifest reads, especially the ones the UI badges are built from."""
from prepare_lora_kit.utils.state import RunState


def test_substep_that_never_ran_is_pending_when_the_parent_tracks_substeps(tmp_path):
    state = RunState(tmp_path)
    state.mark_substep_done("CurateStep", "duplicate_check")
    state.mark_done("CurateStep", {"enabled_substeps": ["duplicate_check"]})

    assert state.get_substep("CurateStep", "duplicate_check")["status"] == "done"
    assert state.get_substep("CurateStep", "clip_scan") == {}
    assert state.get_substep("CurateStep", "drop_images") == {}


def test_legacy_record_without_a_substeps_map_still_inherits_the_parent_status(tmp_path):
    state = RunState(tmp_path)
    state.mark_done("CurateStep")

    assert state.get_substep("CurateStep", "clip_scan") == {
        "status": "done",
        "legacy_parent_done": True,
    }


def test_legacy_skipped_record_without_a_substeps_map_inherits_the_reason(tmp_path):
    state = RunState(tmp_path)
    state.mark_skipped("CurateStep", "no images")

    assert state.get_substep("CurateStep", "clip_scan") == {
        "status": "skipped",
        "reason": "no images",
    }


def test_skipped_substeps_are_reported_as_skipped(tmp_path):
    state = RunState(tmp_path)
    state.mark_substep_skipped("CurateStep", "clip_scan", "no images")
    state.mark_done("CurateStep", {"enabled_substeps": ["clip_scan"]})

    assert state.get_substep("CurateStep", "clip_scan") == {
        "status": "skipped",
        "reason": "no images",
    }
