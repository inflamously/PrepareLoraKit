import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from prepare_lora_kit.invoke.vae_gate_step import invoke_vae_gate_step
from prepare_lora_kit.pipeline.configs import VaeGateConfig
from prepare_lora_kit.steps.vae_gate import step as vae_step
from prepare_lora_kit.steps.vae_gate.hf_loss import _hf_loss
from prepare_lora_kit.steps.vae_gate.vae import _encode_decode


def _image(path, color):
    Image.new("RGB", (24, 16), color).save(path)


def _patch_lightweight_runtime(monkeypatch, scores, *, fail_name=None):
    encode_calls = []
    artifact_calls = []
    score_iter = iter(scores)

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(cuda=SimpleNamespace(empty_cache=lambda: None)),
    )
    monkeypatch.setattr(vae_step, "_load_vae", lambda *_args: (object(), "cpu", "float32"))

    def fake_encode(_vae, _device, _dtype, path, *, max_side, seed):
        encode_calls.append((path.name, max_side, seed))
        if path.name == fail_name:
            raise RuntimeError("synthetic reconstruction failure")
        return np.zeros((16, 24, 3), dtype=np.uint8)

    def fake_artifacts(path, _recon, _root, **kwargs):
        artifact_calls.append((path.name, kwargs))
        return {
            "width": 24,
            "height": 16,
            "diff_threshold": 3.0,
            "views": {name: str(path) for name in ("original", "vae", "diff", "hard")},
        }

    monkeypatch.setattr(vae_step, "_encode_decode", fake_encode)
    monkeypatch.setattr(vae_step, "_to_lab_l", lambda image: image[:, :, 0].astype(np.float32))
    monkeypatch.setattr(vae_step, "_hf_loss", lambda *_args, **_kwargs: next(score_iter))
    monkeypatch.setattr(vae_step, "_save_review_artifacts", fake_artifacts)
    return encode_calls, artifact_calls


def test_run_uses_effective_seed_cutoff_and_strict_threshold(tmp_path, monkeypatch):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    _image(first, "red")
    _image(second, "blue")
    encode_calls, artifact_calls = _patch_lightweight_runtime(monkeypatch, [0.25, 0.25])
    cutoffs = []
    monkeypatch.setattr(
        vae_step,
        "_hf_loss",
        lambda *_args, cutoff_fraction: cutoffs.append(cutoff_fraction) or 0.25,
    )

    class Interaction:
        def vae_review(self, items):
            assert all(item["initial_decision"] == "keep" for item in items)
            return {}

    report = vae_step.run(
        tmp_path,
        "fake-vae",
        interaction=Interaction(),
        max_side=None,
        seed=99,
        hf_cutoff_fraction=0.33,
        output_previews=False,
        output_silhouettes=False,
        output_hard_silhouettes=False,
    )

    assert encode_calls == [("first.png", None, 99), ("second.png", None, 99)]
    assert cutoffs == [0.33, 0.33]
    assert report["threshold"] == 0.25
    assert report["flagged"] == []
    assert report["statistics"]["comparison"] == ">"
    assert all(call[1]["output_preview"] for call in artifact_calls)
    assert all(set(item["views"]) == {"original"} for item in report["review_items"])


def test_failed_images_are_kept_and_explicit_drop_removes_caption(tmp_path, monkeypatch):
    paths = [tmp_path / name for name in ("a.png", "b.png", "c.png")]
    for index, path in enumerate(paths):
        _image(path, (index * 50, 20, 30))
        path.with_suffix(".txt").write_text(f"caption {index}", encoding="utf-8")
    _patch_lightweight_runtime(monkeypatch, [0.0, 1.0], fail_name="b.png")

    class Interaction:
        def vae_review(self, items):
            assert [item["name"] for item in items] == ["a.png", "c.png"]
            assert next(item for item in items if item["name"] == "c.png")["flagged"] is True
            assert all(item["initial_decision"] == "keep" for item in items)
            return {str(paths[0]): "replace", str(paths[2]): "drop"}

    report = vae_step.run(
        tmp_path,
        "fake-vae",
        interaction=Interaction(),
        outlier_sigma=0.0,
    )

    assert paths[0].exists()  # invalid legacy decision is normalized to Keep
    assert paths[0].with_suffix(".txt").exists()
    assert paths[1].exists()  # reconstruction failure is kept unassessed
    assert paths[1].with_suffix(".txt").exists()
    assert not paths[2].exists()
    assert not paths[2].with_suffix(".txt").exists()
    assert report["statistics"]["successful"] == 2
    assert report["statistics"]["failed"] == 1
    assert report["failures"][0]["path"] == str(paths[1])
    assert report["flagged"] == [
        {"path": str(paths[2]), "hf_loss": 1.0, "decision": "drop"}
    ]
    assert "needs_replacement" not in report


