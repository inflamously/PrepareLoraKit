"""`projects` command — list available project configs."""
from __future__ import annotations

from ..project import registry as project_registry
from ._shared import cli


@cli.command()
def projects():
    """List available project configs."""
    from ..utils.report import console
    from rich.table import Table
    from rich import box

    names = project_registry.list_projects()
    t = Table(title="Available Project Configs", box=box.SIMPLE)
    t.add_column("Name", style="cyan")
    for n in names:
        t.add_row(n)
    console.print(t)
