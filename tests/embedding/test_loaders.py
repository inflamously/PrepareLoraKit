"""Tests for the Curate-step embedding loaders.

All ML-heavy work is mocked: the test interpreter has no ``torch`` or
``sentence_transformers``, so both are injected as fakes via ``sys.modules``.
Only the Qwen path (which goes through sentence-transformers) is exercised here;
the open_clip / DINOv2 paths call native model methods that aren't worth faking.
"""
import sys
import types

import numpy as np
import pytest
from PIL import Image

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.embedding import catalog, loaders


@pytest.fixture
def fake_torch(monkeypatch):
    """A ``torch`` stub whose CUDA is unavailable (so ``_device`` returns cpu)."""
    mod = types.ModuleType("torch")
    mod.cuda = types.SimpleNamespace(is_available=lambda: False)
    monkeypatch.setitem(sys.modules, "torch", mod)
    return mod


class _FakeSentenceTransformer:
    """Records construction + encode calls and returns deterministic vectors."""

    instances: list["_FakeSentenceTransformer"] = []

    def __init__(self, repo, device=None, trust_remote_code=None):
        self.repo = repo
        self.device = device
        self.trust_remote_code = trust_remote_code
        self.encode_calls: list[dict] = []
        _FakeSentenceTransformer.instances.append(self)

    def encode(self, chunk, normalize_embeddings=None, convert_to_numpy=None):
        self.encode_calls.append(
            {
                "chunk": list(chunk),
                "normalize_embeddings": normalize_embeddings,
                "convert_to_numpy": convert_to_numpy,
            }
        )
        return np.zeros((len(chunk), 4), dtype=np.float32)


@pytest.fixture
def fake_sentence_transformers(monkeypatch):
    _FakeSentenceTransformer.instances = []
    mod = types.ModuleType("sentence_transformers")
    mod.SentenceTransformer = _FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", mod)
    return mod


def _make_images(tmp_path, n):
    paths = []
    for i in range(n):
        p = tmp_path / f"img_{i}.png"
        Image.new("RGB", (8, 8), (i, i, i)).save(p)
        paths.append(p)
    return paths


def _qwen_spec():
    return catalog.get("Qwen/Qwen3-VL-Embedding-2B")


def test_embed_qwen_uses_sentence_transformers(tmp_path, fake_torch, fake_sentence_transformers):
    paths = _make_images(tmp_path, 3)

    emb = loaders._embed_qwen(_qwen_spec(), paths, None)

    assert isinstance(emb, np.ndarray)
    assert emb.shape == (3, 4)  # (N, D), stacked from the batch encode

    [st] = _FakeSentenceTransformer.instances
    assert st.repo == "Qwen/Qwen3-VL-Embedding-2B"
    assert st.device == "cpu"
    assert st.trust_remote_code is True

    # One batch (batch_size 8 > 3 images); encoded as PIL images, L2-normalized.
    assert len(st.encode_calls) == 1
    call = st.encode_calls[0]
    assert all(isinstance(im, Image.Image) for im in call["chunk"])
    assert call["normalize_embeddings"] is True


def test_embed_qwen_batches_large_inputs(tmp_path, fake_torch, fake_sentence_transformers):
    paths = _make_images(tmp_path, 10)

    emb = loaders._embed_qwen(_qwen_spec(), paths, None)

    assert emb.shape == (10, 4)
    [st] = _FakeSentenceTransformer.instances
    # batch_size is 8, so 10 images span two encode calls (8 + 2).
    assert [len(c["chunk"]) for c in st.encode_calls] == [8, 2]


def test_embed_images_dispatches_qwen_id_to_qwen_loader(tmp_path, monkeypatch):
    sentinel = np.ones((1, 2), dtype=np.float32)
    seen = {}

    def fake_embed_qwen(spec, paths, cancel_check):
        seen["spec"] = spec
        seen["paths"] = paths
        return sentinel

    monkeypatch.setattr(loaders, "_embed_qwen", fake_embed_qwen)

    out = loaders.embed_images("Qwen/Qwen3-VL-Embedding-2B", ["a", "b"])

    assert out is sentinel
    assert seen["spec"].family == "qwen"
    assert seen["paths"] == ["a", "b"]


def test_embed_qwen_missing_dependency_raises_actionable_error(tmp_path, fake_torch, monkeypatch):
    # sentence_transformers is genuinely absent in the test interpreter; force the
    # import to fail deterministically even if it ever gets installed.
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    paths = _make_images(tmp_path, 1)

    with pytest.raises(RuntimeError, match="sentence-transformers"):
        loaders._embed_qwen(_qwen_spec(), paths, None)


def test_embed_qwen_honors_cancellation(tmp_path, fake_torch, fake_sentence_transformers):
    paths = _make_images(tmp_path, 3)

    def cancel():
        raise CancelledRun("stop")

    with pytest.raises(CancelledRun):
        loaders._embed_qwen(_qwen_spec(), paths, cancel)

    # Cancellation trips before any image is encoded.
    assert _FakeSentenceTransformer.instances[0].encode_calls == []
