"""Tests for run selection and the Rich views of a benchmark."""
import asyncio

import pytest
from rich.console import Console

from prepare_lora_kit.caption_bench import store
from prepare_lora_kit.caption_bench.render import diff_text, render_case, select_runs
from prepare_lora_kit.caption_bench.store import BenchRun, CaseResult
from prepare_lora_kit.caption_bench.suite import BenchSuite


def _run(stamp, variant, caption, **result):
    return BenchRun(
        run_id=store.make_run_id(store.parse_timestamp(stamp), variant),
        variant=variant, suite="tiny", created_at=stamp, git_commit="abc",
        model={"model_id": "m"}, config={},
        results=[CaseResult(image="images/burger.png", caption=caption, **result)],
    )


@pytest.fixture
def saved(suite_dir):
    old = _run("20260101-100000", "current", "a red crab burger")
    mid = _run("20260102-100000", "current", "a red krustekrabbe")
    focus = _run("20260103-100000", "focus", "krustekrabbe on a plate",
                 trace={"facts": "FOCUS: burger"})
    for run in (old, mid, focus):
        store.save_run(suite_dir, run)
    return old, mid, focus


def _plain(renderable) -> str:
    console = Console(width=200, record=True)
    console.print(renderable)
    return console.export_text()


def test_default_selection_is_latest_run_per_variant_with_oldest_as_baseline(suite_dir, saved):
    _, mid, focus = saved

    selection = select_runs(suite_dir)

    assert [r.run_id for r in selection.runs] == [mid.run_id, focus.run_id]
    assert selection.baseline.run_id == mid.run_id


def test_explicit_baseline_is_added_to_the_selection(suite_dir, saved):
    old, _, focus = saved

    selection = select_runs(suite_dir, [focus.run_id], baseline_ref="20260101")

    assert [r.run_id for r in selection.runs] == [old.run_id, focus.run_id]
    assert selection.baseline.run_id == old.run_id


def test_no_runs_is_a_clear_error(suite_dir):
    with pytest.raises(ValueError, match="caption-bench run"):
        select_runs(suite_dir)


def test_diff_text_styles_changes():
    text = diff_text("a red burger", "a glossy red burger")

    styled = {text.plain[span.start:span.end]: str(span.style) for span in text.spans}
    assert styled == {"glossy": "bold green"}


def test_render_case_shows_every_run_and_trace_on_request(suite_dir, saved):
    suite = BenchSuite.load(suite_dir)
    selection = select_runs(suite_dir)

    without = _plain(render_case(suite.cases[0], selection))
    with_trace = _plain(render_case(suite.cases[0], selection, show_trace=True))

    assert "baseline" in without
    assert "plate" in without                       # candidate diffed into view
    assert "invented food item" in without          # case notes
    assert "FOCUS: burger" not in without
    assert "FOCUS: burger" in with_trace


def test_render_case_marks_images_missing_from_a_run(suite_dir, saved):
    suite = BenchSuite.load(suite_dir)

    out = _plain(render_case(suite.cases[1], select_runs(suite_dir)))

    assert "not in this run" in out


def test_tui_mounts_and_toggles_trace(suite_dir, saved):
    pytest.importorskip("textual")
    from prepare_lora_kit.caption_bench.tui import BenchViewApp

    app = BenchViewApp(BenchSuite.load(suite_dir), select_runs(suite_dir))

    async def drive():
        async with app.run_test() as pilot:
            await pilot.press("t")
            await pilot.pause()
            assert app.show_trace is True
            await pilot.press("down")
            await pilot.pause()
            assert app.index == 1

    asyncio.run(drive())
