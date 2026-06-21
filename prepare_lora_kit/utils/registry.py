"""Generic name → config registry shared by the project and network registries.

A registry resolves a *name* to a config object, looking first at Python-defined
built-ins (each a module exposing a ``load()`` callable) and then at a YAML file
under ``configs/<subdir>/``. Names are hyphenated; the matching YAML file uses
underscores (``flux-klein-9b`` → ``flux_klein_9b.yaml``).
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable, Generic, TypeVar

from ..paths import CONFIGS_DIR

T = TypeVar("T")


class ConfigRegistry(Generic[T]):
    """Loads named configs of type ``T`` from built-ins or ``configs/<subdir>/``."""

    def __init__(
        self,
        *,
        kind: str,
        subdir: str,
        loader: Callable[[Path], T],
        builtin_package: str,
        builtins: dict[str, str] | None = None,
        skip_example: bool = False,
    ) -> None:
        self.kind = kind                        # noun used in error messages
        self.loader = loader                    # e.g. NetworkProfile.from_yaml
        self.builtin_package = builtin_package   # dotted package of built-in modules
        self.builtins = builtins or {}           # name → module name within package
        self.skip_example = skip_example
        self.configs_dir = CONFIGS_DIR / subdir

    def load(self, name: str) -> T:
        """Load a config by name. Checks built-ins then ``configs/<subdir>/``."""
        if name in self.builtins:
            mod = importlib.import_module(
                f"{self.builtin_package}.{self.builtins[name]}"
            )
            return mod.load()

        # Fall back to YAML in configs/<subdir>/<name>.yaml (hyphens → underscores)
        yaml_path = self.configs_dir / (name.replace("-", "_") + ".yaml")
        if yaml_path.exists():
            return self.loader(yaml_path)

        available = ", ".join(self.list()) or "(none)"
        raise ValueError(f"Unknown {self.kind} '{name}'. Available: {available}")

    def list(self) -> list[str]:
        """Return all known names (built-ins + YAML configs), sorted."""
        names = set(self.builtins)
        if self.configs_dir.exists():
            for p in self.configs_dir.glob("*.yaml"):
                if self.skip_example and "example" in p.name:
                    continue
                names.add(p.stem.replace("_", "-"))
        return sorted(names)
