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


def test_mock_caption_persists_boxes_sidecar_and_reloads_on_force(tmp_path):
    img = _write_image(tmp_path / "image.png")
    box = {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6, "label": "a red car"}
    provider = _BatchProvider(lambda d: {"annotations": [dict(box)], "skipped": False})

    invoke._mock_caption(
        tmp_path, tmp_path, concept_token="tok", force=False, interaction=provider,
    )
    assert (tmp_path / "plk_bbox__image__boxes.json").exists()

    # A forced re-run reloads the saved box into the descriptor handed to the UI and
    # never deletes the reload sidecar.
    second = _BatchProvider(lambda d: {"annotations": d["annotations"], "skipped": False})
    invoke._mock_caption(
        tmp_path, tmp_path, concept_token="tok", force=True, interaction=second,
    )
    descriptor = next(d for d in second.seen if Path(d["path"]).name == "image.png")
    assert descriptor["annotations"][0]["label"] == "a red car"
    assert (tmp_path / "plk_bbox__image__boxes.json").exists()


def test_mock_caption_resume_skips_done_and_prompts_only_pending(tmp_path):
    _write_image(tmp_path / "done.png")
    box = {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6, "label": "a red car"}
    invoke._mock_caption(
        tmp_path, tmp_path, concept_token="tok", force=False,
        interaction=_BatchProvider(lambda d: {"annotations": [dict(box)], "skipped": False}),
    )
    assert (tmp_path / "done.txt").exists()
    done_caption = (tmp_path / "done.txt").read_text(encoding="utf-8")

    # A new uncaptioned image appears; resume without force prompts only for it and
    # leaves the done image (and its boxes) untouched.
    _write_image(tmp_path / "new.png")
    second = _BatchProvider(lambda d: {"annotations": [], "skipped": False})
    invoke._mock_caption(
        tmp_path, tmp_path, concept_token="tok", force=False, interaction=second,
    )
    assert {Path(d["path"]).name for d in second.seen} == {"new.png"}
    assert (tmp_path / "new.txt").exists()
    assert (tmp_path / "plk_bbox__done__boxes.json").exists()
    assert (tmp_path / "done.txt").read_text(encoding="utf-8") == done_caption
