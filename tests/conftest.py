"""Suite-wide fixtures.

The autouse fixture below is a safety rail, not a convenience: without it every
test that creates a project would read the *developer's* real
``~/.prepare_lora_kit/settings.yaml``, making results depend on ambient machine
state, and any test that saved settings would overwrite it for real.
"""
import pytest

from prepare_lora_kit import paths, settings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Point the settings store at a throwaway file for every test."""
    monkeypatch.setattr(paths, "SETTINGS_PATH", tmp_path / "settings.yaml")
    settings.invalidate()
    yield
    settings.invalidate()
