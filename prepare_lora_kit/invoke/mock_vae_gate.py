"""Deterministic mock runtime for VaeGateStep (--mock)."""
from __future__ import annotations
from pathlib import Path

from prepare_lora_kit.cancellation import check_cancel


def _mock_vae_gate(
        working_dir: Path,
        output_dir: Path,
        *,
        interaction=None,
        enabled_substeps: list[str] | None = None,
        cancel_check=None,
) -> dict:
    from ..utils import image as img_utils
    from ..utils import report as rpt
    from ..steps.vae_gate.review import _save_review_artifacts
    import numpy as np
    from PIL import Image, ImageFilter

    rpt.step_header(4, "VAE Reconstruction Gate")
    enabled = set(enabled_substeps or ["reconstruct_images", "review_vae_artifacts", "apply_vae_decisions"])
    images = img_utils.iter_images(working_dir)
    scores = {str(path): 0.0 for path in images}
    preview_root = output_dir / "reports" / "VaeGateStep_previews"
    review_items = []
    for index, path in enumerate(images):
        check_cancel(cancel_check)
        with Image.open(path).convert("RGB") as img:
            recon = img.filter(ImageFilter.GaussianBlur(radius=1.6 if index == 0 else 0.6))
            recon_arr = np.array(recon)
        artifact = _save_review_artifacts(path, recon_arr, preview_root)
        review_items.append({
            "path": str(path),
            "name": path.name,
            "width": artifact["width"],
            "height": artifact["height"],
            "hf_loss": 0.0,
            "threshold": 0.0,
            "diff_threshold": artifact["diff_threshold"],
            "flagged": False,
            "initial_decision": "keep",
            "views": artifact["views"],
        })

    check_cancel(cancel_check)
    decisions = (
        interaction.vae_review(review_items)
        if "review_vae_artifacts" in enabled and interaction and review_items
        else {}
    )
    check_cancel(cancel_check)
    survivors = [
        path for path in images
        if "apply_vae_decisions" not in enabled
           or decisions.get(str(path), decisions.get(str(path.resolve()), "keep")) != "drop"
    ]
    img_utils.materialize(survivors, working_dir, working_dir)
    report = {
        "mock_runtime": True,
        "hf_scores": scores,
        "threshold": 0.0,
        "flagged": [],
        "review_items": [
            {
                **item,
                "decision": decisions.get(
                    item["path"],
                    decisions.get(str(Path(item["path"]).resolve()), "keep"),
                ),
            }
            for item in review_items
        ],
        "needs_replacement": [
            str(path)
            for path in images
            if decisions.get(str(path), decisions.get(str(path.resolve()), "keep")) == "replace"
        ],
        "substeps": {
            "reconstruct_images": {"enabled": "reconstruct_images" in enabled},
            "review_vae_artifacts": {"enabled": "review_vae_artifacts" in enabled},
            "apply_vae_decisions": {"enabled": "apply_vae_decisions" in enabled},
        },
    }
    rpt.info(f"Mock runtime: recorded deterministic VAE pass for {len(images)} image(s).")
    check_cancel(cancel_check)
    rpt.save_report(report, output_dir / "reports" / "VaeGateStep_report.json")
    return report
