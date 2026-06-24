from pathlib import Path

from PIL import Image
import pytest

from prepare_lora_kit.cancellation import CancelledRun
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


class _SkippingProvider:
    def annotate_image(self, path, *, captioner=None):
        return [], True, False


def test_caption_step_reuses_runtime_for_region_and_original_caption(tmp_path, monkeypatch):
    image_path = tmp_path / "image.png"
    Image.new("RGB", (16, 12), "blue").save(image_path)
    events = []

    class FakeRuntime:
        def __init__(self, model_id, *, quantization, dtype, max_pixels):
            events.append(("init", model_id, quantization, dtype, max_pixels))

        def caption_region(self, crop):
            events.append(("region", crop.size))
            return "green detail"

        def caption_image(self, path, annotations, concept_token, *, max_new_tokens):
            events.append(("image", Path(path).name, annotations[0]["crop_name"], concept_token, max_new_tokens))
            return "whole original caption"

        def unload(self):
            events.append(("unload",))

    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", FakeRuntime)
    provider = _AnnotatingProvider()

    report = caption_step.run(
        tmp_path,
        concept_token="tok",
        output_dir=tmp_path,
        qwen_model_id="fake/model",
        interaction=provider,
        spot_check_pct=0,
    )

    assert report["captioned"] == 2
    assert [event[0] for event in events] == ["init", "region", "image", "unload"]
    assert (tmp_path / "image.txt").read_text(encoding="utf-8") == "tok, Whole original caption"
    assert (tmp_path / "plk_bbox__image__01.txt").read_text(encoding="utf-8") == "tok, Green detail"


def test_caption_step_full_image_failure_is_loud_and_does_not_write_sidecar(tmp_path, monkeypatch):
    image_path = tmp_path / "image.png"
    Image.new("RGB", (16, 12), "blue").save(image_path)
    events = []

    class FailingRuntime:
        def __init__(self, *args, **kwargs):
            events.append("init")

        def caption_image(self, path, annotations, concept_token, *, max_new_tokens):
            raise RuntimeError("model crashed")

        def unload(self):
            events.append("unload")

    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", FailingRuntime)

    with pytest.raises(RuntimeError, match="VL captioning failed for image.png: model crashed"):
        caption_step.run(
            tmp_path,
            concept_token="tok",
            output_dir=tmp_path,
            interaction=_SkippingProvider(),
            spot_check_pct=0,
        )

    assert events == ["init", "unload"]
    assert not (tmp_path / "image.txt").exists()


def test_caption_step_unloads_runtime_when_cancelled_during_caption(tmp_path, monkeypatch):
    image_path = tmp_path / "image.png"
    Image.new("RGB", (16, 12), "blue").save(image_path)
    events = []

    class CancellingRuntime:
        def __init__(self, *args, **kwargs):
            events.append("init")

        def caption_image(self, path, annotations, concept_token, *, max_new_tokens):
            raise CancelledRun("Run cancelled")

        def unload(self):
            events.append("unload")

    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", CancellingRuntime)

    with pytest.raises(CancelledRun):
        caption_step.run(
            tmp_path,
            concept_token="tok",
            output_dir=tmp_path,
            interaction=_SkippingProvider(),
            spot_check_pct=0,
        )

    assert events == ["init", "unload"]
    assert not (tmp_path / "image.txt").exists()
