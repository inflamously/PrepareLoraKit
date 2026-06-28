from PIL import Image

from prepare_lora_kit.steps.s5_caption.artifacts import (
    _is_bbox_artifact,
    _save_bbox_training_item,
    _update_bbox_caption,
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


def test_update_bbox_caption_rewrites_sidecar(tmp_path):
    source = tmp_path / "image.png"
    crop = Image.new("RGB", (12, 8), "blue")
    source.write_bytes(b"placeholder")

    result = _save_bbox_training_item(crop, source, tmp_path, "blue detail", "tok")
    sidecar = tmp_path / "plk_bbox__image__01.txt"
    assert sidecar.read_text(encoding="utf-8") == "tok, Blue detail"

    final = _update_bbox_caption(sidecar, "tok, blue detail and a red hat", "tok")

    # Normalized like the initial write: body capitalized, leading token preserved
    # verbatim (not re-capitalized to "Tok") and not duplicated.
    assert final == "tok, Blue detail and a red hat"
    assert sidecar.read_text(encoding="utf-8") == "tok, Blue detail and a red hat"
    assert result["sidecar_path"] == str(sidecar)


def test_update_bbox_caption_prepends_missing_token(tmp_path):
    sidecar = tmp_path / "plk_bbox__image__01.txt"
    sidecar.write_text("tok, old caption", encoding="utf-8")

    final = _update_bbox_caption(sidecar, "a silver buckle", "tok")

    assert final == "tok, A silver buckle"
    assert sidecar.read_text(encoding="utf-8") == "tok, A silver buckle"


def test_bbox_artifacts_are_excluded_from_caption_sources(tmp_path):
    original = tmp_path / "image.png"
    artifact = tmp_path / "plk_bbox__image__01.png"

    assert not _is_bbox_artifact(original)
    assert _is_bbox_artifact(artifact)
