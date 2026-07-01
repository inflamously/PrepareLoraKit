"""Per-step config field definitions.

Each submodule exposes a ``STEP_TYPE`` string and a ``FIELDS`` list of
:class:`~..fields.FieldSpec`. ``STEP_MODULES`` lists them in pipeline order; the
parent :mod:`..schema` assembles them into ``CONFIG_FIELD_SCHEMA``.
"""
from __future__ import annotations

from . import (
    audit,
    bucket_dry_run,
    caption,
    config_gen,
    curate,
    export,
    import_step,
    quality_gate,
    upscale,
    vae_gate,
)

# Order here defines the order of CONFIG_FIELD_SCHEMA (pipeline order).
STEP_MODULES = [
    import_step,
    quality_gate,
    curate,
    upscale,
    vae_gate,
    caption,
    audit,
    config_gen,
    bucket_dry_run,
    export,
]
