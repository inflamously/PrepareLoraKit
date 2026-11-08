"""Single source of truth for filesystem locations.

Compute paths from these — never re-derive them with ``Path(__file__).parents[n]`` in
individual modules, which silently breaks when a file moves.
"""
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent   # .../prepare_lora_kit
PROJECT_ROOT = PACKAGE_ROOT.parent               # repo root (holds configs/, outputs/)
CONFIGS_DIR = PROJECT_ROOT / "configs"

# App-wide settings and the project library live outside the checkout so they
# survive a re-clone and are shared by every working copy. See
# prepare_lora_kit.settings and prepare_lora_kit.project.store.
USER_CONFIG_DIR = Path.home() / ".prepare_lora_kit"
SETTINGS_PATH = USER_CONFIG_DIR / "settings.yaml"
PROJECTS_DIR = USER_CONFIG_DIR / "projects"
