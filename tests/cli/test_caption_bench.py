"""CLI tests for `plk caption-bench` using the mock runtime."""
from pathlib import Path

from click.testing import CliRunner
from PIL import Image

from prepare_lora_kit.caption_bench import store
from prepare_lora_kit.cli import cli


def _suite(tmp_path: Path) -> Path:
    root = tmp_path / "suite"
    (root / "images").mkdir(parents=True)
    Image.new("RGB", (8, 8), (255, 0, 0)).save(root / "images" / "a.png")
    (root / "bench.yaml").write_text("name: cli\nconcept_token: tok\n", encoding="utf-8")
    (root / "variants").mkdir()
    (root / "variants" / "single.yaml").write_text(
        "caption_strategy: single\n", encoding="utf-8")
    return root


def test_run_mock_saves_one_run_per_variant_then_lists_and_views_them(tmp_path):
    root = _suite(tmp_path)
    runner = CliRunner()

    ran = runner.invoke(cli, ["caption-bench", "run", str(root), "--mock",
                              "-v", "current", "-v", "single"])
    listed = runner.invoke(cli, ["caption-bench", "runs", str(root)])
    viewed = runner.invoke(cli, ["caption-bench", "view", str(root), "--plain"])

    assert ran.exit_code == 0, ran.output
    assert [r.variant for r in store.list_runs(root)] == ["current", "single"]
    assert store.list_runs(root)[0].results[0].caption.startswith("tok")
    assert listed.exit_code == 0, listed.output
    assert "single" in listed.output
    assert viewed.exit_code == 0, viewed.output
    assert "single mock caption" in viewed.output


def test_unknown_variant_fails_cleanly(tmp_path):
    root = _suite(tmp_path)

    result = CliRunner().invoke(cli, ["caption-bench", "run", str(root), "--mock", "-v", "x"])

    assert result.exit_code != 0
    assert "Unknown variant 'x'" in result.output


def test_view_without_runs_fails_cleanly(tmp_path):
    root = _suite(tmp_path)

    result = CliRunner().invoke(cli, ["caption-bench", "view", str(root), "--plain"])

    assert result.exit_code != 0
    assert "No benchmark runs yet" in result.output
