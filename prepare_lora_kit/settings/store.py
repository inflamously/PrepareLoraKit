"""Read and write ``~/.prepare_lora_kit/settings.yaml``.

The file lives outside the checkout so it survives a re-clone and is shared by
every working copy; ``prepare_lora_kit.paths`` owns the location.

Absent, empty and partial files all resolve to a fully defaulted
:class:`AppSettings` — settings are strictly additive, and the app must behave
exactly as it did before this feature existed until the user configures
something. Only genuinely malformed YAML raises, and it names the file.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from prepare_lora_kit import paths
from prepare_lora_kit.settings.model import AppSettings
from prepare_lora_kit.utils.atomic_yaml import write_yaml_atomic

# Cached by resolved path rather than as a bare value: tests redirect
# paths.SETTINGS_PATH, and keying on the path means such a redirect can never be
# served a stale document from a previous location.
_cache: tuple[Path, AppSettings] | None = None


def settings_path() -> Path:
    """The active settings file.

    Read through the module attribute (not a from-import) so that redirecting
    ``paths.SETTINGS_PATH`` in a test is honored here.
    """
    return Path(paths.SETTINGS_PATH)


def invalidate() -> None:
    """Drop the in-process cache so the next load re-reads from disk."""
    global _cache
    _cache = None


def load_settings() -> AppSettings:
    """Return the current settings, reading from disk at most once per path."""
    global _cache
    path = settings_path()
    if _cache is not None and _cache[0] == path:
        return _cache[1]
    settings = read_settings(path)
    _cache = (path, settings)
    return settings


def read_settings(path: Path) -> AppSettings:
    """Parse one settings file, uncached. Missing or empty -> all defaults."""
    if not path.exists():
        return AppSettings()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Could not parse settings file {path}: {exc}") from exc
    if data is None:
        return AppSettings()
    if not isinstance(data, dict):
        raise ValueError(f"Settings file {path} must contain a mapping, not {type(data).__name__}.")
    return AppSettings.from_dict(data)


def save_settings(settings: AppSettings) -> AppSettings:
    """Write settings atomically and refresh the cache. Returns what was stored."""
    global _cache
    path = settings_path()
    # Same tmp+replace dance as steps/caption_verifier/captions.write_caption_atomic:
    # a half-written settings file would break every subsequent launch.
    write_yaml_atomic(path, settings.to_dict(), secure_parent=True)
    _cache = (path, settings)
    return settings


def save_settings_dict(data: dict) -> AppSettings:
    """Validate a raw payload (e.g. straight from the UI bridge) and store it."""
    return save_settings(AppSettings.from_dict(data))


def apply_environment(settings: AppSettings | None = None) -> None:
    """Push environment-level settings into ``os.environ``.

    Must run before anything imports ``huggingface_hub``, which resolves
    ``HF_HOME`` at import time — calling this later is a silent no-op. That is
    why it is invoked from the CLI entry point rather than lazily.

    ``setdefault`` on purpose: an ``HF_HOME`` the user exported in their shell
    outranks the one stored in the settings file.
    """
    settings = settings if settings is not None else load_settings()
    if settings.huggingface.home:
        os.environ.setdefault("HF_HOME", str(Path(settings.huggingface.home).expanduser()))
