"""Rich-based console reporting helpers."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import json

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def step_header(step_num: int, title: str) -> None:
    console.rule(f"[bold cyan]{title}[/bold cyan]")


def info(msg: str) -> None:
    console.print(f"[dim]ℹ[/dim]  {msg}")


def warn(msg: str) -> None:
    console.print(f"[yellow]⚠[/yellow]  {msg}")


def error(msg: str) -> None:
    console.print(f"[red]✗[/red]  {msg}")


def ok(msg: str) -> None:
    console.print(f"[green]✓[/green]  {msg}")


def save_report(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    info(f"Report saved → {path}")


def load_report(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


def image_table(rows: list[dict], title: str = "") -> None:
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
    console.print(t)


def summary_counts(kept: int, rejected: int, flagged: int = 0) -> None:
    console.print(
        f"  [green]kept {kept}[/green]"
        f"  [red]rejected {rejected}[/red]"
        + (f"  [yellow]flagged {flagged}[/yellow]" if flagged else "")
    )
