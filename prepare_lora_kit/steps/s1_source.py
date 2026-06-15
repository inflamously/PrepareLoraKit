"""
Step 1 — Source Image Quality Gates + Manual Review

Phase A: automated scoring via pluggable scorer registry.
Phase B: easygui one-by-one manual review for passed/borderline images.
"""
from __future__ import annotations
from pathlib import Path

from ..utils import image as img_utils
from ..utils import report as rpt


# ── thresholds (all configurable) ─────────────────────────────────────────────

DEFAULTS = {
    "min_side": 1024,
    "blur_threshold": 100.0,        # Laplacian variance — below = reject
    "noise_threshold": 25.0,        # HF residual std — above = reject
    "jpeg_threshold": 0.08,         # 1-SSIM — above = reject
    "watermark_threshold": 0.65,    # CLIP score — above = reject
    "borderline_blur": 150.0,       # below this → show in manual review even if pass
}


# ── scorer registry ───────────────────────────────────────────────────────────
# Each entry: name, fn(Path)->float|int, threshold_key, op ("lt"|"gt"),
#             optional (skip silently on error), borderline_key (triggers manual review).
# Add new algorithms here without touching _score_image.

SCORER_REGISTRY: list[dict] = [
    {
        "name": "min_side",
        "fn": img_utils.min_side,
        "threshold_key": "min_side",
        "op": "lt",
    },
    {
        "name": "blur",
        "fn": img_utils.blur_score,
        "threshold_key": "blur_threshold",
        "op": "lt",
        "borderline_key": "borderline_blur",
    },
    {
        "name": "noise",
        "fn": img_utils.noise_score,
        "threshold_key": "noise_threshold",
        "op": "gt",
    },
    {
        "name": "jpeg",
        "fn": img_utils.jpeg_artifact_score,
        "threshold_key": "jpeg_threshold",
        "op": "gt",
    },
    {
        "name": "watermark",
        "fn": img_utils.watermark_score,
        "threshold_key": "watermark_threshold",
        "op": "gt",
        "optional": True,
    },
]


def _score_image(path: Path, thresholds: dict, scorers: list[dict]) -> dict:
    scores: dict = {}
    reasons: list[str] = []
    borderline_flags: list[bool] = []

    for s in scorers:
        name = s["name"]
        threshold = thresholds[s["threshold_key"]]
        optional = s.get("optional", False)

        try:
            value = s["fn"](path)
        except Exception:
            if optional:
                scores[name] = None
                borderline_flags.append(False)
                continue
            raise

        scores[name] = round(value, 3) if isinstance(value, float) else value
        op = s["op"]

        if (op == "lt" and value < threshold) or (op == "gt" and value > threshold):
            reasons.append(f"{name} {value} {'<' if op == 'lt' else '>'} {threshold}")

        bkey = s.get("borderline_key")
        if bkey and op == "lt":
            bthresh = thresholds.get(bkey)
            borderline_flags.append(bthresh is not None and value < bthresh)
        else:
            borderline_flags.append(False)

    auto_reject = bool(reasons)
    return {
        "scores": scores,
        "auto_reject": auto_reject,
        "borderline": (not auto_reject) and any(borderline_flags),
        "auto_reasons": reasons,
    }


def _manual_review(path: Path, score_info: dict) -> str:
    """Show image + scores; return 'keep', 'reject', or 'flag'."""
    try:
        import easygui
        from PIL import Image as PILImage

        PILImage.open(path).show()

        lines = [f"File: {path.name}\n"]
        for k, v in score_info["scores"].items():
            val_str = f"{v}" if v is not None else "n/a"
            lines.append(f"  {k:<14}: {val_str}")

        msg = "\n".join(lines)
        if score_info["auto_reasons"]:
            msg += f"\n\nAuto-flags: {', '.join(score_info['auto_reasons'])}"

        choice = easygui.buttonbox(msg, title="Step 1 — Review Image",
                                   choices=["Keep", "Reject", "Flag for later"])
        if choice == "Keep":
            return "keep"
        if choice == "Reject":
            return "reject"
        return "flag"

    except ImportError:
        rpt.warn(f"easygui not available. Terminal fallback: {path.name}")
        print(f"\n  {path}")
        _show_scores_terminal(score_info)
        ans = input("  [k]eep / [r]eject / [f]lag? ").strip().lower()
        return {"k": "keep", "r": "reject", "f": "flag"}.get(ans[0] if ans else "k", "keep")


def _show_scores_terminal(score_info: dict) -> None:
    parts = [f"{k}={v}" for k, v in score_info["scores"].items() if v is not None]
    print(f"    {' '.join(parts)}")


def run(
    input_dir: Path,
    output_dir: Path,
    thresholds: dict | None = None,
    auto_only: bool = False,
    manual_all: bool = False,
    scorers: list[dict] | None = None,
) -> dict:
    """
    Run Step 1.

    Returns report dict: {path_str: {kept, decision, scores, reasons}}.
    Writes report to output_dir/step1_report.json.

    Pass `scorers` to override SCORER_REGISTRY with custom quality checks.
    Each scorer: {"name", "fn", "threshold_key", "op", "optional", "borderline_key"}.
    """
    rpt.step_header(1, "Source Image Quality Gates")

    thresholds = {**DEFAULTS, **(thresholds or {})}
    scorers = scorers if scorers is not None else SCORER_REGISTRY
    images = img_utils.iter_images(input_dir)
    if not images:
        rpt.warn(f"No images found in {input_dir}")
        return {}

    rpt.info(f"Scoring {len(images)} images …")

    report: dict = {}
    kept = rejected = flagged = 0

    for path in images:
        key = str(path)
        try:
            info = _score_image(path, thresholds, scorers)
        except Exception as exc:
            rpt.error(f"{path.name}: scoring failed — {exc}")
            report[key] = {"kept": False, "decision": "reject", "reason": str(exc), "scores": {}}
            rejected += 1
            continue

        if info["auto_reject"] and not manual_all:
            decision = "reject"
            reason = "; ".join(info["auto_reasons"])
            report[key] = {"kept": False, "decision": decision, "reason": reason, "scores": info["scores"]}
            rejected += 1
            rpt.warn(f"AUTO-REJECT {path.name}: {reason}")
            continue

        if not auto_only and (manual_all or info["borderline"] or info["auto_reject"]):
            decision = _manual_review(path, info)
        else:
            decision = "keep"

        kept_bool = decision == "keep"
        flag_bool = decision == "flag"
        report[key] = {
            "kept": kept_bool or flag_bool,
            "decision": decision,
            "reason": "; ".join(info["auto_reasons"]) if info["auto_reasons"] else None,
            "scores": info["scores"],
        }
        if kept_bool:
            kept += 1
        elif flag_bool:
            flagged += 1
        else:
            rejected += 1

    rpt.summary_counts(kept, rejected, flagged)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "step1_report.json"
    rpt.save_report(report, report_path)
    return report
