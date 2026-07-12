import sys
from types import SimpleNamespace
from unittest.mock import Mock

from prepare_lora_kit.utils import accelerator


def test_release_accelerator_memory_does_not_import_torch(monkeypatch):
    collect = Mock()
    monkeypatch.delitem(sys.modules, "torch", raising=False)
    monkeypatch.setattr(accelerator.gc, "collect", collect)

    accelerator.release_accelerator_memory()

    collect.assert_not_called()


def test_release_accelerator_memory_collects_before_emptying_cuda(monkeypatch):
    calls = []
    cuda = SimpleNamespace(
        is_initialized=lambda: True,
        synchronize=lambda: calls.append("synchronize"),
        empty_cache=lambda: calls.append("empty_cache"),
    )
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda))
    monkeypatch.setattr(accelerator.gc, "collect", lambda: calls.append("collect"))

    accelerator.release_accelerator_memory()

    assert calls == ["synchronize", "collect", "empty_cache"]
