"""Assembles the per-step field lists in :mod:`.steps` into ``CONFIG_FIELD_SCHEMA``."""
from __future__ import annotations

from collections.abc import Callable

from prepare_lora_kit.project.config_schema.fields import FieldSpec
from prepare_lora_kit.project.config_schema.steps import STEP_MODULES

CONFIG_FIELD_SCHEMA: dict[str, list[FieldSpec]] = {
    module.STEP_TYPE: module.FIELDS for module in STEP_MODULES
}

OptionProvider = Callable[[], list[tuple[str, str]]]

CONFIG_FIELD_OPTIONS: dict[str, dict[str, OptionProvider]] = {
    module.STEP_TYPE: providers
    for module in STEP_MODULES
    if (providers := getattr(module, "OPTION_PROVIDERS", None))
}
