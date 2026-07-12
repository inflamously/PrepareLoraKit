import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.steps.quality_gate import step
from prepare_lora_kit.utils import image as image_utils


def test_unload_watermark_model_releases_cached_cuda_model(monkeypatch):
    empty_cache = Mock()
    fake_torch = SimpleNamespace(cuda=SimpleNamespace(empty_cache=empty_cache))
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr(image_utils, "_clip_model", object())
    monkeypatch.setattr(image_utils, "_clip_processor", object())
    monkeypatch.setattr(image_utils, "_clip_device", "cuda")

    image_utils.unload_watermark_model()

    assert image_utils._clip_model is None
    assert image_utils._clip_processor is None
    assert image_utils._clip_device is None
    empty_cache.assert_called_once_with()


def test_quality_gate_releases_watermark_model_after_scoring(tmp_path, monkeypatch):
    image = tmp_path / "image.png"
    cleanup = Mock()
    monkeypatch.setattr(step.img_utils, "iter_images", lambda _path: [image])
    monkeypatch.setattr(step.img_utils, "ImageData", lambda path: path)
    monkeypatch.setattr(step.img_utils, "materialize", Mock())
    monkeypatch.setattr(step.img_utils, "unload_watermark_model", cleanup)
    monkeypatch.setattr(
        step,
        "_score_image",
        lambda *_args: {
            "auto_reject": False,
            "auto_reasons": [],
            "scores": {},
            "quality": 100.0,
        },
    )

    step.run(tmp_path, tmp_path, auto_only=True)

    cleanup.assert_called_once_with()


def test_quality_gate_releases_watermark_model_when_cancelled(tmp_path, monkeypatch):
    image = tmp_path / "image.png"
    cleanup = Mock()
    monkeypatch.setattr(step.img_utils, "iter_images", lambda _path: [image])
    monkeypatch.setattr(step.img_utils, "unload_watermark_model", cleanup)

    def cancel():
        raise CancelledRun("stop")

    with pytest.raises(CancelledRun, match="stop"):
        step.run(tmp_path, tmp_path, auto_only=True, cancel_check=cancel)

    cleanup.assert_called_once_with()
