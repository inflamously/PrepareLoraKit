"""CLI fallback reviewer for flagged Step 3 images (mirrors s4_vae_gate/review.py)."""
from __future__ import annotations

from pathlib import Path


def _review_flagged_decisions(items: list[dict]) -> dict[str, str]:
    decisions: dict[str, str] = {}
    for item in items:
        path = str(item.get("path") or "")
        if not path:
            continue
        initial = str(item.get("initial_decision") or "upscale")
        name = item.get("name") or Path(path).name
        print(f"\n  {name}  {item.get('width')}x{item.get('height')}  (min_side={item.get('min_side')})")
        print(f"    planned action: {item.get('planned_action')}")
        ans = input(f"  [u]pscale / [s]kip? [{initial[0]}] ").strip().lower()
        if not ans:
            decisions[path] = initial if initial in {"upscale", "skip"} else "upscale"
            continue
        decisions[path] = {"u": "upscale", "s": "skip"}.get(ans[0], "upscale")
    return decisions
