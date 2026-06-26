"""Shared CLIP loader for Step 2 curation (open_clip backend).

The occlusion filter needs a text<->image model, so it stays on CLIP. Model
selection and loading live in the shared embedding package; this re-export keeps
the historic import path stable.
"""
from __future__ import annotations

from ...embedding import catalog
from ...embedding.loaders import LoadedClip, load_clip

__all__ = ["LoadedClip", "load_clip", "catalog"]
