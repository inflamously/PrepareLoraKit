"""
PrepareLoraKit CLI — `python main.py <command> [options]`

Commands:
  run   Full pipeline
  s1    Source quality gates + manual review
  s2    Curation (dedupe + coverage)
  s3    Upscale (optional)
  s4    VAE reconstruction gate
  s5    Caption (bbox annotation + Qwen3-VL)
  s6    Pairing & integrity audit
  s7    Config maker
  s8    Bucket dry-run
  networks   List available network profiles
"""
from __future__ import annotations
from pathlib import Path

import click

from .networks import registry


def _load_network(name: str):
    try:
        return registry.load(name)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--network")


# ── Shared options ────────────────────────────────────────────────────────────

_input_opt = click.option("--input", "-i", "input_dir", required=True,
                          type=click.Path(exists=True, file_okay=False, path_type=Path),
                          help="Dataset directory")
_output_opt = click.option("--output", "-o", "output_dir",
                           type=click.Path(file_okay=False, path_type=Path),
                           default=None, help="Output directory (default: same as input)")
_network_opt = click.option("--network", "-n", default="flux-klein-9b", show_default=True,
                            help="Network profile name")
_token_opt = click.option("--token", "-t", default=None,
                          help="Concept token / trigger word. Omit for style training.")


@click.group()
def cli():
    """PrepareLoraKit — LoRA dataset preparation pipeline."""


# ── run ───────────────────────────────────────────────────────────────────────

@cli.command()
@_input_opt
@_output_opt
@_network_opt
@_token_opt
@click.option("--auto-only", is_flag=True, help="Skip manual review in Step 1")
@click.option("--manual-all", is_flag=True, help="Force manual review of every image in Step 1")
@click.option("--skip-clip", is_flag=True, help="Skip CLIP-based checks in Step 2")
@click.option("--skip-upscale", is_flag=True, help="Skip Step 3 entirely")
@click.option("--qwen-model", default="Qwen/Qwen2-VL-7B-Instruct", show_default=True,
              help="Qwen VL model HF ID for Step 5")
@click.option("--overwrite-captions", is_flag=True, help="Re-caption images that already have .txt")
@click.option("--novel-concept/--known-concept", default=True, show_default=True,
              help="EMA gate: novel concept = off (default)")
@click.option("--concept-gated", is_flag=True, help="Force caption_dropout=0")
@click.option("--lr", type=float, default=None, help="Learning rate (default from network profile)")
@click.option("--rank", type=int, default=None, help="LoRA rank")
@click.option("--alpha", type=int, default=None, help="LoRA alpha")
@click.option("--steps", "total_steps", type=int, default=None, help="Total training steps")
@click.option("--cache-mode", is_flag=True, help="Write cache_info.json in Step 8")
@click.option("--force", is_flag=True, help="Re-run all steps even if already completed")
def run(input_dir, output_dir, network, token, auto_only, manual_all, skip_clip,
        skip_upscale, qwen_model, overwrite_captions, novel_concept, concept_gated,
        lr, rank, alpha, total_steps, cache_mode, force):
    """Run the full 8-step pipeline."""
    net = _load_network(network)
    output_dir = output_dir or input_dir

    from .pipeline import run_all
    run_all(
        dataset_dir=input_dir,
        network=net,
        concept_token=token,
        output_dir=output_dir,
        auto_only=auto_only,
        manual_all=manual_all,
        skip_clip=skip_clip,
        skip_upscale=skip_upscale,
        qwen_model_id=qwen_model,
        overwrite_captions=overwrite_captions,
        novel_concept=novel_concept,
        concept_gated=concept_gated,
        lr=lr,
        rank=rank,
        alpha=alpha,
        total_steps=total_steps,
        cache_mode=cache_mode,
        force=force,
    )


# ── s1 ───────────────────────────────────────────────────────────────────────

@cli.command()
@_input_opt
@_output_opt
@click.option("--auto-only", is_flag=True)
@click.option("--manual-all", is_flag=True)
def s1(input_dir, output_dir, auto_only, manual_all):
    """Step 1: Source image quality gates + manual review."""
    from .steps import s1_source
    out = output_dir or (input_dir / "s1_output")
    s1_source.run(input_dir, out, auto_only=auto_only, manual_all=manual_all)


# ── s2 ───────────────────────────────────────────────────────────────────────

