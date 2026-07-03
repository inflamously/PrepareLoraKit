from pathlib import Path
from typing import Any

import yaml

from prepare_lora_kit.utils.registry import ConfigRegistry
from .base import ProjectConfig

_registry: ConfigRegistry[ProjectConfig] = ConfigRegistry(
    kind="project",
    subdir="projects",
    loader=ProjectConfig.from_yaml,
    builtin_package="prepare_lora_kit.project",  # reserved for future built-ins
    skip_example=True,
)

# Exposed for callers that resolve config paths directly (e.g. cli/run.py).
_CONFIGS_DIR = _registry.configs_dir


def _default_substep_data(step_type: str) -> list[dict[str, Any]]:
    from .steps import SUBSTEP_REGISTRY

    return [
        {"id": definition.id, "enabled": definition.enabled_by_default}
        for definition in SUBSTEP_REGISTRY.get(step_type, ())
    ]


def _default_pipeline() -> list[dict[str, Any]]:
    return [
        {
            "type": "ImportStep",
            "substeps": _default_substep_data("ImportStep"),
        },
        {
            "type": "QualityGateStep",
            "scorers": [
                {"name": "min_side", "enabled": True, "op": "lt", "threshold": 1024.0},
                {"name": "blur", "enabled": True, "op": "lt", "threshold": 100.0, "borderline": 150.0},
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
            "type": "UpscaleStep",
            "upscale_target": 3072,
            "hallucination_ssim_threshold": 0.60,
            "upscale_model": "seedvr2",
            "substeps": _default_substep_data("UpscaleStep"),
        },
        {
            "type": "CaptionStep",
            "caption_model_id": None,
            "caption_model_task": "auto",
            "vram_tier": "auto",
            "max_new_tokens": 200,
            "spot_check_pct": 0.10,
            "substeps": _default_substep_data("CaptionStep"),
        },
        {
            "type": "VaeGateStep",
            "diff_amplification": 4.0,
            "gaussian_blur_sigma": 2.0,
            "gaussian_blur_kernel": 21,
            "otsu_enabled": True,
            "output_previews": True,
            "output_silhouettes": True,
            "output_hard_silhouettes": True,
            "outlier_sigma": 2.0,
            "hf_cutoff_fraction": 0.25,
            "max_side": None,
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
            "substeps": _default_substep_data("AuditStep"),
        },
        {
            "type": "ConfigGenStep",
            "base_template_path": None,
            "substeps": _default_substep_data("ConfigGenStep"),
        },
        {
            "type": "BucketDryRunStep",
            "thin_threshold": 2,
            "cache_mode": False,
            "bucket_overrides": None,
            "substeps": _default_substep_data("BucketDryRunStep"),
        },
        {
            "type": "ExportStep",
            "target_dir": None,  # null → sibling <input>_export folder
            "substeps": _default_substep_data("ExportStep"),
        },
    ]


def config_path_for_name(name: str) -> Path:
    return _registry.configs_dir / f"{name.replace('-', '_')}.yaml"


def default_project_data(
    name: str,
    input_dir: Path | str | None = None,
    network: str = "flux-klein-9b",
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": name,
        "network": network,
    }
    if input_dir is not None:
        data["input_dir"] = str(input_dir)
    if output_dir is not None:
        data["output_dir"] = str(output_dir)
    data["pipeline"] = _default_pipeline()
    return data


def write_default_project(
    name: str,
    path: Path | None = None,
    input_dir: Path | str | None = None,
    network: str = "flux-klein-9b",
    output_dir: Path | str | None = None,
) -> Path:
    """Write a fully-defaulted project config and return its path."""
    config_path = path or config_path_for_name(name)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            default_project_data(name, input_dir, network, output_dir),
            sort_keys=False,
        )
    )
    return config_path


def create_project(
    name: str,
    network: str = "flux-klein-9b",
    input_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> Path:
    """Create a new project YAML. Raises if a project with this name exists."""
    name = name.strip()
    if not name:
        raise ValueError("Project name is required.")
    config_path = config_path_for_name(name)
    if config_path.exists():
        raise ValueError(f"A project named '{name}' already exists.")
    return write_default_project(
        name,
        config_path,
        input_dir=input_dir or None,
        network=network or "flux-klein-9b",
        output_dir=output_dir or None,
    )


def update_project_meta(
    orig_name: str,
    name: str,
    network: str = "flux-klein-9b",
    input_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> Path:
    """Patch a project's top-level metadata, preserving its pipeline.

    Supports renaming: when ``name`` differs from ``orig_name`` the YAML is
    written under the new path and the old file removed.
    """
    name = name.strip()
    if not name:
        raise ValueError("Project name is required.")

    src_path = config_path_for_name(orig_name)
    if not src_path.exists():
        raise ValueError(f"Project '{orig_name}' does not exist.")

    dst_path = config_path_for_name(name)
    if dst_path != src_path and dst_path.exists():
        raise ValueError(f"A project named '{name}' already exists.")

    data = yaml.safe_load(src_path.read_text()) or {}
    data["name"] = name
    data["network"] = network or "flux-klein-9b"
    if input_dir:
        data["input_dir"] = str(input_dir)
    else:
        data.pop("input_dir", None)
    if output_dir:
        data["output_dir"] = str(output_dir)
    else:
        data.pop("output_dir", None)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(yaml.safe_dump(data, sort_keys=False))
    if dst_path != src_path:
        src_path.unlink(missing_ok=True)
    return dst_path


def delete_project(name: str) -> None:
    """Remove a project's YAML config (idempotent)."""
    config_path_for_name(name).unlink(missing_ok=True)


def duplicate_project(name: str, new_name: str | None = None) -> str:
    """Copy a project's YAML to a new name and return that name.

    When ``new_name`` is omitted, an available ``<name>_copy`` / ``<name>_copy2``
    name is chosen automatically.
    """
    src_path = config_path_for_name(name)
    if not src_path.exists():
        raise ValueError(f"Project '{name}' does not exist.")

    if new_name:
        target = new_name.strip()
        if config_path_for_name(target).exists():
            raise ValueError(f"A project named '{target}' already exists.")
    else:
        target = f"{name}_copy"
        suffix = 2
        while config_path_for_name(target).exists():
            target = f"{name}_copy{suffix}"
            suffix += 1

    data = yaml.safe_load(src_path.read_text()) or {}
    data["name"] = target
    dst_path = config_path_for_name(target)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(yaml.safe_dump(data, sort_keys=False))
    return target


def set_project_input_dir(name: str, input_dir: Path | str) -> Path:
    """Persist input_dir on an existing YAML project without changing pipeline data."""
    config_path = config_path_for_name(name)
    if not config_path.exists():
        write_default_project(name, config_path, input_dir)
        return config_path

    data = yaml.safe_load(config_path.read_text()) or {}
    data["input_dir"] = str(input_dir)
    config_path.write_text(yaml.safe_dump(data, sort_keys=False))
    return config_path


def load_or_create_for_input(input_dir: Path | str) -> ProjectConfig:
    resolved = Path(input_dir).expanduser().resolve()
    name = resolved.name
    set_project_input_dir(name, resolved)
    return load(name)


def load(name: str) -> ProjectConfig:
    """Load a ProjectConfig by name. Checks built-ins then configs/projects/ dir."""
    return _registry.load(name)


def list_projects() -> list[str]:
    return _registry.list()
