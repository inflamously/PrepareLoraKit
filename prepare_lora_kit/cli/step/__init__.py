"""`step` command package — run a single pipeline step manually.

Importing this package registers the ``step`` command on the shared ``cli``
group (via :mod:`.command`). Helper functions are re-exported here so callers
and tests can keep importing them from ``prepare_lora_kit.cli.step``.
"""
from __future__ import annotations

from .bbox import _parse_bbox, _resolve_bbox_target, build_bbox_interaction
from .command import step
from .resolve import _load_project, _resolve_step_type

__all__ = [
    "step",
    "_resolve_step_type",
    "_load_project",
    "_parse_bbox",
    "_resolve_bbox_target",
    "build_bbox_interaction",
]
