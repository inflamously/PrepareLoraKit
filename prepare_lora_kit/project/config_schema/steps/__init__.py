"""Per-step config field definitions; each submodule exposes ``STEP_TYPE`` and ``FIELDS``."""
from __future__ import annotations

from . import (
    audit,
    bucket_pools_check,
    caption_bbox,
    caption_verifier,
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
    upscale,
    quality_gate,
    curate,
    caption_bbox,
    caption_verifier,
    vae_gate,
    audit,
    bucket_pools_check,
    export,
]
