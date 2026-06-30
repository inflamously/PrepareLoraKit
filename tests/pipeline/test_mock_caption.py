"""Mock-runtime CaptionStep drives the same batch interaction as the real step."""
from pathlib import Path

from PIL import Image

from prepare_lora_kit import invoke


def _write_image(path: Path) -> Path:
    Image.new("RGB", (16, 12), "blue").save(path)
    return path


class _BatchProvider:
    """Implements the workspace ``annotate_dataset`` hook."""

    def __init__(self, decide):
        self._decide = decide
        self.seen: list[dict] = []

    def annotate_dataset(self, images, *, captioner=None):
        self.seen = [dict(d) for d in images]
        return {str(d["path"]): self._decide(d) for d in images}, False


def test_mock_caption_captions_and_skips_per_decision(tmp_path):
    a = _write_image(tmp_path / "a.png")
    _write_image(tmp_path / "b.png")

    def decide(descriptor):
        if Path(descriptor["path"]).name == "a.png":
            return {"annotations": [], "skipped": False}
        return {"annotations": [], "skipped": True}

    provider = _BatchProvider(decide)
    report = invoke._mock_caption(
        tmp_path, tmp_path, concept_token="tok", force=False, interaction=provider,
    )

    assert (tmp_path / "a.txt").exists()
    assert not (tmp_path / "b.txt").exists()
    assert report["mock_runtime"] is True
    # The descriptors carried the reload fields the workspace expects.
    assert {Path(d["path"]).name for d in provider.seen} == {"a.png", "b.png"}
    assert all("done" in d and "annotations" in d for d in provider.seen)


def test_mock_caption_persists_boxes_sidecar_for_reload(tmp_path):
    img = _write_image(tmp_path / "image.png")
    box = {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6, "label": "a red car"}
    provider = _BatchProvider(lambda d: {"annotations": [dict(box)], "skipped": False})

    invoke._mock_caption(
        tmp_path, tmp_path, concept_token="tok", force=False, interaction=provider,
    )
    assert (tmp_path / "plk_bbox__image__boxes.json").exists()

    # A second run reloads the saved box into the descriptor handed to the UI.
    second = _BatchProvider(lambda d: {"annotations": d["annotations"], "skipped": True})
    invoke._mock_caption(
        tmp_path, tmp_path, concept_token="tok", force=False, interaction=second,
    )
    descriptor = next(d for d in second.seen if Path(d["path"]).name == "image.png")
    assert descriptor["done"] is True
    assert descriptor["annotations"][0]["label"] == "a red car"
