import os

import pytest
import yaml

from prepare_lora_kit import paths, settings
from prepare_lora_kit.settings.model import AppSettings
from prepare_lora_kit.settings.store import apply_environment, read_settings


def test_missing_file_gives_fully_defaulted_settings():
    loaded = settings.load_settings()

    assert loaded == AppSettings()
    assert loaded.is_empty()
    assert not settings.settings_path().exists()


@pytest.mark.parametrize("body", ["", "\n", "# only a comment\n", "null\n"])
def test_empty_or_commented_file_is_not_an_error(tmp_path, body):
    path = tmp_path / "settings.yaml"
    path.write_text(body, encoding="utf-8")

    assert read_settings(path) == AppSettings()


def test_round_trips_through_disk():
    stored = settings.save_settings_dict(
        {
            "huggingface": {"home": "/tmp/hf"},
            "hardware": {"vram_tier": "mid", "cuda_device": "1"},
            "project_defaults": {"caption_model_id": "Qwen/Qwen3-VL-8B-Instruct"},
        }
    )
    settings.invalidate()
    loaded = settings.load_settings()

    assert loaded == stored
    assert loaded.hardware.vram_tier == "mid"
    assert loaded.project_defaults.caption_model_id == "Qwen/Qwen3-VL-8B-Instruct"


def test_saved_file_is_yaml_with_a_version_and_no_token_key():
    settings.save_settings_dict({"hardware": {"vram_tier": "high"}})

    data = yaml.safe_load(settings.settings_path().read_text(encoding="utf-8"))

    assert data["version"] == 1
    # The token is whatever `hf auth login` stored; we must never persist one.
    assert "token" not in yaml.safe_dump(data)


def test_unknown_keys_and_blank_strings_are_ignored(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 99,
                "future_section": {"whatever": 1},
                "hardware": {"vram_tier": "low", "cuda_device": "   "},
            }
        ),
        encoding="utf-8",
    )

    loaded = read_settings(path)

    assert loaded.hardware.vram_tier == "low"
    assert loaded.hardware.cuda_device is None


def test_invalid_value_for_a_known_key_raises(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump({"hardware": {"vram_tier": "enormous"}}), encoding="utf-8")

    with pytest.raises(ValueError, match="vram_tier"):
        read_settings(path)


def test_malformed_yaml_names_the_file(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text("hardware: [unclosed\n", encoding="utf-8")

    with pytest.raises(ValueError, match=str(path.name)):
        read_settings(path)


def test_non_mapping_document_raises(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(["a", "list"]), encoding="utf-8")

    with pytest.raises(ValueError, match="mapping"):
        read_settings(path)


def test_save_creates_the_parent_directory_and_leaves_no_temp_file(tmp_path, monkeypatch):
    nested = tmp_path / "deep" / "nested" / "settings.yaml"
    monkeypatch.setattr(paths, "SETTINGS_PATH", nested)
    settings.invalidate()

    settings.save_settings_dict({"hardware": {"vram_tier": "max"}})

    assert nested.exists()
    assert not list(nested.parent.glob("*.plk_tmp"))


def test_cache_follows_a_redirected_path(tmp_path, monkeypatch):
    settings.save_settings_dict({"hardware": {"vram_tier": "low"}})
    assert settings.load_settings().hardware.vram_tier == "low"

    # Redirecting the path must not keep serving the previous document.
    monkeypatch.setattr(paths, "SETTINGS_PATH", tmp_path / "elsewhere.yaml")

    assert settings.load_settings().hardware.vram_tier is None


def test_apply_environment_sets_hf_home_without_overriding_the_shell(monkeypatch):
    monkeypatch.delenv("HF_HOME", raising=False)
    apply_environment(AppSettings.from_dict({"huggingface": {"home": "/tmp/hf-cache"}}))
    assert "hf-cache" in os.environ["HF_HOME"]

    monkeypatch.setenv("HF_HOME", "/explicitly/exported")
    apply_environment(AppSettings.from_dict({"huggingface": {"home": "/tmp/hf-cache"}}))
    assert os.environ["HF_HOME"] == "/explicitly/exported"


def test_apply_environment_does_nothing_when_unset(monkeypatch):
    monkeypatch.delenv("HF_HOME", raising=False)

    apply_environment(AppSettings())

    assert "HF_HOME" not in os.environ
