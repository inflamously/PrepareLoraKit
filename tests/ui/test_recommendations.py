from PIL import Image

from prepare_lora_kit.ui.runner.recommendations import upscale_attention


def _img(path, size):
    Image.new("RGB", size, "red").save(path)
    return path


def test_upscale_attention_flags_undersized(tmp_path):
    _img(tmp_path / "small.png", (1000, 1000))
    _img(tmp_path / "big.png", (4000, 4000))

    att = upscale_attention(tmp_path, threshold=1536)

    assert att == {"recommended": True, "undersized": 1, "jpeg": 0, "scanned": 2}


def test_upscale_attention_flags_jpeg_even_when_large(tmp_path):
    _img(tmp_path / "big.jpg", (4000, 4000))

    att = upscale_attention(tmp_path, threshold=1536)

    assert att["recommended"] is True
    assert att["undersized"] == 0
    assert att["jpeg"] == 1


def test_upscale_attention_clean_dataset_not_recommended(tmp_path):
    _img(tmp_path / "a.png", (4000, 4000))
    _img(tmp_path / "b.png", (2048, 2048))

    att = upscale_attention(tmp_path, threshold=1536)

    assert att == {"recommended": False, "undersized": 0, "jpeg": 0, "scanned": 2}


def test_upscale_attention_missing_or_none_dir_returns_none(tmp_path):
    assert upscale_attention(None, threshold=1536) is None
    assert upscale_attention(tmp_path / "nope", threshold=1536) is None


def test_upscale_attention_respects_cap(tmp_path):
    for i in range(5):
        _img(tmp_path / f"img_{i}.png", (1000, 1000))

    att = upscale_attention(tmp_path, threshold=1536, cap=3)

    assert att["scanned"] == 3
    assert att["undersized"] == 3
