"""Single source of truth for filesystem locations.

Anchored to this module's own location in the package root, so the constants
stay correct no matter how deeply nested the modules that import them are.
Compute paths from these — never re-derive them with ``Path(__file__).parents[n]``
in individual modules, which silently breaks when a file moves.
"""
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent   # .../prepare_lora_kit
PROJECT_ROOT = PACKAGE_ROOT.parent               # repo root (holds configs/, outputs/)
CONFIGS_DIR = PROJECT_ROOT / "configs"

# App-wide settings live outside the checkout so they survive a re-clone and are
# shared by every working copy. See prepare_lora_kit.settings.
USER_CONFIG_DIR = Path.home() / ".prepare_lora_kit"
SETTINGS_PATH = USER_CONFIG_DIR / "settings.yaml"
