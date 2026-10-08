"""CLI fallback reviewer for upscale candidates (mirrors vae_gate/review.py).

Candidates are grouped into min-side tiers so a whole tier can be decided at
once; ``[i]ndividually`` drops back to one prompt per image.
"""
from __future__ import annotations

from pathlib import Path

DECISION_KEYS = {"u": "upscale", "c": "cleanup", "s": "skip"}


def _review_flagged_decisions(items: list[dict]) -> dict[str, str]:
    decisions: dict[str, str] = {}
    for (lo, hi), tier_items in _group_by_tier(items):
        decisions.update(_review_tier(lo, hi, tier_items))
    return decisions


def _group_by_tier(items: list[dict]) -> list[tuple[tuple, list[dict]]]:
    tiers: dict[tuple, list[dict]] = {}
    for item in items:
        if item.get("path"):
            key = (item.get("tier_lo"), item.get("tier_hi"))
            tiers.setdefault(key, []).append(item)
    return sorted(tiers.items(), key=lambda entry: (entry[0][0] is None, entry[0][0] or 0))


def _review_tier(lo, hi, items: list[dict]) -> dict[str, str]:
    label = f"{lo}-{hi}px" if lo is not None else "unknown size"
    print(f"\n== Tier {label}: {len(items)} image(s)")
    ans = input("  [u]pscale all / [k]eep size / [i]ndividually? [i] ").strip().lower()
    if ans.startswith("u"):
        return {item["path"]: _upscale_or_keep(item) for item in items}
    if ans.startswith("k"):
        return {item["path"]: _keep_size_decision(item) for item in items}
    return {item["path"]: _review_item(item) for item in items}


def _can_upscale(item: dict) -> bool:
    min_side, target = item.get("min_side"), item.get("target")
    return min_side is None or target is None or min_side < target


def _upscale_or_keep(item: dict) -> str:
    return "upscale" if _can_upscale(item) else _keep_size_decision(item)


def _keep_size_decision(item: dict) -> str:
    """Keeping the size still cleans a JPEG up to PNG; anything else is left as-is."""
    return "cleanup" if item.get("is_jpeg") else "skip"


def _allowed_decisions(item: dict) -> list[str]:
    allowed = ["upscale"] if _can_upscale(item) else []
    if item.get("is_jpeg"):
        allowed.append("cleanup")
    allowed.append("skip")
    return allowed


def _review_item(item: dict) -> str:
    path = str(item["path"])
    allowed = _allowed_decisions(item)
    initial = str(item.get("initial_decision") or "upscale")
    if initial not in allowed:
        initial = allowed[0]
    name = item.get("name") or Path(path).name
    print(f"\n  {name}  {item.get('width')}x{item.get('height')}  "
          f"(min_side={item.get('min_side')})")
    print(f"    planned action: {item.get('planned_action')}")
    labels = {"upscale": "[u]pscale", "cleanup": "[c]leanup to PNG", "skip": "[s]kip"}
    prompt = " / ".join(labels[decision] for decision in allowed)
    ans = input(f"  {prompt}? [{initial[0]}] ").strip().lower()
    decision = DECISION_KEYS.get(ans[:1], initial)
    return decision if decision in allowed else initial
