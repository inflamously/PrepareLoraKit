import sys

import pytest

from prepare_lora_kit import settings
from prepare_lora_kit_ui.bridge import UiBridge


@pytest.fixture
def bridge():
    return UiBridge()


def test_get_settings_returns_defaults_and_choices(bridge):
    payload = bridge.get_settings()

    assert payload["settings"]["version"] == 1
    assert payload["settings"]["project_defaults"]["caption_model_id"] is None
    assert payload["choices"]["caption_model_id"], "caption models must be offered"
    assert {"value", "label"} <= set(payload["choices"]["caption_model_id"][0])
    assert payload["placeholders"]["caption_model_id"]
    assert payload["settings_path"].endswith("settings.yaml")
    assert "login" in payload["login_command"]


def test_get_settings_does_not_import_torch(bridge):
    """The modal must open instantly; a torch import would stall the UI thread."""
    if "torch" in sys.modules:
        pytest.skip("torch was already imported by another test in this process")

    bridge.get_settings()

    assert "torch" not in sys.modules


def test_get_settings_offers_the_same_caption_models_as_the_step_config(bridge):
    from prepare_lora_kit.project.config_schema.steps import caption_bbox

    spec = next(f for f in caption_bbox.FIELDS if f.name == "caption_model_id")
    offered = [choice["value"] for choice in bridge.get_settings()["choices"]["caption_model_id"]]

    assert offered == [option["value"] for option in spec.options]


def test_get_settings_offers_the_same_seedvr2_models_as_the_step_config(bridge):
    from prepare_lora_kit.project.config_schema.steps import upscale

    spec = next(f for f in upscale.FIELDS if f.name == "seedvr2_dit_model")
    offered = [
        choice["value"] for choice in bridge.get_settings()["choices"]["seedvr2_dit_model"]
    ]

    assert offered == [option["value"] for option in spec.options]
    assert offered[0] == "auto"


def test_save_settings_persists_and_echoes_the_new_payload(bridge):
    payload = bridge.save_settings(
        {
            "hardware": {"vram_tier": "mid"},
            "project_defaults": {"caption_model_id": "Qwen/Qwen3-VL-8B-Instruct"},
        }
    )

    assert payload["settings"]["hardware"]["vram_tier"] == "mid"
    assert settings.load_settings().project_defaults.caption_model_id == "Qwen/Qwen3-VL-8B-Instruct"
    assert settings.settings_path().exists()


def test_save_settings_rejects_an_invalid_value(bridge):
    with pytest.raises(ValueError, match="vram_tier"):
        bridge.save_settings({"hardware": {"vram_tier": "gigantic"}})

    assert not settings.settings_path().exists()


def test_save_settings_accepts_an_empty_payload(bridge):
    payload = bridge.save_settings({})

    assert payload["settings"]["hardware"]["vram_tier"] is None


def test_model_ids_always_include_the_gated_vae_default(bridge):
    """FLUX.2 klein is the VaeGate default and is gated — the check must cover it."""
    assert "black-forest-labs/FLUX.2-klein-base-9B" in bridge.get_settings()["model_ids"]


def test_model_ids_skip_sentinels_and_local_paths(bridge):
    payload = bridge.save_settings(
        {
            "project_defaults": {
                "t2i_model_id": "auto",
                "vae_model_id": "/local/checkpoint.safetensors",
                "caption_model_id": "Qwen/Qwen3-VL-2B-Instruct",
            }
        }
    )

    assert payload["model_ids"] == ["Qwen/Qwen3-VL-2B-Instruct"]


def test_check_model_access_uses_the_configured_ids(bridge, monkeypatch):
    pytest.importorskip("huggingface_hub")
    seen = []
    monkeypatch.setattr("huggingface_hub.auth_check", seen.append)
    bridge.save_settings({"project_defaults": {"caption_model_id": "Qwen/Qwen3-VL-2B-Instruct"}})

    results = bridge.check_model_access()["results"]

    assert "Qwen/Qwen3-VL-2B-Instruct" in seen
    assert all(result["status"] == "ok" for result in results)


def test_check_model_access_accepts_an_explicit_list(bridge, monkeypatch):
    pytest.importorskip("huggingface_hub")
    seen = []
    monkeypatch.setattr("huggingface_hub.auth_check", seen.append)

    bridge.check_model_access(["only/this-one"])

    assert seen == ["only/this-one"]
