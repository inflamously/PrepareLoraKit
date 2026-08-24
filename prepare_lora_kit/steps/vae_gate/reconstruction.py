"""VAE reconstruction pass and its in-memory results."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from prepare_lora_kit.cancellation import CancelCheck, CancelledRun, check_cancel
from prepare_lora_kit.report import reporter
from prepare_lora_kit.steps.vae_gate.hf_loss import _hf_loss
from prepare_lora_kit.steps.vae_gate.review import _save_review_artifacts
from prepare_lora_kit.steps.vae_gate.vae import _encode_decode, _to_lab_l


@dataclass(frozen=True)
class _PreviewOptions:
    """Which review artifacts to render, and how."""

    diff_amplification: float
    gaussian_blur_sigma: float
    gaussian_blur_kernel: int
    otsu_enabled: bool
    write_vae: bool
    write_diff: bool
    write_hard: bool

    @property
    def writes_anything(self) -> bool:
        return self.write_vae or self.write_diff or self.write_hard


@dataclass
class _ReconstructionPass:
    """What one encode/decode sweep over the dataset produced."""

    hf_scores: dict[str, float] = field(default_factory=dict)
    reconstructions: dict[str, np.ndarray] = field(default_factory=dict)
    review_artifacts: dict[str, dict] = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)


def _reconstruct_all(
    images: list[Path],
    vae,
    device,
    dtype,
    preview_root: Path,
    previews: _PreviewOptions,
    *,
    max_side: int | None,
    seed: int,
    hf_cutoff_fraction: float,
    cancel_check: CancelCheck | None,
) -> _ReconstructionPass:
    """Encode/decode every image without letting one bad input abort the pass."""
    import torch
    from PIL import Image

    result = _ReconstructionPass()
    for path in images:
        check_cancel(cancel_check)
        try:
            recon = _encode_decode(vae, device, dtype, path, max_side=max_side, seed=seed)
            check_cancel(cancel_check)
            orig_arr = np.array(Image.open(path).convert("RGB").resize(
                (recon.shape[1], recon.shape[0]), Image.LANCZOS
            ))
            loss = _hf_loss(
                _to_lab_l(orig_arr),
                _to_lab_l(recon),
                cutoff_fraction=hf_cutoff_fraction,
            )
            if previews.writes_anything:
                result.review_artifacts[str(path)] = _save_review_artifacts(
                    path,
                    recon,
                    preview_root,
                    diff_amplification=previews.diff_amplification,
                    gaussian_blur_sigma=previews.gaussian_blur_sigma,
                    gaussian_blur_kernel=previews.gaussian_blur_kernel,
                    otsu_enabled=previews.otsu_enabled,
                    output_preview=previews.write_vae,
                    output_silhouette=previews.write_diff,
                    output_hard_silhouette=previews.write_hard,
                )
            result.hf_scores[str(path)] = loss
            result.reconstructions[str(path)] = recon
        except CancelledRun:
            raise
        except Exception as exc:
            reporter.warn(
                f"Reconstruction failed for {path.name}; keeping it unassessed: {exc}"
            )
            result.failures.append(
                {"stage": "reconstruct", "path": str(path), "error": str(exc)})
        finally:
            if device == "cuda":
                torch.cuda.empty_cache()
    return result
