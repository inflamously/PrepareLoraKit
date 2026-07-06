"""
Step 7 — Config Maker

Generates an ai-toolkit-compatible YAML training config (job: extension) from:
- The network profile (buckets, scheduler, optimizer defaults)
- Dataset statistics (n_images, repeats)
- User-provided training intent flags (novel concept, caption-gated, VRAM tier)
"""
from __future__ import annotations
from pathlib import Path

import yaml

from ...cancellation import CancelCheck, check_cancel
from ...networks.base import NetworkProfile
from ...utils import report as rpt
from .build import build_config
from .helpers import _count_images, _epoch_math


def run(
    dataset_dir: Path,
    network: NetworkProfile,
    concept_token: str | None = None,
    output_dir: Path | None = None,
    # training intent
    repeats: int = 1,
    batch: int = 1,
    grad_accum: int = 1,
    total_steps: int | None = None,
    sample_every_n_epochs: int = 2,
    novel_concept: bool = True,
    caption_dropout: float | None = None,
    concept_gated: bool = False,
    lr: float | None = None,
    rank: int | None = None,
    alpha: int | None = None,
    in_concept_sample: str | None = None,
    run_name: str | None = None,
    network_type: str | None = None,
    report_path: Path | None = None,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    style_mode = not concept_token
    rpt.step_header(7, "Config Maker")
    enabled = set(enabled_substeps or [
        "dataset_stats",
        "build_training_config",
        "write_training_config",
    ])

    output_dir = output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    n_images = _count_images(dataset_dir) if "dataset_stats" in enabled else 1
    check_cancel(cancel_check)
    if n_images == 0:
        rpt.warn("No images found in dataset — config will have placeholder counts.")
        n_images = 1

    em = _epoch_math(n_images, repeats, batch, grad_accum)
    steps_per_epoch = em["steps_per_epoch"]
    save_every = steps_per_epoch
    sample_every = steps_per_epoch * sample_every_n_epochs

    rpt.info(
        f"Epoch math:  {n_images} imgs × {repeats} repeats / ({batch} batch × {grad_accum} accum)"
        f" = {steps_per_epoch} steps/epoch"
    )
    rpt.info(f"  save_every={save_every}  sample_every={sample_every}")

    # Defaults
    lr = lr or network.lr_range[0]
    rank = rank or network.rank_range[0]
    alpha = alpha if alpha is not None else rank
    total_steps = total_steps or (steps_per_epoch * 10)

    # Caption dropout
    # Style training: higher dropout so style bleeds into unconditioned space.
    # Concept training: 0 if concept-gated, else a small value.
    if caption_dropout is None:
        if style_mode:
            caption_dropout = 0.1
        elif concept_gated:
            caption_dropout = 0.0
        else:
            caption_dropout = 0.05

    # ── Cross-checks ──────────────────────────────────────────────────────────
    ratio = lr / (alpha / rank) if alpha and rank else 0
    lo, hi = network.lr_alpha_rank_ratio_range
    if not (lo <= ratio <= hi):
        rpt.warn(
            f"lr/alpha_rank ratio {ratio:.4f} outside recommended [{lo}, {hi}]. "
            f"(lr={lr}, alpha={alpha}, rank={rank})"
        )

    if not style_mode and caption_dropout > 0.05 and concept_gated:
        rpt.warn(f"caption_dropout={caption_dropout} but concept_gated=True — "
                 "concept may leak into unconditioned generations. Consider 0.")

    if style_mode:
        rpt.info("Style training mode: no concept token, caption_dropout=0.1")

    lo_lr, hi_lr = network.lr_range
    if not (lo_lr <= lr <= hi_lr):
        rpt.warn(f"lr={lr} outside recommended range [{lo_lr}, {hi_lr}] for {network.display_name}")

    if "build_training_config" not in enabled:
        report = {
            "skipped": True,
            "reason": "build_training_config disabled",
            "epoch_math": em,
            "substeps": {
                "dataset_stats": {"enabled": "dataset_stats" in enabled},
                "build_training_config": {"enabled": False},
                "write_training_config": {"enabled": "write_training_config" in enabled},
            },
        }
        rpt.save_report(report, report_path or (output_dir / "step7_report.json"))
        return report

    # ── Build config ──────────────────────────────────────────────────────────
    dataset_abs = str(dataset_dir.resolve())
    output_abs = str(output_dir.resolve())

    config_name = run_name or (concept_token.replace(" ", "_") if concept_token else "style_lora")

    if style_mode:
        sample_prompt = in_concept_sample or "high quality photograph, natural lighting"
    else:
        sample_prompt = in_concept_sample or f"{concept_token}, high quality photograph"

    resolutions = network.train_resolutions or [network.max_bucket_side]
    sample_w, sample_h = network.resolution_buckets[0]

    config = build_config(
        network=network,
        dataset_abs=dataset_abs,
        output_abs=output_abs,
        config_name=config_name,
        rank=rank,
        alpha=alpha,
        save_every=save_every,
        caption_dropout=caption_dropout,
        repeats=repeats,
        resolutions=resolutions,
        batch=batch,
        total_steps=total_steps,
        grad_accum=grad_accum,
        lr=lr,
        novel_concept=novel_concept,
        sample_w=sample_w,
        sample_h=sample_h,
        sample_prompt=sample_prompt,
        sample_every=sample_every,
        concept_token=concept_token,
        network_type=network_type,
    )
    check_cancel(cancel_check)
    out_path = output_dir / "run_config.yaml"
    if "write_training_config" in enabled:
        with open(out_path, "w") as f:
            yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False)
        rpt.ok(f"Config saved → {out_path}")
    else:
        rpt.info("Write-config substep disabled; run_config.yaml was not written.")

    rpt.info(f"EMA: {'off (novel concept)' if novel_concept else 'on (known concept)'}")
    rpt.info(f"Caption dropout: {caption_dropout}")
    rpt.info(f"LR={lr}  rank={rank}  alpha={alpha}  steps={total_steps}")

    report = {
        "epoch_math": em,
        "save_every": save_every,
        "sample_every": sample_every,
        "lr": lr,
        "rank": rank,
        "alpha": alpha,
        "total_steps": total_steps,
        "novel_concept": novel_concept,
        "caption_dropout": caption_dropout,
        "config_path": str(out_path) if "write_training_config" in enabled else None,
        "substeps": {
            "dataset_stats": {"enabled": "dataset_stats" in enabled},
            "build_training_config": {"enabled": "build_training_config" in enabled},
            "write_training_config": {"enabled": "write_training_config" in enabled},
        },
    }
    check_cancel(cancel_check)
    rpt.save_report(report, report_path or (output_dir / "step7_report.json"))
    return report
