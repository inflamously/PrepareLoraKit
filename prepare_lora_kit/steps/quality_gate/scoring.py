from __future__ import annotations
from pathlib import Path


from prepare_lora_kit.utils import image as img_utils

# ── thresholds (all configurable) ─────────────────────────────────────────────

DEFAULTS = {
    "min_side": 1024,
    "blur_threshold": 100.0,        # Laplacian variance — below = reject
    "noise_threshold": 25.0,        # HF residual std — above = reject
    "jpeg_threshold": 0.08,         # 1-SSIM — above = reject
    "watermark_threshold": 0.80,    # CLIP score — above = reject
    "borderline_blur": 150.0,       # below this → show in manual review even if pass
}


# ── scorer functions ──────────────────────────────────────────────────────────
# Maps a scorer's `name` to the function that computes its raw value. This is the
# single place a new algorithm is wired in; the gate's op/threshold/borderline are
# data carried on each scorer entry (see ScorerEntry / project YAML).

SCORER_FNS = {
    "min_side":  img_utils.min_side,
    "blur":      img_utils.blur_score,
    "noise":     img_utils.noise_score,
    "jpeg":      img_utils.jpeg_artifact_score,
    "watermark": img_utils.watermark_score,
}


# ── scorer registry ───────────────────────────────────────────────────────────
# Default scorers used when a caller passes no `scorers`. Each entry mirrors the
# configurable ScorerEntry schema: name, op ("lt"|"gt"), threshold (inline),
# optional borderline (triggers manual review). Pipeline runs override this with
# the project's configured scorers.

SCORER_REGISTRY: list[dict] = [
    {"name": "min_side",  "op": "lt", "threshold": 1024.0},
    {"name": "blur",      "op": "lt", "threshold": 100.0, "borderline": 150.0},
    {"name": "noise",     "op": "gt", "threshold": 25.0},
    {"name": "jpeg",      "op": "gt", "threshold": 0.08},
    {"name": "watermark", "op": "gt", "threshold": 0.80},
]


def _resolve_fn(s: dict):
    """Function that computes the scorer's raw value, from inline `fn` or `name`."""
    fn = s.get("fn")
    if fn is not None:
        return fn
    name = s["name"]
    try:
        return SCORER_FNS[name]
    except KeyError:
        raise KeyError(f"no scorer function registered for '{name}'") from None


def _resolve_threshold(s: dict, thresholds: dict) -> float:
    """Gate threshold: inline `threshold` wins, else legacy `threshold_key` lookup."""
    if s.get("threshold") is not None:
        return s["threshold"]
    key = s.get("threshold_key")
    if key is not None and key in thresholds:
        return thresholds[key]
    raise KeyError(f"scorer '{s['name']}' has no threshold (inline or via threshold_key)")


def _resolve_borderline(s: dict, thresholds: dict):
    """Borderline threshold: inline `borderline`, else legacy `borderline_key` lookup."""
    if s.get("borderline") is not None:
        return s["borderline"]
    key = s.get("borderline_key")
    if key is not None:
        return thresholds.get(key)
    return None


def _active_scorers(scorers: list[dict]) -> list[dict]:
    """Drop scorers explicitly disabled via `enabled: false`."""
    return [s for s in scorers if s.get("enabled", True)]


def _quality_score(scores: dict, thresholds: dict, scorers: list[dict]) -> float:
    """
    Overall quality in [0, 100] derived from the quality gates.

    Each gate maps its raw value to [0, 1] with the threshold pinned to 0.5:
      - "lt" gate (higher value = better): q = value / (2 * threshold)
      - "gt" gate (lower value = better):  q = 1 - value / (2 * threshold)
    Final score = mean of available gates × 100.
    """
    parts: list[float] = []
    for s in _active_scorers(scorers):
        v = scores.get(s["name"])
        if v is None:
            continue
        try:
            thr = _resolve_threshold(s, thresholds)
        except KeyError:
            continue
        if not thr or thr <= 0:
            continue
        if s["op"] == "lt":
            q = v / (2 * thr)
        else:
            q = 1.0 - v / (2 * thr)
        parts.append(max(0.0, min(1.0, q)))
    return round(100 * sum(parts) / len(parts), 1) if parts else 0.0


def _score_image(src, thresholds: dict, scorers: list[dict]) -> dict:
    """Score one image. ``src`` is a Path or a decoded ``ImageData`` (shared across
    scorers so the image is decoded once)."""
    scores: dict = {}
    reasons: list[str] = []
    borderline_flags: list[bool] = []

    for scorer in _active_scorers(scorers):
        name = scorer["name"]
        threshold = _resolve_threshold(scorer, thresholds)
        fn = _resolve_fn(scorer)

        optional = scorer.get("optional", False)
        try:
            value = fn(src)
        except Exception:
            if optional:
                scores[name] = None
                borderline_flags.append(False)
                continue
            raise

        scores[name] = round(value, 3) if isinstance(value, float) else value

        op = scorer["op"]
        if (op == "lt" and value < threshold) or (op == "gt" and value > threshold):
            reasons.append(f"{name} {value} {'<' if op == 'lt' else '>'} {threshold}")

        bthresh = _resolve_borderline(scorer, thresholds)
        if bthresh is not None and op == "lt":
            borderline_flags.append(value < bthresh)
        else:
            borderline_flags.append(False)

    auto_reject = bool(reasons)
    return {
        "scores": scores,
        "quality": _quality_score(scores, thresholds, scorers),
        "auto_reject": auto_reject,
        "borderline": (not auto_reject) and any(borderline_flags),
        "auto_reasons": reasons,
    }
