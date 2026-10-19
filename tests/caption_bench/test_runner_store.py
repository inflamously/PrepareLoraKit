"""Tests for running a benchmark variant and storing/diffing its results."""
import json

from prepare_lora_kit.caption_bench import store
from prepare_lora_kit.caption_bench.diff import word_diff
from prepare_lora_kit.caption_bench.mock import MockBenchRuntime
from prepare_lora_kit.caption_bench.runner import CaptionBenchRunner
from prepare_lora_kit.caption_bench.suite import BenchSuite
from prepare_lora_kit.caption_bench.variants import load_variants


class _ExplodingRuntime(MockBenchRuntime):
    def caption_image(self, image_path, annotations, concept_token, **kwargs):
        if image_path.name == "beach.png":
            raise RuntimeError("CUDA out of memory")
        return super().caption_image(image_path, annotations, concept_token, **kwargs)


def _runner(suite, runtime_cls=MockBenchRuntime, created=None):
    runtimes = []

    def factory(config):
        runtime = runtime_cls(config)
        runtimes.append(runtime)
        return runtime

    runner = CaptionBenchRunner(
        suite, runtime_factory=factory, git_commit=lambda: "abc1234",
        now=lambda: created or store.utc_now(),
    )
    return runner, runtimes


def test_run_records_caption_trace_passes_and_timing_per_case(suite_dir):
    suite = BenchSuite.load(suite_dir)
    runner, _ = _runner(suite)

    (run,) = runner.run(load_variants(suite, ["current"]))

    burger = run.results[0]
    assert burger.image == "images/burger.png"
    assert burger.caption.startswith("krustekrabbe")       # cleaned like the real step
    assert "sesame claws" in burger.caption               # annotation reached the runtime
    assert burger.trace["draft"]
    assert burger.passes == {"compose": 1}
    assert burger.seconds >= 0
    assert burger.words == len(burger.caption.split())
    assert run.git_commit == "abc1234"
    assert run.model["model_id"] == "some/model"


def test_a_failing_image_is_recorded_and_the_run_continues(suite_dir):
    suite = BenchSuite.load(suite_dir)
    runner, _ = _runner(suite, _ExplodingRuntime)

    (run,) = runner.run(load_variants(suite, ["current"]))

    burger, beach = run.results
    assert burger.error is None
    assert beach.caption == ""
    assert "CUDA out of memory" in beach.error


def test_variants_sharing_a_model_reuse_it_and_unload_once_at_the_end(suite_dir):
    (suite_dir / "variants").mkdir()
    (suite_dir / "variants" / "single.yaml").write_text(
        "caption_strategy: single\n", encoding="utf-8")
    suite = BenchSuite.load(suite_dir)
    runner, runtimes = _runner(suite)

    runs = runner.run(load_variants(suite, ["current", "single"]))

    assert [run.variant for run in runs] == ["current", "single"]
    assert [runtime.unloaded for runtime in runtimes] == [False, True]


def test_switching_model_unloads_the_previous_one(suite_dir):
    (suite_dir / "variants").mkdir()
    (suite_dir / "variants" / "other.yaml").write_text(
        "caption_model_id: other/model\n", encoding="utf-8")
    suite = BenchSuite.load(suite_dir)
    runner, runtimes = _runner(suite)

    runner.run(load_variants(suite, ["current", "other"]))

    assert [runtime.unloaded for runtime in runtimes] == [True, True]


def test_saved_run_round_trips_and_is_listed_newest_last(suite_dir):
    suite = BenchSuite.load(suite_dir)
    first, _ = _runner(suite, created=store.parse_timestamp("20260101-100000"))
    second, _ = _runner(suite, created=store.parse_timestamp("20260102-100000"))
    old = first.run(load_variants(suite, ["current"]))[0]
    new = second.run(load_variants(suite, ["current"]))[0]

    path_old = store.save_run(suite.root, old)
    store.save_run(suite.root, new)

    assert path_old.name == "20260101-100000__current.json"
    assert [run.run_id for run in store.list_runs(suite.root)] == [old.run_id, new.run_id]
    loaded = store.load_run(path_old)
    assert loaded == old
    assert json.loads(path_old.read_text(encoding="utf-8"))["variant"] == "current"


def test_find_run_accepts_a_unique_prefix(suite_dir):
    suite = BenchSuite.load(suite_dir)
    runner, _ = _runner(suite, created=store.parse_timestamp("20260101-100000"))
    store.save_run(suite.root, runner.run(load_variants(suite, ["current"]))[0])

    assert store.find_run(suite.root, "20260101").variant == "current"


def test_word_diff_marks_added_and_removed_words():
    tokens = word_diff("a red crab burger", "a glossy red krustekrabbe")

    assert [(t.op, t.text) for t in tokens] == [
        ("same", "a"),
        ("added", "glossy"),
        ("same", "red"),
        ("removed", "crab"),
        ("removed", "burger"),
        ("added", "krustekrabbe"),
    ]


def test_word_diff_ignores_trailing_punctuation_differences():
    tokens = word_diff("a red burger.", "a red burger")

    assert {t.op for t in tokens} == {"same"}
