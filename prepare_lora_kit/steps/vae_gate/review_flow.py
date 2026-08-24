"""Thresholding and keep/drop review flow for reconstructed images."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.providers.interaction import InteractionProvider
from prepare_lora_kit.report import reporter
from prepare_lora_kit.steps.vae_gate.reconstruction import _ReconstructionPass
from prepare_lora_kit.steps.vae_gate.review import _manual_flag_decision


@dataclass(frozen=True)
class _ReviewResult:
    mean: float | None
    std: float | None
    threshold: float | None
    flagged: list[str]
    items: list[dict]
    decisions: dict[str, str]


def _review_reconstructions(
    images: list[Path],
    recon: _ReconstructionPass,
    outlier_sigma: float,
    enabled: set[str],
    interaction: InteractionProvider | None,
    cancel_check: CancelCheck | None,
) -> _ReviewResult:
    """Calculate outliers and collect keep/drop decisions through UI or CLI."""
    mean, std, threshold = _threshold_stats(recon.hf_scores, outlier_sigma)
    flagged = [
        path for path, score in recon.hf_scores.items()
        if threshold is not None and score > threshold
    ]
    reporter.warn(f"{len(flagged)} images flagged as high-frequency-loss outliers")
    items = _build_review_items(images, recon, threshold, set(flagged), cancel_check)
    decisions = _collect_decisions(
        enabled, interaction, items, flagged, recon, cancel_check)
    return _ReviewResult(mean, std, threshold, flagged, items, decisions)


def _threshold_stats(
    hf_scores: dict[str, float],
    outlier_sigma: float,
) -> tuple[float | None, float | None, float | None]:
    """Mean/std/outlier threshold over the scored images, or ``None`` if empty."""
    values = np.array(list(hf_scores.values()), dtype=np.float64)
    if not values.size:
        reporter.warn("No images were reconstructed successfully; no outliers were calculated.")
        return None, None, None

    mean = float(values.mean())
    std = float(values.std())
    threshold = mean + outlier_sigma * std
    reporter.info(f"HF-loss  mean={mean:.4f}  std={std:.4f}  threshold={threshold:.4f}")
    return mean, std, threshold


def _build_review_items(
    images: list[Path],
    recon: _ReconstructionPass,
    threshold: float | None,
    flagged_set: set[str],
    cancel_check: CancelCheck | None,
) -> list[dict]:
    """Build one review row per image that produced review artifacts."""
    review_items: list[dict] = []
    for path in images:
        check_cancel(cancel_check)
        path_str = str(path)
        artifact = recon.review_artifacts.get(path_str)
        if artifact is None:
            continue
        review_items.append({
            "path": path_str,
            "name": path.name,
            "width": artifact.get("width"),
            "height": artifact.get("height"),
            "hf_loss": round(recon.hf_scores.get(path_str, 0.0), 5),
            "threshold": _rounded(threshold),
            "diff_threshold": artifact.get("diff_threshold"),
            "flagged": path_str in flagged_set,
            "initial_decision": "keep",
            "views": artifact.get("views", {}),
        })
    return review_items


def _collect_decisions(
    enabled: set[str],
    interaction: InteractionProvider | None,
    review_items: list[dict],
    flagged: list[str],
    recon: _ReconstructionPass,
    cancel_check: CancelCheck | None,
) -> dict[str, str]:
    """Collect keep/drop verdicts through the UI gallery or CLI fallback."""
    decisions: dict[str, str] = {}
    if "review_vae_artifacts" not in enabled:
        return decisions

    if interaction is not None and review_items:
        check_cancel(cancel_check)
        decisions.update(interaction.vae_review(review_items))
        check_cancel(cancel_check)
        return decisions

    for path_str in flagged:
        check_cancel(cancel_check)
        path = Path(path_str)
        reconstruction = recon.reconstructions.get(path_str)
        if reconstruction is not None:
            decision = _manual_flag_decision(path, reconstruction, recon.hf_scores[path_str])
        else:
            decision = "drop"
        decisions[path_str] = decision
        reporter.info(f"  {path.name} → {decision}")
    return decisions


def _select_survivors(
    images: list[Path],
    decisions: dict[str, str],
    *,
    apply_decisions: bool,
) -> list[Path]:
    if not apply_decisions:
        return list(images)
    return [path for path in images if _decision_for(decisions, path) != "drop"]


def _reviewed_items(
    items: list[dict],
    decisions: dict[str, str],
    cancel_check: CancelCheck | None,
) -> list[dict]:
    reviewed = []
    for item in items:
        check_cancel(cancel_check)
        path = Path(str(item["path"]))
        decision = _decision_for(decisions, path)
        reviewed.append({**item, "decision": decision})
        if decision != "keep":
            reporter.info(f"  {path.name} → {decision}")
    return reviewed


def _decision_for(decisions: dict[str, str], path: Path) -> str:
    """Return a normalized verdict for ``path``, defaulting to keep."""
    decision = decisions.get(str(path), decisions.get(str(path.resolve()), "keep"))
    return decision if decision in {"keep", "drop"} else "keep"


def _rounded(value: float | None) -> float | None:
    return round(float(value), 5) if value is not None else None
