"""The app-wide settings document: dataclasses plus tolerant dict conversion.

Every field is optional and defaults to ``None``, which always means *"not
configured — use the app default"*. That single convention is what keeps the
whole feature a no-op until the user actually sets something: seeding skips
``None`` fields entirely, so a default settings file produces byte-identical
project YAML to the one the app wrote before settings existed.

Conversion is deliberately forgiving in one direction only: unknown keys and
blank strings are dropped on the way in (a settings file written by a newer
build must not break an older one), but a *known* key holding an invalid value
raises, so a typo surfaces in the Settings modal instead of silently reverting.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

SETTINGS_VERSION = 1

VRAM_TIERS = ("low", "mid", "high", "max")
CAPTION_MODEL_TASKS = ("auto", "image-text-to-text", "image-to-text")
CAPTION_MODEL_TYPES = ("auto", "clip", "t5", "llm")


def _clean(value: Any) -> str | None:
    """Normalize an incoming scalar to ``str`` or ``None``.

    Blank and whitespace-only strings collapse to ``None`` so that clearing a
    field in the UI is indistinguishable from never having set it.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _one_of(value: str | None, allowed: tuple[str, ...], label: str) -> str | None:
    if value is not None and value not in allowed:
        raise ValueError(f"{label} must be one of {list(allowed)}, got '{value}'.")
    return value


@dataclass(frozen=True)
class HuggingFaceSettings:
    """Hub-related machine settings.

    Note there is no token field, by design: the token is whatever
    ``hf auth login`` already wrote. See :mod:`prepare_lora_kit.settings.hub`.
    """

    home: str | None = None      # HF_HOME; None -> huggingface's own default

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> HuggingFaceSettings:
        data = data or {}
        return cls(home=_clean(data.get("home")))


@dataclass(frozen=True)
class HardwareSettings:
    """Facts about this machine, applied as fallbacks rather than stored per project."""

    vram_tier: str | None = None             # None -> "auto" (probe at run time)
    cuda_device: str | None = None           # None -> device 0
    seedvr2_submodule_dir: str | None = None  # None -> third_party/seedvr2
    seedvr2_model_dir: str | None = None      # None -> ~/.cache/prepare_lora_kit/seedvr2

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> HardwareSettings:
        data = data or {}
        return cls(
            vram_tier=_one_of(_clean(data.get("vram_tier")), VRAM_TIERS, "vram_tier"),
            cuda_device=_clean(data.get("cuda_device")),
            seedvr2_submodule_dir=_clean(data.get("seedvr2_submodule_dir")),
            seedvr2_model_dir=_clean(data.get("seedvr2_model_dir")),
        )


@dataclass(frozen=True)
class ProjectDefaults:
    """Values copied into a project's YAML when that project is created.

    These are a one-time seed, never a live override: once a project exists its
    YAML is the only source of truth, so changing a value here never alters how
    an existing project runs.
    """

    caption_model_id: str | None = None
    caption_model_task: str | None = None
    t2i_model_id: str | None = None
    vae_model_id: str | None = None
    coverage_embedding_model: str | None = None
    seedvr2_dit_model: str | None = None
    caption_model_type: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ProjectDefaults:
        data = data or {}
        return cls(
            caption_model_id=_clean(data.get("caption_model_id")),
            caption_model_task=_one_of(
                _clean(data.get("caption_model_task")), CAPTION_MODEL_TASKS, "caption_model_task"
            ),
            t2i_model_id=_clean(data.get("t2i_model_id")),
            vae_model_id=_clean(data.get("vae_model_id")),
            coverage_embedding_model=_clean(data.get("coverage_embedding_model")),
            seedvr2_dit_model=_clean(data.get("seedvr2_dit_model")),
            caption_model_type=_one_of(
                _clean(data.get("caption_model_type")), CAPTION_MODEL_TYPES, "caption_model_type"
            ),
        )


@dataclass(frozen=True)
class AppSettings:
    """The whole settings document. Construct with no arguments for "nothing configured"."""

    huggingface: HuggingFaceSettings = HuggingFaceSettings()
    hardware: HardwareSettings = HardwareSettings()
    project_defaults: ProjectDefaults = ProjectDefaults()

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AppSettings:
        data = data or {}
        if not isinstance(data, dict):
            raise ValueError("Settings must be a mapping.")
        return cls(
            huggingface=HuggingFaceSettings.from_dict(data.get("huggingface")),
            hardware=HardwareSettings.from_dict(data.get("hardware")),
            project_defaults=ProjectDefaults.from_dict(data.get("project_defaults")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for YAML and for the UI bridge (the same shape both ways)."""
        return {"version": SETTINGS_VERSION, **asdict(self)}

    def is_empty(self) -> bool:
        """True when nothing at all is configured — used to skip writing a no-op file."""
        return all(
            getattr(group, field.name) is None
            for group in (self.huggingface, self.hardware, self.project_defaults)
            for field in fields(group)
        )
