"""On-the-fly downscaled image variants for the UI media server.

The desktop UI never needs full-resolution pixels just to *display* an image: grids and
thumbnail strips show tiny previews, and detail/canvas panes are viewport-bounded. Serving the
original 3042x4096 bytes for those forces the browser to download and decode megabytes per image,
which is what makes the caption workspace sluggish.

`render_variant` returns a small WEBP encoding of an image, downscaled so its longest side is at
most ``width``. Results are memoized in a bounded, thread-safe LRU keyed by the file's
modification time, so a re-run that overwrites an image invalidates its cached variants
automatically. The media server is threaded, hence the lock.
"""
from __future__ import annotations

from collections import OrderedDict
from io import BytesIO
from pathlib import Path
import threading

# Encoded variants are tiny (a few KB for thumbnails, ~tens-hundreds KB for views), so a few
# hundred entries comfortably covers a large dataset shown across the UI without unbounded growth.
_CACHE_LIMIT = 512

_CACHE: "OrderedDict[tuple[str, int, int], tuple[bytes, str]]" = OrderedDict()
_LOCK = threading.Lock()

_WEBP_QUALITY = 82


def _encode(path: Path, width: int) -> tuple[bytes, str]:
    from PIL import Image

    with Image.open(path) as img:
        # WEBP cannot encode palette ("P") or "LA" modes directly; normalize to RGB(A) and keep
        # alpha when present so PNG transparency survives the downscale.
        if img.mode in ("P", "LA", "RGBA"):
            img = img.convert("RGBA")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((width, width), Image.LANCZOS)
        buffer = BytesIO()
        try:
            img.save(buffer, format="WEBP", quality=_WEBP_QUALITY, method=4)
            content_type = "image/webp"
        except Exception:
            # Pillow builds without WEBP support fall back to JPEG (no alpha).
            if img.mode != "RGB":
                img = img.convert("RGB")
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=_WEBP_QUALITY)
            content_type = "image/jpeg"
    return buffer.getvalue(), content_type


def render_variant(path: Path, width: int) -> tuple[bytes, str]:
    """Return ``(encoded_bytes, content_type)`` for a downscaled variant of ``path``.

    ``width`` bounds the longest side (aspect ratio preserved). Results are cached per
    ``(path, mtime_ns, width)``; the cache self-invalidates when the file is rewritten.
    """
    resolved = path.resolve()
    mtime_ns = resolved.stat().st_mtime_ns
    key = (str(resolved), mtime_ns, int(width))

    with _LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            _CACHE.move_to_end(key)
            return cached

    # Encode outside the lock so concurrent requests for different images don't serialize.
    result = _encode(resolved, int(width))

    with _LOCK:
        _CACHE[key] = result
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_LIMIT:
            _CACHE.popitem(last=False)
    return result


def clear_cache() -> None:
    """Drop all cached variants (used by tests)."""
    with _LOCK:
        _CACHE.clear()
