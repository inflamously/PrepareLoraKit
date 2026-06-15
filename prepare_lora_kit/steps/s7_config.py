"""
Step 7 — Config Maker

Generates an ai-toolkit-compatible TOML training config from:
- The network profile (buckets, scheduler, optimizer defaults)
- Dataset statistics (n_images, repeats)
- User-provided training intent flags (novel concept, caption-gated, VRAM tier)
"""
from __future__ import annotations
import copy
import math
from pathlib import Path
from typing import Any

import toml

from ..networks.base import NetworkProfile
from ..utils import image as img_utils
from ..utils import report as rpt

SAMPLE_CONTROL = "dog on motorcycle"


def _count_images(dataset_dir: Path) -> int:
    return len(img_utils.iter_images(dataset_dir))


def _epoch_math(
    n_images: int,
    repeats: int,
    batch: int,
    grad_accum: int,
) -> dict:
    steps_per_epoch = math.ceil(n_images * repeats / (batch * grad_accum))
    return {
        "n_images": n_images,
        "repeats": repeats,
        "batch": batch,
        "grad_accum": grad_accum,
        "steps_per_epoch": steps_per_epoch,
    }


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


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
) -> dict:
    style_mode = not concept_token
    rpt.step_header(7, "Config Maker")

    output_dir = output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    n_images = _count_images(dataset_dir)
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

    if network.requires_diff_guidance:
        rpt.warn("This network requires diff_guidance — add it manually to the config.")

    lo_lr, hi_lr = network.lr_range
    if not (lo_lr <= lr <= hi_lr):
        rpt.warn(f"lr={lr} outside recommended range [{lo_lr}, {hi_lr}] for {network.display_name}")

    # ── Build config ──────────────────────────────────────────────────────────
    dataset_abs = str(dataset_dir.resolve())
    output_abs = str(output_dir.resolve())

    config_name = run_name or (concept_token.replace(" ", "_") if concept_token else "style_lora")

    if style_mode:
        sample_prompt = in_concept_sample or "high quality photograph, natural lighting"
    else:
        sample_prompt = in_concept_sample or f"{concept_token}, high quality photograph"

    overrides: dict[str, Any] = {
        "config": {
            "name": config_name,
            "process": [
                {
                    "type": "custom_sd_trainer",
                    "training_folder": output_abs,
                    "device": "cuda:0",
                    "network": {
                        "type": "lora",
                        "linear": rank,
                        "linear_alpha": alpha,
                    },
                    "save": {
                        "dtype": "float16",
                        "save_every": save_every,
                        "max_step_saves_to_keep": 4,
                    },
                    "datasets": [
                        {
                            "folder_path": dataset_abs,
                            "caption_ext": "txt",
                            "caption_dropout_rate": caption_dropout,
                            "shuffle_tokens": False,
                            "cache_latents_to_disk": True,
                            "resolution": [
                                list(bucket) for bucket in network.resolution_buckets
                            ],
                        }
                    ],
                    "train": {
                        **network.config_template.get("train", {}),
                        "batch_size": batch,
                        "steps": total_steps,
                        "gradient_accumulation_steps": grad_accum,
                        "lr": lr,
                        "ema": {"enabled": not novel_concept, "decay": 0.99},
                        "caption_dropout": caption_dropout,
                    },
                    "model": network.config_template.get("model", {}),
                    "sample": {
                        "sampler": "flowmatch" if network.noise_scheduler == "flowmatch" else "ddpm",
                        "sample_every": sample_every,
                        "width": network.resolution_buckets[0][0],
                        "height": network.resolution_buckets[0][1],
                        "prompts": [sample_prompt, SAMPLE_CONTROL],
                        "neg": "",
                        "seed": 42,
                        "walk_seed": True,
                        "guidance_scale": 4.0,
                        "sample_steps": 20,
                        "force_first_sample": True,
                    },
                }
            ],
        }
    }

    config = _deep_merge(network.config_template, overrides)
    out_path = output_dir / "run_config.toml"
    with open(out_path, "w") as f:
        toml.dump(config, f)

    rpt.ok(f"Config saved → {out_path}")
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
        "config_path": str(out_path),
    }
    rpt.save_report(report, output_dir / "step7_report.json")
    return report
