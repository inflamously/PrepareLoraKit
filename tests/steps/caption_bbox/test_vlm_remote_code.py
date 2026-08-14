"""The caption loader must not execute Hub-authored code unless told to.

``transformers`` is faked through ``sys.modules`` so these run on a bare
interpreter: the loader chain imports it lazily inside the function, which is
exactly the seam a fake module needs.
"""
import sys
import types

import pytest

from prepare_lora_kit import settings
from prepare_lora_kit.steps.caption_bbox import vlm


class _RecordingLoader:
    """Stands in for an Auto* class, recording the kwargs it was loaded with."""

    def __init__(self, raises=None):
        self._raises = raises
        self.kwargs = None

    def from_pretrained(self, model_id, **kwargs):
        self.kwargs = kwargs
        if self._raises is not None:
            raise self._raises
        return types.SimpleNamespace(name_or_path=model_id)


def _fake_transformers(monkeypatch, **classes):
    module = types.ModuleType("transformers")
    for name, obj in classes.items():
        setattr(module, name, obj)
    monkeypatch.setitem(sys.modules, "transformers", module)
    return module


def _allow_remote_code(value):
    settings.save_settings_dict({"huggingface": {"allow_remote_code": value}})
    settings.invalidate()


def test_prompted_model_load_denies_remote_code_by_default(monkeypatch):
    loader = _RecordingLoader()
    _fake_transformers(monkeypatch, AutoModelForImageTextToText=loader)

    vlm._load_prompted_model("some/model", {})

    assert loader.kwargs["trust_remote_code"] is False


def test_image_to_text_model_load_denies_remote_code_by_default(monkeypatch):
    loader = _RecordingLoader()
    _fake_transformers(monkeypatch, AutoModelForImageTextToText=loader)

    vlm._load_image_to_text_model("some/model", {})

    assert loader.kwargs["trust_remote_code"] is False


def test_processor_load_denies_remote_code_by_default(monkeypatch):
    loader = _RecordingLoader()
    _fake_transformers(monkeypatch, AutoProcessor=loader)

    vlm._load_processor("some/model")

    assert loader.kwargs["trust_remote_code"] is False


def test_opt_in_reaches_the_loader(monkeypatch):
    _allow_remote_code(True)
    loader = _RecordingLoader()
    _fake_transformers(monkeypatch, AutoModelForImageTextToText=loader)

    vlm._load_prompted_model("some/model", {})

    assert loader.kwargs["trust_remote_code"] is True


def test_remote_code_refusal_is_not_buried_in_the_adapter_chain(monkeypatch):
    # Without this, the real cause ends up joined into "Could not load caption
    # model ... with supported Hugging Face adapters" and the user is told the
    # model is broken rather than that they must opt in.
    refusal = ValueError(
        "The repository some/model contains custom code which must be executed to "
        "correctly load the model. Please pass the argument `trust_remote_code=True`."
    )
    second = _RecordingLoader()
    _fake_transformers(
        monkeypatch,
        AutoModelForImageTextToText=_RecordingLoader(raises=refusal),
        Qwen2VLForConditionalGeneration=second,
    )

    with pytest.raises(RuntimeError, match="allow_remote_code"):
        vlm._load_prompted_model("some/model", {})

    # It stops at the refusal instead of walking on to the next class.
    assert second.kwargs is None
