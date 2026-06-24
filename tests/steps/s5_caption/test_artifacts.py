from PIL import Image

from prepare_lora_kit.steps.s5_caption.artifacts import (
    _is_bbox_artifact,
    _save_bbox_training_item,
)


def test_bbox_training_item_is_written(tmp_path):
    source = tmp_path / "image.png"
    crop = Image.new("RGB", (12, 8), "blue")
    source.write_bytes(b"placeholder")

    result = _save_bbox_training_item(
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

    assert not _is_bbox_artifact(original)
    assert _is_bbox_artifact(artifact)
