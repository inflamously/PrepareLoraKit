"""The canonical default pipeline for a new project.

One place, as plain data: every step in workflow order with the settings a fresh
project starts from. ``settings.seeding`` merges configured globals into this
list at creation time, and ``project.store`` splits the result into files — so
this stays a flat ``list[dict]`` keyed by CamelCase step type, exactly as the
single-file YAML used to hold it.
"""
from __future__ import annotations

from typing import Any


def _default_substep_data(step_type: str) -> list[dict[str, Any]]:

    from prepare_lora_kit.project.steps import SUBSTEP_REGISTRY
    return [
        {"id": definition.id, "enabled": definition.enabled_by_default}
        for definition in SUBSTEP_REGISTRY.get(step_type, ())
    ]


def default_pipeline() -> list[dict[str, Any]]:
    return [
        {
            "type": "ImportStep",
            "substeps": _default_substep_data("ImportStep"),
        },
        {
            "type": "UpscaleStep",
            "upscale_target": 3072,
            "hallucination_ssim_threshold": 0.60,
            "upscale_model": "seedvr2",
            "substeps": _default_substep_data("UpscaleStep"),
        },
        {
            "type": "QualityGateStep",
            "scorers": [
                {"name": "min_side", "enabled": True, "op": "lt", "threshold": 1024.0},
                {"name": "blur", "enabled": True, "op": "lt",
                 "threshold": 100.0, "borderline": 150.0},
                {"name": "noise", "enabled": True, "op": "gt", "threshold": 25.0},
                {"name": "jpeg", "enabled": True, "op": "gt", "threshold": 0.08},
                {"name": "watermark", "enabled": True, "op": "gt", "threshold": 0.80},
            ],
            "manual_review": True,
            "auto_only": False,
            "manual_all": False,
            "substeps": _default_substep_data("QualityGateStep"),
        },
        {
            "type": "CurateStep",
            "dedup_hamming_distance": 3,
            "pca_umap_switch_threshold": 30,
            "umap_n_neighbors": 15,
            "umap_min_dist": 0.1,
            "pca_n_components": 2,
            "coverage_embedding_model": "auto",
            "substeps": _default_substep_data("CurateStep"),
        },
        {
            "type": "CaptionBboxStep",
            "caption_model_id": None,
            "caption_model_task": "auto",
            "vram_tier": "auto",
            "max_new_tokens": 200,
            "spot_check_pct": 0.10,
            "substeps": _default_substep_data("CaptionBboxStep"),
        },
        {
            "type": "CaptionVerifierStep",
            "t2i_model_id": "auto",
            "vram_tier": "auto",
            "width": None,
            "height": None,
            "num_inference_steps": None,
            "guidance_scale": None,
            "seed": 42,
            "negative_prompt": None,
            "max_images": None,
            "keep_previews": True,
            "write_edited_captions": True,
            "substeps": _default_substep_data("CaptionVerifierStep"),
        },
        {
            "type": "VaeGateStep",
            "vae_model_id": "black-forest-labs/FLUX.2-klein-base-9B",
            "vae_config_id": None,
            "diff_amplification": 4.0,
            "gaussian_blur_sigma": 2.0,
            "gaussian_blur_kernel": 21,
            "otsu_enabled": True,
            "output_previews": True,
            "output_silhouettes": True,
            "output_hard_silhouettes": True,
            "outlier_sigma": 2.0,
            "hf_cutoff_fraction": 0.25,
            "max_side": 1536,
            "seed": 42,
            "substeps": _default_substep_data("VaeGateStep"),
        },
        {
            "type": "AuditStep",
            "min_caption": 5,
            "max_caption": 600,
            "check_pairing": True,
            "check_corrupt": True,
            "check_caption_length": True,
            "check_resolution_gate": True,
            "min_resolution_side": 1536,
            "caption_model_type": "auto",
            "substeps": _default_substep_data("AuditStep"),
        },
        {
            "type": "BucketPoolsCheckStep",
            "thin_threshold": 2,
            "cache_mode": False,
            "resolution_buckets": [
                [1024, 1024],
                [1152, 896],
                [896, 1152],
                [1216, 832],
                [832, 1216],
                [1344, 768],
                [768, 1344],
                [1536, 640],
                [640, 1536],
            ],
            "substeps": _default_substep_data("BucketPoolsCheckStep"),
        },
        {
            "type": "ExportStep",
            "target_dir": None,  # null → sibling <input>_export folder
            "substeps": _default_substep_data("ExportStep"),
        },
    ]
