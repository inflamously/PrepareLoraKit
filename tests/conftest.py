"""Suite-wide fixtures.

Both autouse fixtures below are safety rails, not conveniences. Without them
every test that creates a project would read the *developer's* real
``~/.prepare_lora_kit/``, making results depend on ambient machine state — and
any test that wrote would damage it for real.
"""
from pathlib import Path

import pytest

from prepare_lora_kit import paths, settings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Point the settings store at a throwaway file for every test."""
    monkeypatch.setattr(paths, "SETTINGS_PATH", tmp_path / "settings.yaml")
    settings.invalidate()
    yield
    settings.invalidate()


@pytest.fixture(autouse=True)
def isolated_projects(tmp_path, monkeypatch):
    """Point the project store at a throwaway projects dir for every test.

    Stricter than ``isolated_settings`` needs to be: project writers create,
    rename and ``shutil.rmtree`` whole *directories*, and their real home is the
    developer's ``~/.prepare_lora_kit/projects`` — unversioned, unbacked-up work.
    One bad path in one test would destroy it, so this is autouse rather than
    opt-in: a newly added test that forgets to ask for isolation still gets it.
    """
    projects = tmp_path / "projects"
    # Deliberately not created: on a fresh machine ~/.prepare_lora_kit/projects
    # does not exist either, so every test exercises that first-run path.
    # Belt and braces: if a future test re-points PROJECTS_DIR at something real,
    # fail here rather than in shutil.rmtree.
    assert Path.home() not in projects.parents
    monkeypatch.setattr(paths, "PROJECTS_DIR", projects)
    return projects
