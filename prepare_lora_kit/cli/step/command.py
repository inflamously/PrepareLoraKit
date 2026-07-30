"""`step` command — run a single pipeline step manually, driven by project config.

Where `run` executes the whole project pipeline, `step` runs exactly one step by
name (or alias) using that step's config from the project. It reuses the same
``STEP_INVOKE_MAP`` adapters and working-dir convention as :func:`run_all`, so a
manually-run step operates on the same ``<output>/dataset`` working tree.
"""

from __future__ import annotations

import click

from prepare_lora_kit.cli._shared import (
    cli,
    cli_option_input,
    cli_option_output,
    cli_option_token,
)
from prepare_lora_kit.cli.step.bbox import build_bbox_interaction
from prepare_lora_kit.cli.step.resolve import _load_project, _resolve_step_type
from prepare_lora_kit.invoke import STEP_INVOKE_MAP
from prepare_lora_kit.pipeline import RunConfig, step_config_class, step_prerequisites, step_slug
from prepare_lora_kit.project.steps import (
    default_substeps_for,
    enabled_substep_ids,
    mark_legacy_import_satisfied,
)


@cli.command()
@click.pass_context
@click.option(
    "--step",
    "-s",
    "step_name",
    required=True,
    help="Step to run, by type name (CaptionBboxStep) or slug (caption_bbox).",
)
@click.option(
    "--project",
    "-p",
    "project_name",
    required=True,
    help="Project name (~/.prepare_lora_kit/projects/<name>/).",
)
@cli_option_input
@cli_option_output
@cli_option_token
@click.option(
    "--force", is_flag=True, help="Run even if run-state already marks this step done."
)
@click.option(
    "--model",
    "model_id",
    default=None,
    help="CaptionBboxStep only: override the project's caption model for this run.",
)
@click.option(
    "--bbox",
    "bboxes",
    multiple=True,
    metavar="X1,Y1,X2,Y2[:LABEL]",
    help="CaptionBboxStep only: region to caption around (repeatable). Pixel "
    "coords, or normalized [0,1] if all four values are <= 1.0.",
)
@click.option(
    "--bbox-image",
    "bbox_image",
    default=None,
    help="CaptionBboxStep only: which dataset image the --bbox regions apply to "
    "(required when the dataset has more than one image).",
)
def step(
    ctx,
    step_name,
    project_name,
    input_dir,
    output_dir,
    token,
    force,
    model_id,
    bboxes,
    bbox_image,
):
    """Run a single pipeline step manually, using the project's step config.

    The step's parameters come from the project pipeline entry of the same type;
    if the project does not define that step, built-in defaults are used.
    """
    step_type = _resolve_step_type(step_name)
    if step_type != "CaptionBboxStep" and (model_id or bboxes or bbox_image):
        raise click.BadParameter(
            "--model/--bbox/--bbox-image are only valid for CaptionBboxStep.",
            param_hint="--step",
        )

    project = _load_project(project_name)
    ctx.obj.project = project

    match = next((s for s in project.pipeline if s.type == step_type), None)
    config = _resolve_step_config(project, step_type, match)

    cfg = RunConfig(
        dataset_dir=input_dir,
        project=project,
        concept_token=token,
        output_dir=output_dir,
    )
    out_dir = cfg.resolved_output_dir
    working_dir = out_dir / "dataset"

    from prepare_lora_kit.pipeline.execution import (
        describe_skip,
        persist_step_outcome,
        resolve_force_invalidated_steps,
        step_outcome,
    )
    from prepare_lora_kit.report import discard_step_reports, reporter, reports_dir_for
    from prepare_lora_kit.utils.state import RunState

    state = RunState(out_dir)

    if not _should_run_step(state, step_type, out_dir, working_dir, force=force):
        return

    if force:
        invalidated = resolve_force_invalidated_steps(project, [step_type])
        state.reset_steps(invalidated)
        # Same rule as the pipeline engine: a report never outlives the run-state
        # that describes it.
        discard_step_reports(out_dir, invalidated)

    shared_kw = {"concept_token": token, "original_dir": input_dir, "force": force}

    reporter.info(f"Running {step_type} for project '{project.name}'.")
    substeps = (
        match.substeps if match is not None else default_substeps_for(step_type, config)
    )
    enabled_substeps = enabled_substep_ids(step_type, substeps)

    enabled_substeps = _apply_caption_overrides(
        shared_kw,
        enabled_substeps,
        working_dir,
        model_id=model_id,
        bboxes=bboxes,
        bbox_image=bbox_image,
    )

    invoke = STEP_INVOKE_MAP[step_type]
    result = invoke(
        working_dir, out_dir, config, **shared_kw, enabled_substeps=enabled_substeps
    )
    if step_type == "AuditStep" and isinstance(result, dict) and not result.get("pass"):
        reporter.warn(
            "Integrity audit found issues — review "
            "reports/AuditStep_report.json before training."
        )
    outcome = step_outcome(result)
    persist_step_outcome(state, step_type, enabled_substeps, outcome)
    if outcome.completed:
        reporter.ok(f"{step_type} complete. Report in {reports_dir_for(out_dir)}.")
    else:
        reporter.warn(describe_skip(step_type, outcome.reason))


