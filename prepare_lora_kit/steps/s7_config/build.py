from __future__ import annotations

from ...networks.base import NetworkProfile
from ...networks.config import NetworkConfig
from .helpers import _deep_merge

SAMPLE_CONTROL = "dog on motorcycle"


def build_config(
    network: NetworkProfile,
    dataset_abs: str,
    output_abs: str,
    config_name: str,
    rank: int,
    alpha: int,
    save_every: int,
    caption_dropout: float,
    repeats: int,
    resolutions: list,
    batch: int,
    total_steps: int,
    grad_accum: int,
    lr: float,
    novel_concept: bool,
    sample_w: int,
    sample_h: int,
    sample_prompt: str,
    sample_every: int,
    concept_token: str | None,
    network_type: str | None = None,
) -> dict:
    tmpl = network.config_template

    # ── Adapter-network block ─────────────────────────────────────────────────
    # The profile's config_template.network defines the default adapter type; an
    # optional per-run `network_type` override (from the project config) wins.
    # NetworkConfig validates the block and renders a clean, type-appropriate dict.
    net_raw = dict(tmpl.get("network", {}) or {})
    if network_type:
        net_raw["type"] = network_type
    net_block = (
        NetworkConfig.from_dict(net_raw)
        .with_rank_alpha(rank, alpha)
        .to_toolkit_dict()
    )

    # ── Assemble the ai-toolkit `config.process[0]` block ─────────────────────
    # Network-static sections come from the profile's config_template; per-run
    # values are overlaid here via _deep_merge.
    process = {
        "type": "diffusion_trainer",
        "training_folder": output_abs,
        "sqlite_db_path": None,
        "device": "cuda",
        "trigger_word": concept_token,
        "performance_log_every": 10,
        "network": net_block,
        "save": _deep_merge(
            tmpl.get("save", {}),
            {"save_every": save_every, "max_step_saves_to_keep": 4},
        ),
        "datasets": [
            {
                "folder_path": dataset_abs,
                "caption_ext": "txt",
                "caption_dropout_rate": caption_dropout,
                "default_caption": "",
                "cache_latents_to_disk": True,
                "is_reg": False,
                "network_weight": 1,
                "num_repeats": repeats,
                "resolution": resolutions,
            }
        ],
        "train": _deep_merge(
            tmpl.get("train", {}),
            {
                "batch_size": batch,
                "steps": total_steps,
                "gradient_accumulation": grad_accum,
                "lr": lr,
                "do_differential_guidance": network.requires_diff_guidance,
                "ema_config": {"use_ema": not novel_concept, "ema_decay": 0.99},
            },
        ),
        "model": tmpl.get("model", {}),
        "sample": _deep_merge(
            tmpl.get("sample", {}),
            {
                "sampler": "flowmatch" if network.noise_scheduler == "flowmatch" else "ddpm",
                "sample_every": sample_every,
                "width": sample_w,
                "height": sample_h,
                "samples": [{"prompt": sample_prompt}, {"prompt": SAMPLE_CONTROL}],
            },
        ),
        "logging": {"log_every": 1, "use_ui_logger": False},
    }

    config = {
        "job": "extension",
        "config": {"name": config_name, "process": [process]},
        "meta": {"name": config_name, "version": "1.0"},
    }
    return config
