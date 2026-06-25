"""Field spec model and builder helpers for config schemas.

:class:`FieldSpec` is the UI metadata for one editable config field; the
``_select``/``_number``/``_check``/``_text`` helpers are thin constructors used
by :mod:`.schema` to declare fields concisely.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldSpec:
    """UI metadata for a single editable config field."""

    name: str
    label: str
    control: str  # "select" | "number" | "text" | "checkbox"
    value_type: str = "str"  # "str" | "int" | "float" | "bool"
    options: list[dict[str, str]] = field(default_factory=list)  # [{value,label}]
    allow_custom: bool = False  # select may accept a free-text value not in options
    nullable: bool = False  # empty input coerces to None instead of being skipped
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    placeholder: str = ""
    help: str = ""


def _select(name, label, choices, **kw) -> FieldSpec:
    options = [
        {"value": value, "label": text}
        for value, text in choices
    ]
    return FieldSpec(name=name, label=label, control="select", options=options, **kw)


def _number(name, label, value_type="float", **kw) -> FieldSpec:
    return FieldSpec(name=name, label=label, control="number", value_type=value_type, **kw)


def _check(name, label, **kw) -> FieldSpec:
    return FieldSpec(name=name, label=label, control="checkbox", value_type="bool", **kw)


def _text(name, label, **kw) -> FieldSpec:
    return FieldSpec(name=name, label=label, control="text", value_type="str", **kw)
