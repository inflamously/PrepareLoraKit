from .base import NetworkProfile
from ..utils.registry import ConfigRegistry

_registry: ConfigRegistry[NetworkProfile] = ConfigRegistry(
    kind="network",
    subdir="networks",
    loader=NetworkProfile.from_yaml,
    builtin_package="prepare_lora_kit.networks.modules",
    builtins={"flux-klein-9b": "flux_klein"},
)

# Exposed for callers that resolve config paths directly.
_CONFIGS_DIR = _registry.configs_dir


def load(name: str) -> NetworkProfile:
    """Load a NetworkProfile by name. Checks built-ins then configs/ dir."""
    return _registry.load(name)


def list_networks() -> list[str]:
    return _registry.list()
