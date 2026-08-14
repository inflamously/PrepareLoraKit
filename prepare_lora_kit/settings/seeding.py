"""Copy configured global defaults into a *new* project's pipeline data, once.

Not a fallback layer: once the YAML exists it is the only source of truth, so changing
a global later never alters an existing project.
"""
from __future__ import annotations

from typing import Any

from prepare_lora_kit.settings.model import AppSettings

# (step type, key in the project YAML, settings group, field on that group).
# vram_tier is one machine fact that seeds two steps — a user with a 16 GB card
# should not have to say so twice.
_SEEDS: tuple[tuple[str, str, str, str], ...] = (
    ("CurateStep", "coverage_embedding_model", "project_defaults", "coverage_embedding_model"),
    ("UpscaleStep", "seedvr2_dit_model", "project_defaults", "seedvr2_dit_model"),
    ("CaptionBboxStep", "caption_model_id", "project_defaults", "caption_model_id"),
    ("CaptionBboxStep", "caption_model_task", "project_defaults", "caption_model_task"),
    ("CaptionBboxStep", "vram_tier", "hardware", "vram_tier"),
    ("CaptionVerifierStep", "t2i_model_id", "project_defaults", "t2i_model_id"),
    ("CaptionVerifierStep", "vram_tier", "hardware", "vram_tier"),
    ("VaeGateStep", "vae_model_id", "project_defaults", "vae_model_id"),
    ("AuditStep", "caption_model_type", "project_defaults", "caption_model_type"),
)


def seeded_fields(settings: AppSettings) -> dict[str, dict[str, Any]]:
    """The configured seeds, grouped as ``{step_type: {field: value}}``."""
    seeds: dict[str, dict[str, Any]] = {}
    for step_type, field, group_name, group_field in _SEEDS:
        value = getattr(getattr(settings, group_name), group_field)
        if value is None:
            continue
        seeds.setdefault(step_type, {})[field] = value
    return seeds


def apply_settings_to_pipeline(
    pipeline: list[dict[str, Any]],
    settings: AppSettings | None = None,
) -> list[dict[str, Any]]:
    """Return ``pipeline`` with configured globals applied. Never mutates the input."""
    if settings is None:
        from prepare_lora_kit.settings.store import load_settings

        settings = load_settings()
    seeds = seeded_fields(settings)
    if not seeds:
        return pipeline
    return [
        {**step, **seeds[step.get("type")]} if step.get("type") in seeds else step
        for step in pipeline
    ]
