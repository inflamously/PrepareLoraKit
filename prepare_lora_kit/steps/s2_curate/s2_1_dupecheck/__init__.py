"""Duplicate detection substep."""
from __future__ import annotations

from ..dedupe import _compute_hashes, _find_duplicates, _resolve_duplicates

__all__ = ["_compute_hashes", "_find_duplicates", "_resolve_duplicates"]
