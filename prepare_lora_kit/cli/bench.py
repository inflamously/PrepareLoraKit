"""`caption-bench` commands — caption a fixed image suite per variant and compare runs."""
from __future__ import annotations

from pathlib import Path

import click

from prepare_lora_kit.cli._shared import cli


def _resolve_suite(_ctx, _param, value: str) -> Path:
    from prepare_lora_kit.caption_bench.scaffold import resolve_suite_path

    return resolve_suite_path(value)


# A path, or a bare name living under ~/.prepare_lora_kit/bench/.
_suite_argument = click.argument("suite_dir", metavar="SUITE", callback=_resolve_suite)


def _load_suite(suite_dir: Path):
    from prepare_lora_kit.caption_bench.suite import BenchSuite

    try:
        return BenchSuite.load(suite_dir)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _open_folder(path: Path) -> None:
    """Show ``path`` in the system file manager; a headless box just skips it."""
    try:
        click.launch(str(path))
    except Exception as exc:  # opening a window is best effort
        click.echo(f"Could not open {path}: {exc}")


@cli.group("caption-bench")
def caption_bench():
    """Benchmark caption settings on a fixed image suite (see docs/caption-step/benchmark.md).

    SUITE is a folder path, or a bare name stored under ~/.prepare_lora_kit/bench/.
    """


@caption_bench.command("init")
@_suite_argument
@click.option("--model", "model_id", default=None,
              help="Caption model id written to bench.yaml (default: Qwen3-VL 8B).")
@click.option("--token", "-t", "concept_token", default=None,
              help="Trigger word for every image (omit for style mode).")
@click.option("--images", "images_from", default=None,
              type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Copy the images of this folder (e.g. a dataset) into the suite.")
@click.option("--no-open", is_flag=True, help="Do not open the new folder.")
def init_bench(suite_dir: Path, model_id: str | None, concept_token: str | None,
               images_from: Path | None, no_open: bool):
    """Create a new suite: bench.yaml, images/ and an example variant."""
    from prepare_lora_kit.caption_bench.scaffold import init_suite, suite_ref
    from prepare_lora_kit.report import reporter

    try:
        result = init_suite(suite_dir, model_id=model_id, concept_token=concept_token,
                            images_from=images_from)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    reporter.ok(f"Created benchmark suite {result.root}")
    if images_from:
        reporter.info(f"Copied {result.copied} images from {images_from}")
    else:
        reporter.info(f"Put images into {result.root / 'images'}")
    reporter.info(f"Then: plk caption-bench run {suite_ref(result.root)}")
    if not no_open:
        _open_folder(result.root)



@caption_bench.command("run")
@_suite_argument
@click.option("--variant", "-v", "variants", multiple=True, default=("current",),
              show_default=True, help="Variant to run (repeatable): 'current' or "
                                      "variants/<name>.yaml.")
@click.option("--model", "model_id", default=None,
              help="Caption model id for every variant (overrides suite and variant).")
@click.option("--mock", is_flag=True, help="Fake runtime: no model, no GPU.")
def run_bench(suite_dir: Path, variants: tuple[str, ...], model_id: str | None, mock: bool):
    """Caption every suite image with each variant and store the runs."""
    from prepare_lora_kit.caption_bench import store
    from prepare_lora_kit.caption_bench.mock import MockBenchRuntime
    from prepare_lora_kit.caption_bench.runner import CaptionBenchRunner, real_runtime_factory
    from prepare_lora_kit.caption_bench.variants import load_variants
    from prepare_lora_kit.report import reporter

    suite = _load_suite(suite_dir)
    try:
        resolved = load_variants(suite, list(variants), model_id=model_id)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    def on_case(variant, case, result):
        if result.error is None:
            reporter.ok(f"[{variant.name}] {case.name} ({result.seconds:.1f}s) → {result.caption}")

    runner = CaptionBenchRunner(
        suite,
        runtime_factory=MockBenchRuntime if mock else real_runtime_factory,
        on_case=on_case,
    )
    for bench_run in runner.run(resolved):
        path = store.save_run(suite.root, bench_run)
        errors = sum(1 for r in bench_run.results if r.error)
        reporter.info(
            f"Saved {bench_run.run_id}: {len(bench_run.results)} images, {errors} errors, "
            f"{bench_run.total_seconds:.1f}s → {path}"
        )


@caption_bench.command("runs")
@_suite_argument
def list_bench_runs(suite_dir: Path):
    """List the stored runs of a suite, oldest first."""
    from rich import box
    from rich.table import Table

    from prepare_lora_kit.caption_bench import store
    from prepare_lora_kit.report import reporter

    suite = _load_suite(suite_dir)
    table = Table(title=f"Runs · {suite.name}", box=box.SIMPLE)
    for column in ("Run", "Variant", "Model", "Commit"):
        table.add_column(column, no_wrap=True)
    for column in ("Images", "Errors", "Seconds"):
        table.add_column(column, justify="right")
    for bench_run in store.list_runs(suite.root):
        table.add_row(
            bench_run.run_id, bench_run.variant, str(bench_run.model.get("model_id")),
            bench_run.git_commit or "?", str(len(bench_run.results)),
            str(sum(1 for r in bench_run.results if r.error)),
            f"{bench_run.total_seconds:.1f}",
        )
    reporter.console.print(table)


@caption_bench.command("view")
@_suite_argument
@click.option("--run", "-r", "refs", multiple=True,
              help="Run id or unique prefix (repeatable). Default: latest run per variant.")
@click.option("--baseline", "-b", default=None,
              help="Run to diff against. Default: the oldest shown run.")
@click.option("--plain", is_flag=True, help="Print every image instead of the Textual view.")
@click.option("--trace", "show_trace", is_flag=True,
              help="Also show each pass's raw output (plain view; press t in the TUI).")
def view_bench(suite_dir: Path, refs: tuple[str, ...], baseline: str | None,
               plain: bool, show_trace: bool):
    """Compare runs side by side, with word changes vs the baseline highlighted."""
    from prepare_lora_kit.caption_bench.render import render_case, select_runs
    from prepare_lora_kit.report import reporter

    suite = _load_suite(suite_dir)
    try:
        selection = select_runs(suite.root, refs, baseline)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if plain:
        for case in suite.cases:
            reporter.console.print(render_case(case, selection, show_trace=show_trace))
            reporter.console.rule()
        return

    try:
        from prepare_lora_kit.caption_bench.tui import run_viewer
    except ImportError as exc:
        raise click.ClickException(
            'The interactive view needs Textual: pip install -e ".[bench]" (or use --plain).'
        ) from exc
    run_viewer(suite, selection)
