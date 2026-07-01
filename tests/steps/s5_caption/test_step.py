from pathlib import Path

from PIL import Image
import pytest

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.steps.s5_caption import step as caption_step


def _write_image(path: Path, size: tuple[int, int] = (16, 12), color: str = "blue") -> Path:
    Image.new("RGB", size, color).save(path)
    return path


class _AnnotatingProvider:
    def __init__(self):
        self.region_result = None

    def annotate_image(self, path, *, captioner=None):
        crop = Image.new("RGB", (8, 6), "green")
        self.region_result = captioner(
            crop,
            {
                "source_path": str(path),
                "box": {"x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5},
            },
        )
        return (
            [
                {
                    "x1": 0.1,
                    "y1": 0.1,
                    "x2": 0.5,
                    "y2": 0.5,
                    "label": self.region_result["caption"],
                    "crop_name": self.region_result["crop_name"],
                }
            ],
            False,
            False,
        )


class _EditingProvider:
    """Captions a region, then submits an annotation with an EDITED label.

    Mirrors the UI flow: ``captionSelected`` writes the sidecar and stamps
    ``crop_path``/``sidecar_path``/``label`` onto the box; the user then edits the
    label before clicking Done, so the submitted annotation carries the edited text.
    """

    def __init__(self, edited_label: str):
        self.edited_label = edited_label
        self.region_result = None

    def annotate_image(self, path, *, captioner=None):
        crop = Image.new("RGB", (8, 6), "green")
        self.region_result = captioner(
            crop,
            {"source_path": str(path), "box": {"x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}},
        )
        return (
            [
                {
                    "x1": 0.1,
                    "y1": 0.1,
                    "x2": 0.5,
                    "y2": 0.5,
                    "label": self.edited_label,
                    "crop_name": self.region_result["crop_name"],
                    "crop_path": self.region_result["crop_path"],
                    "sidecar_path": self.region_result["sidecar_path"],
                }
            ],
            False,
            False,
        )


class _SkippingProvider:
    def annotate_image(self, path, *, captioner=None):
        return [], True, False


class _BatchProvider:
    """Implements the batch ``annotate_dataset`` hook used by the workspace UI."""

    def __init__(self, decide):
        # decide(descriptor) -> {"annotations": [...], "skipped": bool}
        self._decide = decide
        self.seen: list[dict] = []
        self.skip_all = False

    def annotate_dataset(self, images, *, captioner=None):
        self.seen = [dict(d) for d in images]
        decisions = {}
        for descriptor in images:
            decisions[str(descriptor["path"])] = self._decide(descriptor)
        return decisions, self.skip_all


def _fake_runtime_class(
    events,
    *,
    image_caption: str = "whole original caption",
    image_error: Exception | None = None,
    status: dict | None = None,
):
    class FakeRuntime:
        def __init__(self, model_id, *, task, quantization, dtype, max_pixels,
                     status_callback=None, caption_prompt=None, region_prompt=None):
            self.metadata = {
                "model_id": model_id,
                "task": task,
                "adapter": "fake",
                "device": "cpu",
                "quantization": quantization,
                "dtype": dtype,
                "max_pixels": max_pixels,
            }
            self.status = status or {"phase": "ready", "message": "fake ready"}
            self._status_callback = status_callback
            self._loaded = False
            events.append(("init", model_id, task, quantization, dtype, max_pixels))

        def load(self):
            # Mirror CaptionRuntime.load: idempotent, emits status, no caption work.
            if self._loaded:
                return
            self._loaded = True
            if self._status_callback:
                self._status_callback(self.status)

        def caption_region(self, crop):
            events.append(("region", crop.size))
            return "green detail"

        def caption_image(self, path, annotations, concept_token, *, max_new_tokens):
            if image_error is not None:
                raise image_error
            crop_name = annotations[0]["crop_name"] if annotations else None
            events.append(("image", Path(path).name, crop_name, concept_token, max_new_tokens))
            return image_caption

        def unload(self):
            events.append(("unload",))

    return FakeRuntime


def _event_names(events):
    return [event[0] for event in events]


def test_caption_step_reuses_runtime_for_region_and_original_caption(tmp_path, monkeypatch):
    _write_image(tmp_path / "image.png")
    events = []
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", _fake_runtime_class(events))

    report = caption_step.run(
        tmp_path,
        concept_token="tok",
        output_dir=tmp_path,
        caption_model_id="fake/model",
        interaction=_AnnotatingProvider(),
        spot_check_pct=0,
    )

    assert report["captioned"] == 2
    assert _event_names(events) == ["init", "region", "image", "unload"]
    assert (tmp_path / "image.txt").read_text(encoding="utf-8") == "tok, Whole original caption"
    assert (tmp_path / "plk_bbox__image__01.txt").read_text(encoding="utf-8") == "tok, Green detail"
    assert report["caption_model"]["adapter"] == "fake"
    assert report["caption_status"]["phase"] == "ready"


def test_caption_step_persists_edited_region_caption_to_sidecar(tmp_path, monkeypatch):
    # Regression: editing a captioned region's text must be written back to the
    # region's .txt sidecar (it previously stayed as the original VLM output).
    _write_image(tmp_path / "image.png")
    events = []
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", _fake_runtime_class(events))

    caption_step.run(
        tmp_path,
        concept_token="tok",
        output_dir=tmp_path,
        caption_model_id="fake/model",
        interaction=_EditingProvider("tok, Green detail with a silver buckle"),
        spot_check_pct=0,
    )

    sidecar = tmp_path / "plk_bbox__image__01.txt"
    assert sidecar.read_text(encoding="utf-8") == "tok, Green detail with a silver buckle"


def test_caption_step_resume_skips_done_and_prompts_only_pending(tmp_path, monkeypatch):
    # First run: caption `done.png` (and its box); leave `new.png` for later.
    _write_image(tmp_path / "done.png")
    events = []
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", _fake_runtime_class(events))

    box = {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6, "label": "a red car",
           "crop_name": "plk_bbox__done__01.png"}
    first = _BatchProvider(lambda d: {"annotations": [dict(box)], "skipped": False})
    caption_step.run(
        tmp_path, concept_token="tok", output_dir=tmp_path,
        caption_model_id="fake/model", interaction=first, spot_check_pct=0,
    )
    assert (tmp_path / "plk_bbox__done__boxes.json").exists()
    assert (tmp_path / "done.txt").exists()

    # A new uncaptioned image appears; re-run WITHOUT force.
    _write_image(tmp_path / "new.png")
    events2 = []
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", _fake_runtime_class(events2))
    second = _BatchProvider(lambda d: {"annotations": [], "skipped": False})
    report = caption_step.run(
        tmp_path, concept_token="tok", output_dir=tmp_path,
        caption_model_id="fake/model", interaction=second, spot_check_pct=0,
    )

    # Resume: only the pending image is handed to the workspace; the done image and
    # its hand-drawn boxes are left untouched.
    assert {Path(d["path"]).name for d in second.seen} == {"new.png"}
    assert (tmp_path / "plk_bbox__done__boxes.json").exists()
    assert (tmp_path / "done.txt").read_text(encoding="utf-8") == "tok, Whole original caption"
    captioned = [e[1] for e in events2 if e[0] == "image"]
    assert captioned == ["new.png"]
    # The report still covers both images (done caption preserved + new one).
    assert report["captioned"] >= 2


def test_caption_step_force_prefills_boxes_and_never_deletes_them(tmp_path, monkeypatch):
    # First run captions the image and saves a reload sidecar.
    _write_image(tmp_path / "image.png")
    events = []
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", _fake_runtime_class(events))
    box = {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6, "label": "a red car",
           "crop_name": "plk_bbox__image__01.png"}
    first = _BatchProvider(lambda d: {"annotations": [dict(box)], "skipped": False})
    caption_step.run(
        tmp_path, concept_token="tok", output_dir=tmp_path,
        caption_model_id="fake/model", interaction=first, spot_check_pct=0,
    )
    assert (tmp_path / "plk_bbox__image__boxes.json").exists()

    # Force re-run: the image is re-presented with its boxes prefilled, and the
    # reload sidecar is never deleted.
    events2 = []
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", _fake_runtime_class(events2))
    second = _BatchProvider(lambda d: {"annotations": d["annotations"], "skipped": False})
    caption_step.run(
        tmp_path, concept_token="tok", output_dir=tmp_path,
        caption_model_id="fake/model", interaction=second, spot_check_pct=0,
        overwrite=True,
    )
    descriptor = next(d for d in second.seen if Path(d["path"]).name == "image.png")
    assert descriptor["annotations"][0]["label"] == "a red car"
    assert descriptor["annotations"][0]["x2"] == 0.5
    assert (tmp_path / "plk_bbox__image__boxes.json").exists()
    assert "image" in _event_names(events2)


def test_caption_step_resume_with_no_pending_skips_model_load(tmp_path, monkeypatch):
    # Caption everything once.
    _write_image(tmp_path / "image.png")
    events = []
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", _fake_runtime_class(events))
    caption_step.run(
        tmp_path, concept_token="tok", output_dir=tmp_path,
        caption_model_id="fake/model",
        interaction=_BatchProvider(lambda d: {"annotations": [], "skipped": False}),
        spot_check_pct=0,
    )
    assert (tmp_path / "image.txt").exists()

    # Re-run with nothing pending: the VLM is never loaded and no modal is opened,
    # but a valid report is still produced from the existing caption. FakeRuntime
    # emits a status only on load(), so an empty status log proves load() was skipped.
    events2 = []
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", _fake_runtime_class(events2))
    provider = _BatchProvider(lambda d: {"annotations": [], "skipped": False})
    statuses = []
    report = caption_step.run(
        tmp_path, concept_token="tok", output_dir=tmp_path,
        caption_model_id="fake/model", interaction=provider, spot_check_pct=0,
        caption_status_callback=statuses.append,
    )
    assert provider.seen == []              # no empty annotation modal
    assert statuses == []                   # load() never fired (no status emitted)
    assert "image" not in _event_names(events2)
    assert report["captioned"] >= 1


def test_caption_step_skip_all_captions_current_image_only(tmp_path, monkeypatch):
    _write_image(tmp_path / "a.png")
    _write_image(tmp_path / "b.png")
    events = []
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", _fake_runtime_class(events))

    # "Skip all remaining" keeps the active image (a) and skips the rest (b).
    def decide(descriptor):
        if Path(descriptor["path"]).name == "a.png":
            return {"annotations": [], "skipped": False}
        return {"annotations": [], "skipped": True}

    provider = _BatchProvider(decide)
    provider.skip_all = True
    caption_step.run(
        tmp_path, concept_token="tok", output_dir=tmp_path,
        caption_model_id="fake/model", interaction=provider, spot_check_pct=0,
    )

    assert (tmp_path / "a.txt").exists()
    assert not (tmp_path / "b.txt").exists()
    captioned = [e for e in events if e[0] == "image"]
    assert [e[1] for e in captioned] == ["a.png"]


def test_caption_step_requires_model_when_captioning_enabled(tmp_path):
    _write_image(tmp_path / "image.png")

    with pytest.raises(RuntimeError, match="requires caption_model_id"):
        caption_step.run(
            tmp_path,
            concept_token="tok",
            output_dir=tmp_path,
            interaction=_SkippingProvider(),
            spot_check_pct=0,
        )


def test_caption_step_full_image_failure_is_loud_and_does_not_write_sidecar(tmp_path, monkeypatch):
    _write_image(tmp_path / "image.png")
    events = []
    runtime = _fake_runtime_class(
        events,
        image_error=RuntimeError("model crashed"),
        status={"phase": "failed", "message": "model crashed"},
    )
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", runtime)

    with pytest.raises(RuntimeError, match="VL captioning failed for image.png: model crashed"):
        caption_step.run(
            tmp_path,
            concept_token="tok",
            output_dir=tmp_path,
            caption_model_id="fake/model",
            interaction=_SkippingProvider(),
            spot_check_pct=0,
            report_path=tmp_path / "report.json",
        )

    assert _event_names(events) == ["init", "unload"]
    assert not (tmp_path / "image.txt").exists()
    assert (tmp_path / "report.json").exists()


def test_caption_step_unloads_runtime_when_cancelled_during_caption(tmp_path, monkeypatch):
    _write_image(tmp_path / "image.png")
    events = []
    runtime = _fake_runtime_class(
        events,
        image_error=CancelledRun("Run cancelled"),
        status={"phase": "captioning"},
    )
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", runtime)

    with pytest.raises(CancelledRun):
        caption_step.run(
            tmp_path,
            concept_token="tok",
            output_dir=tmp_path,
            caption_model_id="fake/model",
            interaction=_SkippingProvider(),
            spot_check_pct=0,
        )

    assert _event_names(events) == ["init", "unload"]
    assert not (tmp_path / "image.txt").exists()
