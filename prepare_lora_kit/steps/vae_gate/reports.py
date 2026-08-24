"""Stable report shapes for VaeGateStep."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.report import reporter
from prepare_lora_kit.steps.vae_gate.reconstruction import _ReconstructionPass
from prepare_lora_kit.steps.vae_gate.review_flow import _decision_for, _ReviewResult, _rounded


def _save_skipped_report(
    reason: str,
    enabled: set[str],
    outlier_sigma: float,
    target_report: Path,
    *,
    failed: int = 0,
    failures: list[dict] | None = None,
) -> dict:
    """Write and return the report shape used when nothing was assessed."""
    report_data = {
        "skipped": True,
        "reason": reason,
        "hf_scores": {},
        "threshold": None,
        "statistics": _statistics(0, failed, None, None, None, outlier_sigma),
        "flagged": [],
        "failures": failures or [],
        "review_items": [],
        "substeps": _substep_report(enabled),
    }
    reporter.save_report(report_data, target_report)
    return report_data


def _build_success_report(
    recon: _ReconstructionPass,
    review: _ReviewResult,
    reviewed_items: list[dict],
    outlier_sigma: float,
    enabled: set[str],
) -> dict:
    return {
        "hf_scores": {key: round(value, 5) for key, value in recon.hf_scores.items()},
        "threshold": _rounded(review.threshold),
        "statistics": _statistics(
            len(recon.hf_scores),
            len(recon.failures),
            review.mean,
            review.std,
            review.threshold,
            outlier_sigma,
        ),
        "flagged": [
            {
                "path": path,
                "hf_loss": round(recon.hf_scores[path], 5),
                "decision": _decision_for(review.decisions, Path(path)),
            }
            for path in review.flagged
        ],
        "failures": recon.failures,
        "review_items": reviewed_items,
        "substeps": _substep_report(enabled),
    }


def _statistics(
    successful: int,
    failed: int,
    mean: float | None,
    std: float | None,
    threshold: float | None,
    outlier_sigma: float,
) -> dict:
    return {
        "successful": successful,
        "failed": failed,
        "mean": _rounded(mean),
        "std": _rounded(std),
        "threshold": _rounded(threshold),
        "outlier_sigma": outlier_sigma,
        "comparison": ">",
    }


def _substep_report(enabled: set[str]) -> dict:
    return {
        "reconstruct_images": {"enabled": "reconstruct_images" in enabled},
        "review_vae_artifacts": {"enabled": "review_vae_artifacts" in enabled},
        "apply_vae_decisions": {"enabled": "apply_vae_decisions" in enabled},
    }
