from pathlib import Path
from .base import NetworkProfile

_BUILTIN: dict[str, str] = {
    "flux-klein-9b": "flux_klein",
}

_CONFIGS_DIR = Path(__file__).parents[2] / "configs" / "networks"


def load(name: str) -> NetworkProfile:
    """Load a NetworkProfile by name. Checks built-ins then configs/ dir."""
    if name in _BUILTIN:
        module_name = _BUILTIN[name]
        import importlib
        mod = importlib.import_module(f"prepare_lora_kit.networks.{module_name}")
        return mod.load()

    # Fall back to YAML in configs/networks/<name>.yaml (hyphens → underscores)
    yaml_name = name.replace("-", "_") + ".yaml"
    yaml_path = _CONFIGS_DIR / yaml_name
    if yaml_path.exists():
        return NetworkProfile.from_yaml(yaml_path)

    available = list(_BUILTIN.keys()) + [
        p.stem.replace("_", "-") for p in _CONFIGS_DIR.glob("*.yaml")
        if p.stem.replace("_", "-") not in _BUILTIN
    ]
    raise ValueError(
        f"Unknown network '{name}'. Available: {', '.join(sorted(set(available)))}"
    )


def list_networks() -> list[str]:
    names = set(_BUILTIN.keys())
    for p in _CONFIGS_DIR.glob("*.yaml"):
        names.add(p.stem.replace("_", "-"))
    return sorted(names)
