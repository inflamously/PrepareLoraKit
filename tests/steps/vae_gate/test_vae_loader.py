"""Routing tests for VAE-gate model resolution.

These exercise ``_instantiate_vae`` directly with a fake ``AutoencoderKL`` so no real
torch/diffusers/model load happens (per the CLAUDE.md ML-mocking rule).
"""
import sys
import types

from prepare_lora_kit.steps.vae_gate.vae import _instantiate_vae


class _FakeVae:
    """Records which loader produced it and with what arguments."""

    def __init__(self, source, **kwargs):
        self.source = source
        self.kwargs = kwargs


class _FakeAutoencoderKL:
    @classmethod
    def from_pretrained(cls, model_id, **kwargs):
        return _FakeVae(("from_pretrained", model_id), **kwargs)

    @classmethod
    def from_single_file(cls, path, **kwargs):
        return _FakeVae(("from_single_file", path), **kwargs)


def test_repo_id_routes_to_from_pretrained_with_vae_subfolder():
    vae = _instantiate_vae("black-forest-labs/FLUX.2-klein-base-9B", _FakeAutoencoderKL)
    assert vae.source == ("from_pretrained", "black-forest-labs/FLUX.2-klein-base-9B")
    assert vae.kwargs == {"subfolder": "vae"}


def test_local_single_file_routes_to_from_single_file_without_subfolder():
    vae = _instantiate_vae("/models/sdxl_vae.safetensors", _FakeAutoencoderKL)
    assert vae.source == ("from_single_file", "/models/sdxl_vae.safetensors")
    assert vae.kwargs == {}


def test_single_file_suffix_match_is_case_insensitive():
    vae = _instantiate_vae("/models/AE.SafeTensors", _FakeAutoencoderKL)
    assert vae.source[0] == "from_single_file"


def test_hf_file_ref_downloads_then_single_file_loads(monkeypatch):
    calls = {}

    def _fake_download(repo_id, filename):
        calls["args"] = (repo_id, filename)
        return "/cache/ae.safetensors"

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.hf_hub_download = _fake_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)

    vae = _instantiate_vae("org/flux::vae/ae.safetensors", _FakeAutoencoderKL)

    assert calls["args"] == ("org/flux", "vae/ae.safetensors")
    assert vae.source == ("from_single_file", "/cache/ae.safetensors")


def test_config_id_forwarded_to_single_file_loader():
    vae = _instantiate_vae(
        "/models/ae.safetensors", _FakeAutoencoderKL, config_id="black-forest-labs/FLUX.1-dev"
    )
    assert vae.source == ("from_single_file", "/models/ae.safetensors")
    assert vae.kwargs == {"config": "black-forest-labs/FLUX.1-dev", "subfolder": "vae"}
