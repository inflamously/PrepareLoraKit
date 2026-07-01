"""CLI (terminal) fallback for the ExportStep diff pre-step.

Mirrors the terminal-prompt style of ``steps/s4_vae_gate/review.py``: print the
categorized diff, then ask the user to confirm before anything is written.
"""
from __future__ import annotations

from typing import Any


def review_export_cli(payload: dict[str, Any]) -> dict[str, Any]:
    """Print the export diff and prompt for confirmation on the terminal."""
    added = payload.get("added", []) or []
    modified = payload.get("modified", []) or []
    orphaned = payload.get("orphaned", []) or []

    print(f"\n  Export target: {payload.get('target_dir')}")
    print(f"  + added:    {len(added)}")
    for entry in added:
        print(f"      + {entry.get('rel')}")
    print(f"  ~ modified: {len(modified)}")
    for entry in modified:
        print(f"      ~ {entry.get('rel')}")
    print(f"  ! orphaned (left as-is): {len(orphaned)}")
    for rel in orphaned:
        print(f"      ! {rel}")

    if not added and not modified:
        print("  Nothing to export — no added or modified files.")
        return {"confirmed": False, "excluded": []}

    answer = input("  Proceed with export? [y/N] ").strip().lower()
    return {"confirmed": answer[:1] == "y", "excluded": []}
