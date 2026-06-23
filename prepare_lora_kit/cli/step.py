"""`step` command — run a single pipeline step manually, driven by project config.

Where `run` executes the whole project pipeline, `step` runs exactly one step by
name (or alias) using that step's config from the project. It reuses the same
``STEP_INVOKE_MAP`` adapters and working-dir convention as :func:`run_all`, so a
manually-run step operates on the same ``<output>/dataset`` working tree.
"""
from __future__ import annotations
from pathlib import Path

import click

from ._shared import cli, cli_option_input, cli_option_output, cli_option_token
from ..invoke import STEP_INVOKE_MAP
from ..project import registry as project_registry
from ..project.base import STEP_TYPE_MAP
from ..project.steps import (
    STEP_PREREQUISITES,
    default_substeps_for,
    enabled_substep_ids,
    mark_legacy_import_satisfied,
    step_aliases,
)
from ..pipeline import RunConfig


# Short aliases (sN / bare index) → canonical step type, preserving s1..s8.
_STEP_ALIASES = step_aliases()


def _resolve_step_type(raw: str) -> str:
    """Map a user-supplied step name/alias to a canonical step type."""
    low = raw.strip().lower()
    if low in _STEP_ALIASES:
        return _STEP_ALIASES[low]
    for t in STEP_TYPE_MAP:
        if t.lower() == low:
            return t
    raise click.BadParameter(
        f"Unknown step '{raw}'.\n"
        f"  Types:   {', '.join(STEP_TYPE_MAP)}\n"
        f"  Aliases: {', '.join(sorted(_STEP_ALIASES))}",
        param_hint="--step",
    )


def _load_project(name: str):
    try:
        return project_registry.load(name)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--project")


@cli.command()
@click.pass_context
@click.option("--step", "-s", "step_name", required=True,
              help="Step to run: type name (e.g. CaptionStep) or alias s0..s8.")
@click.option("--project", "-p", "project_name", required=True,
              help="Project config name (configs/projects/<name>.yaml).")
@cli_option_input
@cli_option_output
@cli_option_token
@click.option("--force", is_flag=True,
              help="Run even if run-state already marks this step done.")
def step(ctx, step_name, project_name, input_dir, output_dir, token, force):
    """Run a single pipeline step manually, using the project's step config.

    The step's parameters come from the project pipeline entry of the same type;
    if the project does not define that step, built-in defaults are used.
    """
    step_type = _resolve_step_type(step_name)
    project = _load_project(project_name)
    ctx.obj.project = project

    match = next((s for s in project.pipeline if s.type == step_type), None)
    if match is not None:
        config = match.config
    else:
        config = STEP_TYPE_MAP[step_type]()
        click.echo(f"'{step_type}' not defined in project '{project.name}' "
                   f"pipeline — using built-in defaults.")

    cfg = RunConfig(
        dataset_dir=input_dir,
        project=project,
        concept_token=token,
        output_dir=output_dir,
    )
    out_dir = cfg.resolved_output_dir
    working_dir = out_dir / "dataset"

    from ..networks import registry as net_registry
    from ..utils import report as rpt
    from ..utils.state import RunState

    network = net_registry.load(project.network)
    state = RunState(out_dir)

    if (
        not force
        and step_type == "ImportStep"
        and mark_legacy_import_satisfied(state, out_dir)
    ):
        rpt.info("ImportStep satisfied by existing working dataset.")
        return

    if not force and state.is_done(step_type):
        rpt.info(f"{step_type} already done — skipping (use --force to re-run).")
        return

    if not force:
        if mark_legacy_import_satisfied(state, out_dir):
            rpt.info("ImportStep satisfied by existing working dataset.")
        for req in STEP_PREREQUISITES.get(step_type, []):
            if not state.is_done(req):
                raise click.ClickException(f"{step_type} requires completed prerequisite {req}")

    if step_type != "ImportStep" and not working_dir.exists():
        raise click.ClickException("The working dataset does not exist. Run ImportStep first.")

    shared_kw = dict(network=network, concept_token=token, original_dir=input_dir,
                     network_type=project.network_type, force=force)

    rpt.info(f"Running {step_type} for project '{project.name}'.")
    substeps = match.substeps if match is not None else default_substeps_for(step_type, config)
    enabled_substeps = enabled_substep_ids(step_type, substeps)
    invoke = STEP_INVOKE_MAP[step_type]
    result = invoke(working_dir, out_dir, config, **shared_kw, enabled_substeps=enabled_substeps)
    if step_type == "AuditStep" and isinstance(result, dict) and not result.get("pass"):
        rpt.warn("Integrity audit found issues — review "
                 "reports/AuditStep_report.json before training.")
    for substep_id in enabled_substeps:
        state.mark_substep_done(step_type, substep_id)
    state.mark_done(step_type, {"enabled_substeps": enabled_substeps})
    rpt.ok(f"{step_type} complete. Report in {out_dir / 'reports'}.")
