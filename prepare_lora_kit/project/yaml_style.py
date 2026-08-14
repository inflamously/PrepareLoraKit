"""Flow-style markers for the handful of project values that read badly as blocks."""
from __future__ import annotations

from typing import Any

import yaml


class InlineDict(dict):
    """A mapping to emit as ``{a: 1, b: 2}``."""


class InlineList(list):
    """A sequence to emit as ``[1, 2]``."""


class ProjectDumper(yaml.SafeDumper):
    """SafeDumper that honors the inline markers above."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        # Indent block sequences under their key. PyYAML's default leaves them
        # flush with the key, which reads as if the list were a sibling.
        return super().increase_indent(flow, False)


def _represent_inline_dict(dumper: yaml.Dumper, data: dict) -> Any:
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True)


def _represent_inline_list(dumper: yaml.Dumper, data: list) -> Any:
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


ProjectDumper.add_representer(InlineDict, _represent_inline_dict)
ProjectDumper.add_representer(InlineList, _represent_inline_list)


def inline(value: Any) -> Any:
    """Mark ``value`` for flow style, leaving anything else untouched."""

    if isinstance(value, dict):
        return InlineDict(value)
    if isinstance(value, (list, tuple)):
        return InlineList(value)
    return value


__all__ = ["InlineDict", "InlineList", "ProjectDumper", "inline"]
