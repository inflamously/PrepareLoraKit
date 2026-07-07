"""`projects` command — list available project configs."""
from __future__ import annotations

from prepare_lora_kit.project import project_registry

from prepare_lora_kit.cli._shared import cli

@cli.command()
def projects():
    """List available project configs."""
    from prepare_lora_kit.report import reporter
    from rich.table import Table
    from rich import box

    names = project_registry.list_projects()
    t = Table(title="Available Project Configs", box=box.SIMPLE)
    t.add_column("Name", style="cyan")
    for n in names:
        t.add_row(n)
    reporter.console.print(t)
