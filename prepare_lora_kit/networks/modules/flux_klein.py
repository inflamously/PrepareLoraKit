from prepare_lora_kit.networks.base import NetworkProfile
from prepare_lora_kit.paths import CONFIGS_DIR

_YAML = CONFIGS_DIR / "networks" / "flux_klein_9b.yaml"


def load() -> NetworkProfile:
    return NetworkProfile.from_yaml(_YAML)
