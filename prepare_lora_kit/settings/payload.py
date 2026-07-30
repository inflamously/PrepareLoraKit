"""Build the Settings modal's payload: current values, choices, and placeholders.

Strictly cheap. Everything here is disk reads and torch-free catalogs, because
the modal has to open instantly — probing VRAM would drag ``torch`` into the UI
process and freeze it for seconds, and asking the Hub anything needs the
network. Both live behind their own buttons instead
(``bridge.detect_hardware`` / ``bridge.hf_status`` / ``bridge.check_model_access``).
"""
from __future__ import annotations

from typing import Any

from prepare_lora_kit.settings.model import VRAM_TIERS, AppSettings


def _caption_model_choices() -> list[dict[str, str]]:
    """Reuse the step-config dropdown so the two lists can never diverge."""
    from prepare_lora_kit.project.config_schema.steps import caption_bbox

    for spec in caption_bbox.FIELDS:
        if spec.name == "caption_model_id":
            return [dict(option) for option in spec.options]
    return []


def _pairs(choices: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"value": value, "label": label} for value, label in choices]


def choices() -> dict[str, list[dict[str, str]]]:
    """Select options for every field the modal renders."""
    from prepare_lora_kit.embedding import catalog as embedding_catalog
    from prepare_lora_kit.steps.caption_verifier import catalog as t2i_catalog
    from prepare_lora_kit.steps.upscale.seedvr2_catalog import list_seedvr2_dit_models

    return {
        "caption_model_id": _caption_model_choices(),
        "caption_model_task": _pairs(
            [
                ("auto", "Auto"),
                ("image-text-to-text", "Image + text to text"),
                ("image-to-text", "Image to text"),
            ]
        ),
        "t2i_model_id": _pairs(t2i_catalog.model_choices()),
        "coverage_embedding_model": _pairs(embedding_catalog.coverage_choices()),
        "seedvr2_dit_model": [
            {
                "value": model.name,
                "label": (
                    f"{model.parameter_size} {model.precision_quantization} "
                    f"({model.suitability_label})"
                ),
            }
            for model in list_seedvr2_dit_models()
        ],
        "caption_model_type": _pairs(
            [("auto", "Auto"), ("clip", "CLIP"), ("t5", "T5"), ("llm", "LLM")]
        ),
        "vram_tier": _pairs(
            [
                ("low", "Low (<=16 GB)"),
                ("mid", "Mid (<=24 GB)"),
                ("high", "High (<=32 GB)"),
                ("max", "Max (>32 GB)"),
            ]
        ),
    }


def placeholders() -> dict[str, str]:
    """What each field falls back to when left unset — shown as placeholder text.

    These are the *real* constants, imported rather than retyped, so the modal
    cannot advertise a default the code does not actually use.
    """
    from prepare_lora_kit.pipeline.configs import VaeGateConfig
    from prepare_lora_kit.steps.upscale.seedvr2_adapter import (
        DEFAULT_SEEDVR2_MODEL_DIR,
        default_seedvr2_submodule_dir,
    )
    from prepare_lora_kit.steps.upscale.seedvr2_catalog import DEFAULT_SEEDVR2_DIT_MODEL

    return {
        "hf_home": "~/.cache/huggingface",
        "vram_tier": "auto (detect at run time)",
        "cuda_device": "0",
        "seedvr2_submodule_dir": str(default_seedvr2_submodule_dir()),
        "seedvr2_model_dir": DEFAULT_SEEDVR2_MODEL_DIR,
        "caption_model_id": "required — a run fails without one",
        "caption_model_task": "auto",
        "t2i_model_id": "auto",
        "vae_model_id": VaeGateConfig().vae_model_id,
        "coverage_embedding_model": "auto",
        "seedvr2_dit_model": DEFAULT_SEEDVR2_DIT_MODEL,
        "caption_model_type": "auto",
    }


def configured_model_ids(settings: AppSettings) -> list[str]:
    """Model repos worth checking Hub access for.

    Only real repo ids: ``auto`` is resolved at run time and single-file paths
    are local. The VAE default is always included because it is the gated one
    that actually bites — it is the default even when nothing is configured.
    """
    from prepare_lora_kit.pipeline.configs import VaeGateConfig

    defaults = settings.project_defaults
    candidates = [
        defaults.caption_model_id,
        defaults.t2i_model_id,
        defaults.vae_model_id or VaeGateConfig().vae_model_id,
        defaults.coverage_embedding_model,
    ]
    return [
        value
        for value in candidates
        if value and value != "auto" and "::" not in value and not value.startswith(("/", ".", "~"))
    ]


def settings_payload(settings: AppSettings) -> dict[str, Any]:
    """The whole `get_settings` response."""
    from prepare_lora_kit.settings.hub import login_command
    from prepare_lora_kit.settings.store import settings_path

    return {
        "settings": settings.to_dict(),
        "choices": choices(),
        "placeholders": placeholders(),
        "vram_tiers": list(VRAM_TIERS),
        "settings_path": str(settings_path()),
        "login_command": login_command(),
        "model_ids": configured_model_ids(settings),
    }