def test_vae_load_failure_replaces_stale_previews_and_writes_report(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    report_path = tmp_path / "reports" / "VaeGateStep_report.json"
    preview_root = report_path.parent / "VaeGateStep_previews"
    dataset.mkdir()
    preview_root.mkdir(parents=True)
    _image(dataset / "image.png", "red")
    (preview_root / "stale.txt").write_text("stale", encoding="utf-8")
    monkeypatch.setattr(vae_step, "_load_vae", lambda *_args: (_ for _ in ()).throw(RuntimeError("bad model")))

    report = vae_step.run(dataset, "bad-vae", report_path=report_path)

    assert not preview_root.exists()
    assert (dataset / "image.png").exists()
    assert report["skipped"] is True
    assert report["statistics"]["failed"] == 1
    assert json.loads(report_path.read_text(encoding="utf-8"))["failures"][0]["stage"] == "load"


def test_invoker_forwards_cutoff_and_seed(tmp_path, monkeypatch):
    working = tmp_path / "dataset"
    working.mkdir()
    calls = {}

    def fake_run(*args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return {"ok": True}

    from prepare_lora_kit.steps import vae_gate

    monkeypatch.setattr(vae_gate, "run", fake_run)
    result = invoke_vae_gate_step(
        working,
        tmp_path,
        VaeGateConfig(hf_cutoff_fraction=0.31, seed=123),
    )

    assert result == {"ok": True}
    assert calls["kwargs"]["hf_cutoff_fraction"] == 0.31
    assert calls["kwargs"]["seed"] == 123


def test_hf_cutoff_changes_the_measured_frequency_band():
    x = np.arange(64, dtype=np.float32)
    low = np.sin(2 * np.pi * x / 16)
    high = 0.4 * np.sin(2 * np.pi * x / 4)
    original = np.tile(low + high, (64, 1)).astype(np.float32)
    reconstructed = np.tile(low, (64, 1)).astype(np.float32)

    narrow = _hf_loss(original, reconstructed, cutoff_fraction=0.05)
    wide = _hf_loss(original, reconstructed, cutoff_fraction=0.30)

    assert narrow != pytest.approx(wide)


def test_encode_decode_accepts_no_size_cap_and_uses_seed(tmp_path, monkeypatch):
    image_path = tmp_path / "tiny.png"
    Image.new("RGB", (13, 5), "red").save(image_path)
    observed = {}

    class FakeTensor:
        def unsqueeze(self, _dimension):
            return self

        def to(self, *_args, **_kwargs):
            return self

        def squeeze(self, _dimension):
            return self

        def cpu(self):
            return self

        def float(self):
            return self

        def clamp(self, *_args):
            return self

        def byte(self):
            return self

        def permute(self, *_dimensions):
            return self

        def numpy(self):
            return np.zeros((8, 8, 3), dtype=np.uint8)

        def __mul__(self, _value):
            return self

        def __sub__(self, _value):
            return self

        def __add__(self, _value):
            return self

        def __truediv__(self, _value):
            return self

    class FakeGenerator:
        def __init__(self, device):
            observed["device"] = device

        def manual_seed(self, seed):
            observed["seed"] = seed
            return self

    class NoGrad:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return False

    class FakeVae:
        def encode(self, _tensor):
            latent_dist = SimpleNamespace(
                sample=lambda generator: observed.update(generator=generator) or FakeTensor()
            )
            return SimpleNamespace(latent_dist=latent_dist)

        def decode(self, _latent):
            return SimpleNamespace(sample=FakeTensor())

    class ToTensor:
        def __call__(self, image):
            observed["resized"] = image.size
            return FakeTensor()

    fake_torch = SimpleNamespace(Generator=FakeGenerator, no_grad=lambda: NoGrad())
    fake_transforms = SimpleNamespace(ToTensor=ToTensor)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "torchvision", SimpleNamespace(transforms=fake_transforms))
    monkeypatch.setitem(sys.modules, "torchvision.transforms", fake_transforms)

    result = _encode_decode(
        FakeVae(), "cpu", "float32", image_path, max_side=None, seed=77
    )

    assert observed["resized"] == (8, 8)
    assert observed["device"] == "cpu"
    assert observed["seed"] == 77
    assert result.shape == (8, 8, 3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"diff_amplification": -1},
        {"gaussian_blur_sigma": -1},
        {"gaussian_blur_kernel": 0},
        {"outlier_sigma": -1},
        {"max_side": 7},
    ],
)
def test_config_rejects_invalid_runtime_values(kwargs):
    with pytest.raises(ValueError):
        VaeGateConfig(**kwargs)
