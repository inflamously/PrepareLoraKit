"""
Step 3 — Upscale (optional)

Selectively upscales images below the target min-side.
The project config selects the upscaler. Missing configured upscalers skip with
a warning instead of silently falling back to another algorithm.
Re-runs Step 1 quality checks post-upscale to reject hallucinated-texture outputs.
"""
from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Callable

from ...utils import image as img_utils
from ...utils import report as rpt
from .upscalers import UPSCALE_TARGET, _seedvr_upscale, _lanczos_upscale
from .hallucination import HALLUCINATION_SSIM_THRESHOLD, _hallucination_check


def run(
    dataset_dir: Path,
    output_dir: Path | None = None,
    upscale_target: int = UPSCALE_TARGET,
    upscaler: Callable[[Path, Path], Path] | None = None,
    upscale_model: str = "seedvr",
    hallucination_ssim_threshold: float = HALLUCINATION_SSIM_THRESHOLD,
    use_seedvr: bool | None = None,
    report_path: Path | None = None,
) -> dict:
    rpt.step_header(3, "Upscale (optional)")
    if use_seedvr is not None:
        upscale_model = "seedvr" if use_seedvr else "lanczos"
        rpt.warn("UpscaleStep.run(use_seedvr=...) is deprecated; use upscale_model instead.")

    output_dir = output_dir or (dataset_dir / "_upscaled")
    output_dir.mkdir(parents=True, exist_ok=True)
    # In-place mode = the pipeline's single working dir: upscaled images
    # overwrite the originals, no second copy kept. Standalone (-i/-o differ)
    # still emits a fresh upscaled folder.
    in_place = output_dir.resolve() == dataset_dir.resolve()

    def _pass_through(path: Path) -> None:
        """Ensure the original sits at its output slot unchanged."""
        if in_place:
            return  # original already lives in the working dir
        dst = output_dir / path.name
        if not dst.exists():
            shutil.copy2(path, dst)

    images = img_utils.iter_images(dataset_dir)
    candidates = [p for p in images if img_utils.min_side(p) < upscale_target]
    already_large = [p for p in images if img_utils.min_side(p) >= upscale_target]

    # Images already at target resolution pass through unchanged.
    for p in already_large:
        _pass_through(p)

    if not candidates:
        rpt.ok(f"All images already ≥ {upscale_target}px — skipping upscale.")
        return {"upscaled": [], "rejected_post": [], "skipped": [str(p) for p in images]}

    rpt.info(f"{len(candidates)} images below {upscale_target}px min-side will be upscaled.")

    results: dict = {"upscaled": [], "rejected_post": [], "skipped": []}

    if upscaler is None:
        if upscale_model == "seedvr":
            seedvr_available = bool(os.environ.get("SEEDVR_PATH", ""))
            if seedvr_available:
                rpt.info("Using SeedVR upscaler (SEEDVR_PATH set).")
                upscaler = _seedvr_upscale
            else:
                reason = "SEEDVR_PATH not set; configured upscale_model=seedvr"
                rpt.warn(f"{reason} — skipping upscale candidates.")
                for p in candidates:
                    _pass_through(p)
                    results["skipped"].append({"path": str(p), "reason": reason})
                rpt.save_report(results, report_path or (output_dir / "step3_report.json"))
                return results
        elif upscale_model == "lanczos":
            rpt.info("Using Lanczos upscaler.")
            upscaler = lambda p, o: _lanczos_upscale(p, o, upscale_target)
        elif upscale_model == "custom":
            reason = "configured upscale_model=custom but no custom upscaler was provided"
            rpt.warn(f"{reason} — skipping upscale candidates.")
            for p in candidates:
                _pass_through(p)
                results["skipped"].append({"path": str(p), "reason": reason})
            rpt.save_report(results, report_path or (output_dir / "step3_report.json"))
            return results
        else:
            raise ValueError(f"Unknown upscale_model: {upscale_model}")

    for path in candidates:
        out_path = output_dir / path.name
        # Upscale into a temp file first so the original survives intact until the
        # hallucination check passes — required for in-place overwrite safety.
        tmp_path = output_dir / (path.stem + ".upscaling.tmp" + path.suffix)
        try:
            upscaler(path, tmp_path)
        except Exception as exc:
            rpt.error(f"Upscale failed for {path.name}: {exc} — keeping original.")
            results["skipped"].append({"path": str(path), "reason": str(exc)})
            tmp_path.unlink(missing_ok=True)
            _pass_through(path)
            continue

        # Post-upscale hallucination check
        hall_ssim = _hallucination_check(path, tmp_path)
        if hall_ssim < hallucination_ssim_threshold:
            rpt.warn(f"REJECT upscale {path.name} (SSIM={hall_ssim:.3f}) — keeping original size.")
            results["rejected_post"].append({"path": str(path), "hall_ssim": hall_ssim})
            tmp_path.unlink(missing_ok=True)
            _pass_through(path)  # pass original through unchanged
        else:
            rpt.ok(f"Upscaled {path.name} → {out_path.name} (hall_ssim={hall_ssim:.3f})")
            os.replace(tmp_path, out_path)
            results["upscaled"].append({"original": str(path), "upscaled": str(out_path)})

    rpt.save_report(results, report_path or (output_dir / "step3_report.json"))
    return results
