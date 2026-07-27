"""Tests for the caption verifier's load-progress watcher.

Nothing here loads a model. What is under test is the part that has to keep
working while ``loader.load_pipeline`` is blocked for minutes: the heartbeat
that proves the process is alive, and the tqdm tap that turns Hugging Face's
only progress signal into a line of text.

The tap patches ``tqdm.std.tqdm``, so the real tqdm is used — a fake would test
the patch against itself and miss the thing that actually matters, that bars
built from ``tqdm.auto`` (a *subclass*, bound in diffusers at import time) are
still caught.
"""
from __future__ import annotations

import io
import threading
import time
import types

import pytest

from prepare_lora_kit.steps.caption_verifier import load_status


def _bar(**attrs):
    return types.SimpleNamespace(**{"desc": "", "n": 0, "total": None, "unit": "it", **attrs})


# --- describing a bar ------------------------------------------------------

def test_byte_bars_are_described_in_human_sizes():
    """A download is the long pole; its absolute size is what the user reads."""
    progress = load_status.describe_bar(
        _bar(desc="model-00002-of-00006.safetensors", n=2 * 1024 ** 3,
             total=4 * 1024 ** 3, unit="B"),
    )

    assert progress.detail == "model-00002-of-00006.safetensors · 2.0 GB / 4.0 GB"
    assert progress.fraction == pytest.approx(0.5)


def test_counted_bars_are_described_as_a_ratio():
    progress = load_status.describe_bar(
        _bar(desc="Loading checkpoint shards", n=3, total=6),
    )

    assert progress.detail == "Loading checkpoint shards · 3/6"
    assert progress.fraction == pytest.approx(0.5)


def test_a_bar_with_no_total_still_yields_its_description():
    progress = load_status.describe_bar(_bar(desc="Fetching 6 files"))

    assert progress.detail == "Fetching 6 files"
    assert progress.fraction is None


def test_an_empty_bar_is_ignored():
    """Returning None keeps the previous, informative line on screen."""
    assert load_status.describe_bar(_bar()) is None


def test_a_bar_past_its_total_is_clamped():
    progress = load_status.describe_bar(_bar(desc="shards", n=9, total=6))

    assert progress.fraction == pytest.approx(1.0)


# --- the heartbeat ---------------------------------------------------------

def test_watch_emits_while_the_block_is_still_running():
    """The whole point: a silent load and a hung one must not look the same."""
    ticks: list[load_status.LoadProgress] = []
    seen = threading.Event()

    def callback(progress):
        ticks.append(progress)
        seen.set()

    with load_status.watch(callback, interval=0.02):
        assert seen.wait(2.0), "no heartbeat arrived while the block was running"

    assert ticks


def test_watch_stops_emitting_once_the_block_exits():
    ticks: list[load_status.LoadProgress] = []
    seen = threading.Event()

    def callback(progress):
        ticks.append(progress)
        seen.set()

    with load_status.watch(callback, interval=0.02):
        assert seen.wait(2.0)

    settled = len(ticks)
    time.sleep(0.1)
    assert len(ticks) == settled


def test_a_raising_callback_never_escapes_the_watcher():
    def callback(progress):
        raise RuntimeError("the UI went away")

    with load_status.watch(callback, interval=0.02):
        time.sleep(0.08)


# --- the tqdm tap ----------------------------------------------------------

def test_tqdm_bars_reach_the_callback_as_progress():
    """``tqdm.auto`` is a subclass bound in diffusers before this ever runs."""
    from tqdm.auto import tqdm

    ticks: list[load_status.LoadProgress] = []
    seen = threading.Event()

    def callback(progress):
        if progress.detail:
            ticks.append(progress)
            seen.set()

    with load_status.watch(callback, interval=0.02):
        bar = tqdm(total=6, desc="Loading checkpoint shards",
                   file=io.StringIO(), mininterval=0)
        bar.update(3)
        assert seen.wait(2.0), "the tqdm bar never reached the callback"
        bar.close()

    latest = ticks[-1]
    assert latest.detail == "Loading checkpoint shards · 3/6"
    assert latest.fraction == pytest.approx(0.5)


def test_tqdm_is_restored_after_the_block():
    """A permanently patched tqdm would follow the process into every later step."""
    from tqdm.std import tqdm

    before = (tqdm.__init__, tqdm.update)

    with load_status.watch(lambda progress: None, interval=0.02):
        assert tqdm.update is not before[1]

    assert (tqdm.__init__, tqdm.update) == before


def test_tqdm_is_restored_even_when_the_block_raises():
    from tqdm.std import tqdm

    before = (tqdm.__init__, tqdm.update)

    with pytest.raises(RuntimeError):
        with load_status.watch(lambda progress: None, interval=0.02):
            raise RuntimeError("load failed")

    assert (tqdm.__init__, tqdm.update) == before


def test_a_nested_watch_leaves_the_outer_tap_intact():
    """Non-blocking: the inner watch skips the tap rather than unpatching early."""
    from tqdm.std import tqdm

    before = (tqdm.__init__, tqdm.update)

    with load_status.watch(lambda progress: None, interval=0.02):
        patched = (tqdm.__init__, tqdm.update)
        with load_status.watch(lambda progress: None, interval=0.02):
            pass
        assert (tqdm.__init__, tqdm.update) == patched

    assert (tqdm.__init__, tqdm.update) == before


# --- formatting ------------------------------------------------------------

@pytest.mark.parametrize("seconds, expected", [
    (None, ""),
    (0, "0s"),
    (48, "48s"),
    (60, "1m 00s"),
    (612, "10m 12s"),
])
def test_format_elapsed(seconds, expected):
    assert load_status.format_elapsed(seconds) == expected