@cli.command()
@_input_opt
@_output_opt
@click.option("--skip-clip", is_flag=True)
@click.option("--no-auto-dedupe", is_flag=True)
def s2(input_dir, output_dir, skip_clip, no_auto_dedupe):
    """Step 2: Dedupe + CLIP coverage."""
    from .steps import s2_curate
    s2_curate.run(input_dir, output_dir=output_dir, auto_dedupe=not no_auto_dedupe,
                  skip_clip=skip_clip)


# ── s3 ───────────────────────────────────────────────────────────────────────

@cli.command()
@_input_opt
@_output_opt
@click.option("--upscale-target", type=int, default=1024, show_default=True)
def s3(input_dir, output_dir, upscale_target):
    """Step 3: Selective upscaling (SeedVR or Lanczos fallback)."""
    from .steps import s3_upscale
    s3_upscale.run(input_dir, output_dir=output_dir, upscale_target=upscale_target)


# ── s4 ───────────────────────────────────────────────────────────────────────

@cli.command()
@_input_opt
@_output_opt
@_network_opt
def s4(input_dir, output_dir, network):
    """Step 4: VAE reconstruction gate."""
    net = _load_network(network)
    from .steps import s4_vae_gate
    s4_vae_gate.run(input_dir, network=net, output_dir=output_dir)


# ── s5 ───────────────────────────────────────────────────────────────────────

@cli.command()
@_input_opt
@_output_opt
@_token_opt
@click.option("--qwen-model", default="Qwen/Qwen2-VL-7B-Instruct", show_default=True)
@click.option("--overwrite", is_flag=True)
def s5(input_dir, output_dir, token, qwen_model, overwrite):
    """Step 5: Bbox annotation + Qwen3-VL BFL-structured captioning."""
    from .steps import s5_caption
    s5_caption.run(input_dir, concept_token=token, output_dir=output_dir or input_dir,
                   qwen_model_id=qwen_model, overwrite=overwrite)


# ── s6 ───────────────────────────────────────────────────────────────────────

@cli.command()
@_input_opt
@_network_opt
def s6(input_dir, network):
    """Step 6: Pairing & integrity audit."""
    net = _load_network(network)
    from .steps import s6_audit
    s6_audit.run(input_dir, network=net)


# ── s7 ───────────────────────────────────────────────────────────────────────

@cli.command()
@_input_opt
@_output_opt
@_network_opt
@_token_opt
@click.option("--novel-concept/--known-concept", default=True)
@click.option("--concept-gated", is_flag=True)
@click.option("--lr", type=float, default=None)
@click.option("--rank", type=int, default=None)
@click.option("--alpha", type=int, default=None)
@click.option("--steps", "total_steps", type=int, default=None)
@click.option("--in-concept-sample", default=None,
              help="In-concept sample prompt (default: TOKEN, high quality photograph)")
@click.option("--run-name", default=None,
              help="Output run name (required when --token is omitted for style training)")
def s7(input_dir, output_dir, network, token, novel_concept, concept_gated,
       lr, rank, alpha, total_steps, in_concept_sample, run_name):
    """Step 7: Generate ai-toolkit TOML training config."""
    net = _load_network(network)
    from .steps import s7_config
    s7_config.run(
        input_dir, network=net, concept_token=token,
        output_dir=output_dir or input_dir,
        novel_concept=novel_concept, concept_gated=concept_gated,
        lr=lr, rank=rank, alpha=alpha, total_steps=total_steps,
        in_concept_sample=in_concept_sample,
        run_name=run_name,
    )


# ── s8 ───────────────────────────────────────────────────────────────────────

@cli.command()
@_input_opt
@_output_opt
@_network_opt
@click.option("--cache-mode", is_flag=True)
def s8(input_dir, output_dir, network, cache_mode):
    """Step 8: Bucket dry-run — simulate bucketing, flag thin buckets."""
    net = _load_network(network)
    from .steps import s8_bucket
    s8_bucket.run(input_dir, network=net, output_dir=output_dir or input_dir,
                  cache_mode=cache_mode)


# ── networks ──────────────────────────────────────────────────────────────────

@cli.command()
def networks():
    """List available network profiles."""
    from .utils.report import console
    from rich.table import Table
    from rich import box

    names = registry.list_networks()
    t = Table(title="Available Network Profiles", box=box.SIMPLE)
    t.add_column("Name", style="cyan")
    for n in names:
        t.add_row(n)
    console.print(t)
