"""Rich-based console reporting, and where a step's JSON report lives."""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.table import Table

REPORTS_DIR_NAME = "reports"


def load_report(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def reports_dir_for(output_dir: Path) -> Path:
    """The folder holding every step report for one run."""

    return Path(output_dir) / REPORTS_DIR_NAME


def step_report_path(output_dir: Path, step_type: str) -> Path:
    """Where ``step_type`` writes its report.

    The single source of the ``<StepType>_report.json`` convention. Callers used
    to spell it out, which let a report be written where nothing would look for
    it — and let the engine miss one when discarding invalidated state.
    """
    return reports_dir_for(output_dir) / f"{step_type}_report.json"


def discard_step_reports(output_dir: Path, step_types: Iterable[str]) -> list[Path]:
    """Delete the reports of steps whose run-state was just invalidated.

    A report outlives the state that describes it otherwise: ``--force`` resets
    the run-state of the selected step and everything downstream, but the old
    JSON stayed on disk describing a run that no longer happened. Returns the
    paths actually removed. Only ``<StepType>_report.json`` files are touched —
    coverage plots, previews and the caption verdict ledger are run artifacts
    that outlive a single step and are not the engine's to delete.
    """
    removed: list[Path] = []
    for step_type in step_types:
        path = step_report_path(output_dir, step_type)
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed


class Reporter:
    """Console reporter and JSON report persistence helper."""
    console: Console

    def __init__(self) -> None:
        self.console = Console()

    def step_header(self, title: str) -> None:
        self.console.rule(f"[bold cyan]{title}[/bold cyan]")

    def info(self, msg: str) -> None:
        self.console.print(f"[dim]ℹ[/dim]  {msg}")

    def warn(self, msg: str) -> None:
        self.console.print(f"[yellow]⚠[/yellow]  {msg}")

    def error(self, msg: str) -> None:
        self.console.print(f"[red]✗[/red]  {msg}")

    def ok(self, msg: str) -> None:
        self.console.print(f"[green]✓[/green]  {msg}")

    def save_report(self, data: Any, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(data, f, indent=2, default=str)
        self.info(f"Report saved → {path}")

    def image_table(self, rows: list[dict], title: str = "") -> None:
        """Print a table of image results. Each row: {path, status, reason}."""
        t = Table(title=title, box=box.SIMPLE_HEAVY, show_lines=False)
        t.add_column("File", style="cyan", no_wrap=True, max_width=60)
        t.add_column("Status", justify="center", width=10)
        t.add_column("Reason / Notes", style="dim")
        for row in rows:
            status = row.get("status", "")
            colour = {"keep": "green", "reject": "red", "flag": "yellow"}.get(status, "white")
            t.add_row(
                Path(row["path"]).name,
                f"[{colour}]{status}[/{colour}]",
                row.get("reason") or row.get("notes") or "",
            )
        self.console.print(t)

    def summary_counts(self, kept: int, rejected: int, flagged: int = 0) -> None:
        self.console.print(
            f"  [green]kept {kept}[/green]"
            f"  [red]rejected {rejected}[/red]"
            + (f"  [yellow]flagged {flagged}[/yellow]" if flagged else "")
        )


reporter = Reporter()
