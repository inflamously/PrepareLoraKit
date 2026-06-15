from pathlib import Path
from .base import NetworkProfile

_YAML = Path(__file__).parents[2] / "configs" / "networks" / "flux_klein_9b.yaml"


def load() -> NetworkProfile:
    return NetworkProfile.from_yaml(_YAML)
