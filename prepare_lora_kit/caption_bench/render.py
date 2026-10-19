"""Run selection and Rich rendering shared by the plain and the Textual bench views."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Group, RenderableType
from rich.text import Text

from prepare_lora_kit.caption_bench import store
from prepare_lora_kit.caption_bench.diff import word_diff
from prepare_lora_kit.caption_bench.store import BenchRun, CaseResult
from prepare_lora_kit.caption_bench.suite import BenchCase

_DIFF_STYLES = {"same": "", "added": "bold green", "removed": "red strike"}
# Trace keys in pass order, with the label shown for each.
_TRACE_LABELS = (
    ("facts", "observe"),
    ("draft", "compose"),
    ("gap_raw", "gap (raw)"),
    ("gap_phrases", "gap (kept)"),
)


@dataclass(frozen=True)
class RunSelection:
    """The runs to show, oldest first, and the one others are diffed against."""

    runs: list[BenchRun]
    baseline: BenchRun


def select_runs(
        suite_root: Path,
        refs: list[str] | tuple[str, ...] = (),
        baseline_ref: str | None = None,
) -> RunSelection:
    """Explicit ``refs``, else the latest run of every variant.

    The baseline is ``baseline_ref`` when given (added to the selection if needed),
    else the oldest selected run.
    """
    if refs:
        runs = [store.find_run(suite_root, ref) for ref in refs]
    else:
        latest: dict[str, BenchRun] = {}
        for run in store.list_runs(suite_root):
            latest[run.variant] = run
        runs = sorted(latest.values(), key=lambda r: r.run_id)
    if not runs:
        raise ValueError("No benchmark runs yet — run `plk caption-bench run <suite>` first")
    baseline = store.find_run(suite_root, baseline_ref) if baseline_ref else runs[0]
    if all(run.run_id != baseline.run_id for run in runs):
        runs = [baseline, *runs]
    return RunSelection(runs=runs, baseline=baseline)


def diff_text(baseline: str, caption: str) -> Text:
    text = Text()
    for i, token in enumerate(word_diff(baseline, caption)):
        if i:
            text.append(" ")
        text.append(token.text, style=_DIFF_STYLES[token.op])
    return text


def _run_header(run: BenchRun, result: CaseResult, *, is_baseline: bool) -> Text:
    passes = "+".join(
        stage if count == 1 else f"{stage}×{count}" for stage, count in result.passes.items()
    ) or "-"
    header = Text(f"{run.variant}", style="bold cyan")
    header.append(f"  {run.run_id}  @{run.git_commit or '?'}", style="dim")
    header.append(f"  {result.words}w {result.seconds:.1f}s [{passes}]", style="dim")
    if is_baseline:
        header.append("  baseline", style="bold yellow")
    return header


def _trace(result: CaseResult) -> RenderableType:
    lines = Text()
    for key, label in _TRACE_LABELS:
        value = result.trace.get(key)
        if value in (None, "", []):
            continue
        shown = ", ".join(value) if isinstance(value, list) else str(value)
        lines.append(f"  {label}: ", style="bold dim")
        lines.append(f"{shown.strip()}\n", style="dim")
    return lines


def render_case(
        case: BenchCase,
        selection: RunSelection,
        *,
        show_trace: bool = False,
) -> RenderableType:
    """Every selected run's caption for ``case``, diffed against the baseline."""
    base = selection.baseline.result_for(case.rel_path)
    base_caption = base.caption if base else ""
    parts: list[RenderableType] = [Text(case.rel_path, style="bold")]
    if case.notes:
        parts.append(Text(f"notes: {case.notes}", style="italic dim"))
    for run in selection.runs:
        result = run.result_for(case.rel_path)
        parts.append(Text())
        if result is None:
            parts.append(Text(f"{run.variant}  {run.run_id}: not in this run", style="dim"))
            continue
        is_baseline = run.run_id == selection.baseline.run_id
        parts.append(_run_header(run, result, is_baseline=is_baseline))
        if result.error:
            parts.append(Text(f"error: {result.error}", style="bold red"))
        elif is_baseline:
            parts.append(Text(result.caption))
        else:
            parts.append(diff_text(base_caption, result.caption))
        if show_trace:
            parts.append(_trace(result))
    return Group(*parts)