def _resolve_step_config(project, step_type: str, match):
    """The step's config from the project, or built-in defaults with a note why.

    A disabled step and an undefined one both fall back to defaults, but they are
    reported differently: the disabled one has a tuned ``<step>.yaml`` sitting
    right there, and saying "not defined" would send the user looking for a file
    that already exists.
    """
    if match is not None:
        return match.config

    config_cls = step_config_class(step_type)
    if config_cls is None:
        raise click.ClickException(f"Unknown step type {step_type}")

    if step_type in project.disabled_types:
        slug = step_slug(step_type)
        click.echo(
            f"'{step_type}' is disabled in index.yaml — using built-in "
            f"defaults, not {slug}.yaml. Enable it to use your settings."
        )
    else:
        click.echo(
            f"'{step_type}' not defined in project '{project.name}' "
            f"pipeline — using built-in defaults."
        )
    return config_cls()


def _should_run_step(state, step_type: str, out_dir, working_dir, *, force: bool) -> bool:
    """Whether the step still needs running, raising if it cannot run at all.

    Returns ``False`` for a step already satisfied (so the caller just returns);
    raises ``ClickException`` when a prerequisite or the working dataset is missing.
    """
    from prepare_lora_kit.report import reporter

    if (
        not force
        and step_type == "ImportStep"
        and mark_legacy_import_satisfied(state, out_dir)
    ):
        reporter.info("ImportStep satisfied by existing working dataset.")
        return False

    if not force and state.is_done(step_type):
        reporter.info(f"{step_type} already done — skipping (use --force to re-run).")
        return False

    if not force:
        if mark_legacy_import_satisfied(state, out_dir):
            reporter.info("ImportStep satisfied by existing working dataset.")
        for req in step_prerequisites(step_type):
            if not state.is_done(req):
                raise click.ClickException(
                    f"{step_type} requires completed prerequisite {req}"
                )

    if step_type != "ImportStep" and not working_dir.exists():
        raise click.ClickException(
            "The working dataset does not exist. Run ImportStep first."
        )
    return True


def _apply_caption_overrides(
    shared_kw: dict,
    enabled_substeps: list[str],
    working_dir,
    *,
    model_id: str | None,
    bboxes,
    bbox_image,
) -> list[str]:
    """Fold the CaptionBboxStep-only flags into the invoke kwargs.

    Passing ``--bbox`` implies region annotation, so the substep is switched on
    even when the project has it disabled — otherwise the regions would be
    silently ignored.
    """
    from prepare_lora_kit.report import reporter

    if model_id:
        shared_kw["caption_runtime"] = {"model_id": model_id}
    if not bboxes:
        return enabled_substeps

    interaction, target, boxes = build_bbox_interaction(working_dir, bboxes, bbox_image)
    shared_kw["interaction"] = interaction
    if "annotate_regions" not in enabled_substeps:
        enabled_substeps = [*enabled_substeps, "annotate_regions"]
    reporter.info(f"Applying {len(boxes)} bbox region(s) to {target.name}.")
    return enabled_substeps
