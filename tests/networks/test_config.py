"""Unit tests for the generic adapter-network config (NetworkConfig)."""
import pytest

from prepare_lora_kit.networks.config import NetworkConfig

# The flux-klein lora block as authored in configs/networks/flux_klein_9b.yaml.
_FLUX_LORA = {
    "type": "lora",
    "linear": 16,
    "linear_alpha": 16,
    "conv": 16,
    "conv_alpha": 16,
}


def test_equivalence_with_legacy_deep_merge():
    """to_toolkit_dict() must reproduce the old _deep_merge output for flux-klein."""
    # Legacy: _deep_merge(tmpl["network"], {"linear": rank, "linear_alpha": alpha}).
    rank, alpha = 32, 16
    legacy = {**_FLUX_LORA, "linear": rank, "linear_alpha": alpha}

    rendered = (
        NetworkConfig.from_dict(_FLUX_LORA)
        .with_rank_alpha(rank, alpha)
        .to_toolkit_dict()
    )
    assert rendered == legacy


def test_no_extra_keys_for_lora():
    """A bare lora block must not gain transformer_only / lokr_* keys."""
    rendered = NetworkConfig.from_dict(_FLUX_LORA).to_toolkit_dict()
    assert set(rendered) == {"type", "linear", "linear_alpha", "conv", "conv_alpha"}


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown network type"):
        NetworkConfig.from_dict({"type": "bogus"})


@pytest.mark.parametrize("bad", [
    {"type": "lora", "linear": 0},
    {"type": "lora", "dropout": 1.0},
    {"type": "lora", "dropout": -0.1},
    {"type": "lora", "conv": 0},
])
def test_validation_rejects_bad_values(bad):
    with pytest.raises(ValueError):
        NetworkConfig.from_dict(bad)


def test_rank_alpha_aliases():
    cfg = NetworkConfig.from_dict({"type": "lora", "rank": 24})
    assert cfg.linear == 24
    assert cfg.linear_alpha == 24  # alpha defaults to linear
    cfg2 = NetworkConfig.from_dict({"type": "lora", "rank": 24, "alpha": 12})
    assert (cfg2.linear, cfg2.linear_alpha) == (24, 12)


def test_lokr_gating():
    """Overriding to lokr drops conv and emits the lokr_* keys."""
    rendered = NetworkConfig.from_dict({**_FLUX_LORA, "type": "lokr"}).to_toolkit_dict()
    assert "conv" not in rendered and "conv_alpha" not in rendered
    assert rendered["lokr_factor"] == -1
    assert rendered["lokr_full_rank"] is False


def test_dora_keeps_conv():
    rendered = NetworkConfig.from_dict({**_FLUX_LORA, "type": "dora"}).to_toolkit_dict()
    assert rendered["type"] == "dora"
    assert rendered["conv"] == 16 and rendered["conv_alpha"] == 16


def test_unknown_keys_fold_into_network_kwargs():
    cfg = NetworkConfig.from_dict({
        "type": "lokr",
        "linear": 16,
        "ignore_if_contains": ["foo"],          # unknown top-level → network_kwargs
        "network_kwargs": {"rank_dropout": 0.1},
    })
    assert cfg.network_kwargs == {"rank_dropout": 0.1, "ignore_if_contains": ["foo"]}
    rendered = cfg.to_toolkit_dict()
    assert rendered["network_kwargs"]["ignore_if_contains"] == ["foo"]


def test_conv_alpha_defaults_to_conv():
    cfg = NetworkConfig.from_dict({"type": "lora", "linear": 16, "conv": 8})
    assert cfg.conv_alpha == 8
