"""`step` command — run a single pipeline step manually, driven by project config.

Where `run` executes the whole project pipeline, `step` runs exactly one step by
name (or alias) using that step's config from the project. It reuses the same
``STEP_INVOKE_MAP`` adapters and working-dir convention as :func:`run_all`, so a
manually-run step operates on the same ``<output>/dataset`` working tree.
"""
from __future__ import annotations

import click

from prepare_lora_kit_pipeline.configuration import STEP_PREREQUISITES
from .._shared import cli, cli_option_input, cli_option_output, cli_option_token
from .bbox import build_bbox_interaction
from .resolve import _load_project, _resolve_step_type
from ...invoke import STEP_INVOKE_MAP
from ...pipeline import RunConfig
from ...project.base import STEP_TYPE_MAP
from ...project.steps import (
    default_substeps_for,
    enabled_substep_ids,
    mark_legacy_import_satisfied,
)


@cli.command()
@click.pass_context
@click.option("--step", "-s", "step_name", required=True,
              help="Step to run by type name (e.g. CaptionBboxStep).")
@click.option("--project", "-p", "project_name", required=True,
              help="Project config name (configs/projects/<name>.yaml).")
@cli_option_input
@cli_option_output
@cli_option_token
@click.option("--force", is_flag=True,
              help="Run even if run-state already marks this step done.")
@click.option("--model", "model_id", default=None,
              help="CaptionBboxStep only: override the project's caption model for this run.")
@click.option("--bbox", "bboxes", multiple=True, metavar="X1,Y1,X2,Y2[:LABEL]",
              help="CaptionBboxStep only: region to caption around (repeatable). Pixel "
                   "coords, or normalized [0,1] if all four values are <= 1.0.")
@click.option("--bbox-image", "bbox_image", default=None,
              help="CaptionBboxStep only: which dataset image the --bbox regions apply to "
                   "(required when the dataset has more than one image).")
def step(ctx, step_name, project_name, input_dir, output_dir, token, force,
         model_id, bboxes, bbox_image):
    """Run a single pipeline step manually, using the project's step config.

    The step's parameters come from the project pipeline entry of the same type;
    if the project does not define that step, built-in defaults are used.
    """
    step_type = _resolve_step_type(step_name)
    if step_type != "CaptionBboxStep" and (model_id or bboxes or bbox_image):
        raise click.BadParameter(
            "--model/--bbox/--bbox-image are only valid for CaptionBboxStep.",
            param_hint="--step")

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

    from ...utils import report as rpt
    from ...utils.state import RunState

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

    shared_kw = dict(concept_token=token, original_dir=input_dir, force=force)

    rpt.info(f"Running {step_type} for project '{project.name}'.")
    substeps = match.substeps if match is not None else default_substeps_for(step_type, config)
    enabled_substeps = enabled_substep_ids(step_type, substeps)

    if model_id:
        shared_kw["caption_runtime"] = {"model_id": model_id}
    if bboxes:
        interaction, target, boxes = build_bbox_interaction(working_dir, bboxes, bbox_image)
        shared_kw["interaction"] = interaction
        if "annotate_regions" not in enabled_substeps:
            enabled_substeps = [*enabled_substeps, "annotate_regions"]
        rpt.info(f"Applying {len(boxes)} bbox region(s) to {target.name}.")

    invoke = STEP_INVOKE_MAP[step_type]
    result = invoke(working_dir, out_dir, config, **shared_kw, enabled_substeps=enabled_substeps)
    if step_type == "AuditStep" and isinstance(result, dict) and not result.get("pass"):
        rpt.warn("Integrity audit found issues — review "
                 "reports/AuditStep_report.json before training.")
    for substep_id in enabled_substeps:
        state.mark_substep_done(step_type, substep_id)
    state.mark_done(step_type, {"enabled_substeps": enabled_substeps})
    rpt.ok(f"{step_type} complete. Report in {out_dir / 'reports'}.")
