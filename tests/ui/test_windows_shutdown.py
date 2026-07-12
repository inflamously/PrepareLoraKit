import sys
from types import SimpleNamespace
from unittest.mock import Mock

from prepare_lora_kit_ui import windows_shutdown


def test_netfx_finalizer_is_suppressed_for_loaded_windows_runtime(monkeypatch):
    release = Mock()
    netfx = SimpleNamespace(_release=release, _FW=object())
    unregister = Mock()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "clr_loader", SimpleNamespace(netfx=netfx))
    monkeypatch.setattr(windows_shutdown.atexit, "unregister", unregister)

    assert windows_shutdown.suppress_netfx_process_finalizer() is True
    unregister.assert_called_once_with(release)


def test_netfx_finalizer_is_unchanged_outside_windows(monkeypatch):
    unregister = Mock()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(windows_shutdown.atexit, "unregister", unregister)

    assert windows_shutdown.suppress_netfx_process_finalizer() is False
    unregister.assert_not_called()


def test_netfx_finalizer_is_unchanged_when_runtime_is_not_loaded(monkeypatch):
    release = Mock()
    netfx = SimpleNamespace(_release=release, _FW=None)
    unregister = Mock()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "clr_loader", SimpleNamespace(netfx=netfx))
    monkeypatch.setattr(windows_shutdown.atexit, "unregister", unregister)

    assert windows_shutdown.suppress_netfx_process_finalizer() is False
    unregister.assert_not_called()
