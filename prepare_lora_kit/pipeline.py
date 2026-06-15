"""
Pipeline orchestrator — runs all 8 steps in order, respecting state for resume.
"""
from __future__ import annotations
from pathlib import Path

from .networks.base import NetworkProfile
from .utils import report as rpt
from .utils.state import RunState


def run_all(
    dataset_dir: Path,
    network: NetworkProfile,
    concept_token: str,
    output_dir: Path | None = None,
    # Step 1 options
    auto_only: bool = False,
    manual_all: bool = False,
    s1_scorers: list[dict] | None = None,
    # Step 2 options
    auto_dedupe: bool = True,
    skip_clip: bool = False,
    # Step 3 options
    upscale_target: int = 1024,
    skip_upscale: bool = False,
    # Step 5 options
    qwen_model_id: str = "Qwen/Qwen2-VL-7B-Instruct",
    overwrite_captions: bool = False,
    # Step 7 options
    novel_concept: bool = True,
    concept_gated: bool = False,
    lr: float | None = None,
    rank: int | None = None,
    alpha: int | None = None,
    total_steps: int | None = None,
    # Step 8 options
    cache_mode: bool = False,
    # Extension points
    extra_steps: list[dict] | None = None,
    # General
    force: bool = False,
) -> None:
    """
    extra_steps: optional list of additional tool steps run after s8.
    Each entry: {
        "key":      str,       # state-tracking key, e.g. "s9_qwen_bench"
        "label":    str,       # display label (defaults to key)
        "fn":       callable,  # fn(dataset_dir, output_dir / key, **kwargs) -> dict
        "kwargs":   dict,      # extra kwargs passed to fn (optional)
        "optional": bool,      # if True, failure is warned not raised (optional)
    }
    """
    output_dir = output_dir or dataset_dir
    state = RunState(output_dir)

    def _skip(step: str) -> bool:
        if force:
            return False
        if state.is_done(step):
            rpt.info(f"Step {step} already done — skipping (use --force to re-run).")
            return True
        return False

    # ── Step 1 ────────────────────────────────────────────────────────────────
    if not _skip("s1"):
        from .steps import s1_source
        s1_out = output_dir / "s1_output"
        s1_source.run(dataset_dir, s1_out, auto_only=auto_only, manual_all=manual_all,
                      scorers=s1_scorers)
        state.mark_done("s1")
        dataset_dir = s1_out  # subsequent steps use kept-image set

    # ── Step 2 ────────────────────────────────────────────────────────────────
    if not _skip("s2"):
        from .steps import s2_curate
        s2_curate.run(dataset_dir, output_dir=output_dir, auto_dedupe=auto_dedupe, skip_clip=skip_clip)
        state.mark_done("s2")

    # ── Step 3 ────────────────────────────────────────────────────────────────
    if not skip_upscale and not _skip("s3"):
        from .steps import s3_upscale
        s3_upscale.run(dataset_dir, output_dir=output_dir / "s3_upscaled", upscale_target=upscale_target)
        state.mark_done("s3")

    # ── Step 4 ────────────────────────────────────────────────────────────────
    if not _skip("s4"):
        from .steps import s4_vae_gate
        s4_vae_gate.run(dataset_dir, network=network, output_dir=output_dir)
        state.mark_done("s4")

    # ── Step 5 ────────────────────────────────────────────────────────────────
    if not _skip("s5"):
        from .steps import s5_caption
        s5_caption.run(
            dataset_dir,
            concept_token=concept_token,
            output_dir=dataset_dir,  # captions alongside images
            qwen_model_id=qwen_model_id,
            overwrite=overwrite_captions,
        )
        state.mark_done("s5")

    # ── Step 6 ────────────────────────────────────────────────────────────────
    if not _skip("s6"):
        from .steps import s6_audit
        result = s6_audit.run(dataset_dir, network=network)
        state.mark_done("s6", {"pass": result.get("pass", False)})
        if not result.get("pass"):
            rpt.warn("Integrity audit found issues — review step6_report.json before training.")

    # ── Step 7 ────────────────────────────────────────────────────────────────
    if not _skip("s7"):
        from .steps import s7_config
        s7_config.run(
            dataset_dir,
            network=network,
            concept_token=concept_token,
            output_dir=output_dir,
            novel_concept=novel_concept,
            concept_gated=concept_gated,
            lr=lr,
            rank=rank,
            alpha=alpha,
            total_steps=total_steps,
        )
        state.mark_done("s7")

    # ── Step 8 ────────────────────────────────────────────────────────────────
    if not _skip("s8"):
        from .steps import s8_bucket
        s8_bucket.run(dataset_dir, network=network, output_dir=output_dir, cache_mode=cache_mode)
        state.mark_done("s8")

    # ── Extra steps (user-supplied) ───────────────────────────────────────────
    for step in (extra_steps or []):
        key = step["key"]
        label = step.get("label", key)
        optional = step.get("optional", False)
        if not _skip(key):
            try:
                step["fn"](dataset_dir, output_dir / key, **step.get("kwargs", {}))
                state.mark_done(key)
            except Exception as exc:
                if optional:
                    rpt.warn(f"{label}: failed (optional) — {exc}")
                else:
                    raise

    rpt.ok("Pipeline complete. Review reports and run_config.toml before training.")
