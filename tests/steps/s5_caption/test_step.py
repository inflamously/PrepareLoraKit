from PIL import Image

from prepare_lora_kit.project.configs import CaptionConfig
from prepare_lora_kit.steps.s5_caption import step as caption_step
from prepare_lora_kit.steps.s5_caption import vlm


def test_caption_config_defaults_to_auto_vram():
    cfg = CaptionConfig()

    assert cfg.vram_tier == "auto"
    assert cfg.quantization == "auto"


def test_auto_quantization_uses_8bit_for_mid_vram(monkeypatch):
    class _Props:
        total_memory = 24 * 1024 ** 3

    class _Cuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def get_device_properties(_index):
            return _Props()

    class _Torch:
        cuda = _Cuda()

    monkeypatch.setattr(vlm, "_bitsandbytes_available", lambda: True)

    assert vlm._resolve_quantization("auto", _Torch) == "8bit"


def test_bbox_training_item_is_written(tmp_path):
    source = tmp_path / "image.png"
    crop = Image.new("RGB", (12, 8), "blue")
    source.write_bytes(b"placeholder")

    result = caption_step._save_bbox_training_item(
        crop,
        source,
        tmp_path,
        "blue detail",
        "tok",
    )

    assert result["crop_name"] == "plk_bbox__image__01.png"
    assert (tmp_path / "plk_bbox__image__01.png").exists()
    assert (tmp_path / "plk_bbox__image__01.txt").read_text(encoding="utf-8") == "tok, Blue detail"


def test_bbox_artifacts_are_excluded_from_caption_sources(tmp_path):
    original = tmp_path / "image.png"
    artifact = tmp_path / "plk_bbox__image__01.png"

    assert not caption_step._is_bbox_artifact(original)
    assert caption_step._is_bbox_artifact(artifact)
