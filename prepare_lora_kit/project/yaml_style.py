"""Flow-style markers for the handful of project values that read badly as blocks.

Block style is right for a step's settings — one key per line, easy to scan and
to diff. It is wrong for short uniform records: PyYAML renders the nine
``resolution_buckets`` coordinate pairs as eighteen lines, and every substep as
two. Wrapping just those in :func:`inline` gets them onto one line each, which is
the shape the project config was split up to achieve.

Markers only affect serialization. Reading a project back yields plain dicts and
lists, so nothing downstream ever has to know these types exist.
"""
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
