"""Windows-specific process-exit workarounds for the pywebview runtime."""
from __future__ import annotations

import atexit
import sys


def suppress_netfx_process_finalizer() -> bool:
    """Skip clr-loader's slow final process-wide CLR finalizer on Windows.

    Python.NET registers its own earlier ``unload`` callback, which performs a
    full Python.NET shutdown and closes the application domain. clr-loader then
    registers an additional process finalizer that calls ``pyclr_finalize``;
    with pywebview's WinForms backend that call can stall for about 15 seconds.

    This helper is called only after the WebView2 window has been disposed and
    the app has confirmed that no pipeline thread remains alive. The hosted CLR
    itself is then reclaimed normally by Windows as the process exits.
    """
    if sys.platform != "win32":
        return False

    try:
        from clr_loader import netfx
    except ImportError:
        return False

    release = getattr(netfx, "_release", None)
    if release is None or getattr(netfx, "_FW", None) is None:
        return False

    atexit.unregister(release)
    return True
