"""Config schema for ConfigGenStep."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from prepare_lora_kit.paths import PROJECT_ROOT


@dataclass
class ConfigGenConfig:
    """Config for ConfigGenStep."""
    base_template_path: Optional[str] = None

    def __post_init__(self) -> None:
        if self.base_template_path is not None:
            p = Path(self.base_template_path).expanduser()
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            if not p.exists():
                raise ValueError(
                    f"ConfigGenStep: base_template_path does not exist: {self.base_template_path}"
                )
