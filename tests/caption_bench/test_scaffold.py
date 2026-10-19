"""Tests for suite-name resolution and `caption-bench init` scaffolding."""
import click
import pytest
from click.testing import CliRunner
from PIL import Image

from prepare_lora_kit import paths
from prepare_lora_kit.caption_bench.scaffold import init_suite, resolve_suite_path, suite_ref
from prepare_lora_kit.caption_bench.suite import BenchSuite
from prepare_lora_kit.caption_bench.variants import load_variants
from prepare_lora_kit.cli import cli


@pytest.fixture
def bench_dir(tmp_path, monkeypatch):
    bench = tmp_path / "bench_home"
    monkeypatch.setattr(paths, "BENCH_DIR", bench)
    return bench


@pytest.fixture
def launched(monkeypatch):
    calls = []
    monkeypatch.setattr(click, "launch", lambda target, **_: calls.append(target))
    return calls


def test_bare_name_resolves_under_bench_dir(bench_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert resolve_suite_path("food") == bench_dir / "food"
    assert suite_ref(bench_dir / "food") == "food"


def test_paths_and_existing_local_folders_are_kept(bench_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "local").mkdir()

    assert resolve_suite_path("local").name == "local"
    assert resolve_suite_path("local").parent != bench_dir
    assert resolve_suite_path(str(tmp_path / "x")) == tmp_path / "x"


def test_init_creates_a_loadable_suite(tmp_path):
    root = tmp_path / "food"

    init_suite(root, model_id="m/x", concept_token="krustekrabbe")

    suite = BenchSuite.load(root)
    assert suite.name == "food"
    assert suite.cases == []                       # images/ exists but is empty
    (current, single) = load_variants(suite, ["current", "single"])
    assert current.config.caption_model_id == "m/x"
    assert single.config.caption_strategy == "single"
    assert "krustekrabbe" in (root / "bench.yaml").read_text(encoding="utf-8")


def test_init_copies_dataset_images_but_not_region_crops(tmp_path):
    source = tmp_path / "dataset"
    source.mkdir()
    for name in ("a.png", "b.jpg", "plk_bbox__a__1.png"):
        Image.new("RGB", (4, 4)).save(source / name)
    (source / "a.txt").write_text("caption", encoding="utf-8")

    result = init_suite(tmp_path / "suite", images_from=source)

    assert result.copied == 2
    assert sorted(p.name for p in (tmp_path / "suite" / "images").iterdir()) == ["a.png", "b.jpg"]


def test_init_never_overwrites_an_existing_suite(tmp_path):
    init_suite(tmp_path / "s")

    with pytest.raises(ValueError, match="already has"):
        init_suite(tmp_path / "s")


def test_cli_init_by_name_opens_the_folder_and_run_finds_it(bench_dir, launched, tmp_path,
                                                          monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    created = runner.invoke(cli, ["caption-bench", "init", "food", "-t", "tok"])
    Image.new("RGB", (4, 4)).save(bench_dir / "food" / "images" / "a.png")
    ran = runner.invoke(cli, ["caption-bench", "run", "food", "--mock"])

    assert created.exit_code == 0, created.output
    assert "plk caption-bench run food" in created.output
    assert launched == [str(bench_dir / "food")]
    assert ran.exit_code == 0, ran.output
    assert list((bench_dir / "food" / "runs").glob("*__current.json"))


def test_cli_init_no_open_skips_the_file_manager(bench_dir, launched, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["caption-bench", "init", "food", "--no-open"])

    assert result.exit_code == 0, result.output
    assert launched == []
