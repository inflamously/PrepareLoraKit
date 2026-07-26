"""Machine fallbacks: the setting replaces a hard-coded constant behind an
existing ``None``. A project that names a value still wins, so no YAML changes
meaning."""
from pathlib import Path

from prepare_lora_kit import settings
from prepare_lora_kit.steps.upscale import seedvr2_adapter as adapter


def _upscaler(**kwargs):
    return adapter.SeedVR2Upscaler(resolution=1024, **kwargs)


def test_defaults_are_unchanged_when_nothing_is_configured():
    up = _upscaler()

    assert up.submodule_dir == Path(__file__).resolve().parents[2] / "third_party" / "seedvr2"
    assert up.model_dir == Path("~/.cache/prepare_lora_kit/seedvr2").expanduser()
    assert up.cuda_device is None


def test_settings_supply_the_fallback(tmp_path):
    settings.save_settings_dict(
        {
            "hardware": {
                "seedvr2_submodule_dir": str(tmp_path / "sub"),
                "seedvr2_model_dir": str(tmp_path / "models"),
                "cuda_device": "1",
            }
        }
    )

    up = _upscaler()

    assert up.submodule_dir == tmp_path / "sub"
    assert up.model_dir == tmp_path / "models"
    assert up.cuda_device == "1"


def test_a_project_value_still_outranks_the_setting(tmp_path):
    settings.save_settings_dict(
        {
            "hardware": {
                "seedvr2_submodule_dir": str(tmp_path / "global-sub"),
                "seedvr2_model_dir": str(tmp_path / "global-models"),
                "cuda_device": "1",
            }
        }
    )

    up = _upscaler(
        submodule_dir=tmp_path / "project-sub",
        model_dir=tmp_path / "project-models",
        cuda_device="0,2",
    )

    assert up.submodule_dir == tmp_path / "project-sub"
    assert up.model_dir == tmp_path / "project-models"
    assert up.cuda_device == "0,2"


def test_user_paths_are_expanded():
    settings.save_settings_dict({"hardware": {"seedvr2_model_dir": "~/somewhere/models"}})

    assert _upscaler().model_dir == Path("~/somewhere/models").expanduser()
