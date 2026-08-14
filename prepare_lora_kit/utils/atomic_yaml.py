"""Durable YAML writes under ``~/.prepare_lora_kit``: temp file beside the target,
swapped in with ``os.replace``.
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

import yaml


def write_yaml_atomic(
    path: Path,
    data: Any,
    *,
    secure_parent: bool = False,
    header: str = "",
    dumper: type[yaml.Dumper] | None = None,
) -> Path:
    """Serialize ``data`` to ``path`` atomically, optionally behind a comment banner.

    ``header`` is prepended verbatim because PyYAML cannot emit comments; a
    regenerated banner is the only durable comment a written file can carry.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if secure_parent and os.name == "posix":
        # User config, not a secret (no token is ever stored here) — but there is
        # no reason for it to be world-readable either.
        with contextlib.suppress(OSError):
            path.parent.chmod(0o700)

    body = yaml.dump(
        data,
        Dumper=dumper or yaml.SafeDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    tmp = path.with_name(f".{path.name}.plk_tmp")
    tmp.write_text(f"{header}{body}", encoding="utf-8")
    tmp.replace(path)
    return path


__all__ = ["write_yaml_atomic"]
