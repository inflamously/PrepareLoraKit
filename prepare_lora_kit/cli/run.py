"""`run` command — dynamic pipeline driven by project config."""
from __future__ import annotations
from pathlib import Path

import click

from prepare_lora_kit.project import project_registry
from ._shared import cli, _default_output
from ..pipeline import RunConfig


def _load_or_create_project(input_dir: Path, project_name: str | None):
    """Load project by explicit name or folder name; prompt to create if missing."""
    name = project_name or input_dir.name

    try:
        return project_registry.load(name)
    except ValueError:
        pass

    click.echo(f"\nNo project config found for '{name}'.")
    if not click.confirm("Create a default project config?", default=True):
        raise click.Abort()

    config_path = project_registry.write_default_project(name, input_dir=input_dir.expanduser().resolve())
    click.echo(f"Created: {config_path}")
    click.echo("Edit it to customize the pipeline, then re-run.")
    click.echo()

    if not click.confirm("Run now with defaults?", default=False):
        raise SystemExit(0)

    return project_registry.load(name)


@cli.command()
@click.pass_context
@click.option("--input", "-i", "input_dir", required=True,
              type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Dataset directory")
@click.option("--output", "-o", "output_dir",
              type=click.Path(file_okay=False, path_type=Path),
              default=None, help="Output directory (default: outputs/<input-name>)")
@click.option("--project", "-p", "project_name", default=None,
              help="Project config name (default: input folder name)")
@click.option("--token", "-t", default=None,
              help="Concept token / trigger word. Omit for style training.")
@click.option("--force", is_flag=True, help="Re-run all steps even if already completed")
def run(ctx, input_dir, output_dir, project_name, token, force):
    """Run the pipeline defined in the project config.

    If no project config exists for the input folder, you will be prompted
    to create one with sensible defaults.
    """
    project = _load_or_create_project(input_dir, project_name)
    output_dir = output_dir or _default_output(input_dir)

    from ..pipeline import run_all
    run_all(RunConfig(
        dataset_dir=input_dir,
        project=project,
        concept_token=token,
        output_dir=output_dir,
        force=force,
    ))
