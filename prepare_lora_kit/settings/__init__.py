"""App-wide settings: machine facts and defaults shared by every project.

Stored at ``~/.prepare_lora_kit/settings.yaml`` (see
:data:`prepare_lora_kit.paths.SETTINGS_PATH`). Two mechanisms, and every field
belongs to exactly one of them:

* **Seeded at project creation** — copied into a new project's YAML once, by
  :mod:`prepare_lora_kit.settings.seeding`. Existing projects are never touched,
  so a run always does exactly what its own YAML says.
* **Machine fallback behind an existing null** — for fields that already default
  to ``None`` meaning "app default", the setting replaces a hard-coded constant.
  No YAML changes meaning.

Deliberately absent: a Hugging Face token. The app reuses whatever
``hf auth login`` stored; see :mod:`prepare_lora_kit.settings.hub`.
"""
from prepare_lora_kit.settings.model import (
    AppSettings,
    HardwareSettings,
    HuggingFaceSettings,
    ProjectDefaults,
)
from prepare_lora_kit.settings.store import (
    apply_environment,
    invalidate,
    load_settings,
    save_settings,
    save_settings_dict,
    settings_path,
)

__all__ = [
    "AppSettings",
    "HardwareSettings",
    "HuggingFaceSettings",
    "ProjectDefaults",
    "apply_environment",
    "invalidate",
    "load_settings",
    "save_settings",
    "save_settings_dict",
    "settings_path",
]
