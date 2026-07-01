"""Tests for the UI media-variant renderer and its cache."""
from io import BytesIO

from PIL import Image

from prepare_lora_kit.ui import media


def _write_image(path, size, color="red", mode="RGB"):
    Image.new(mode, size, color).save(path)


def test_render_variant_downscales_to_width(tmp_path):
    media.clear_cache()
    image = tmp_path / "big.png"
    _write_image(image, (3000, 2000))

    body, content_type = media.render_variant(image, 128)

    assert content_type in ("image/webp", "image/jpeg")
    with Image.open(BytesIO(body)) as decoded:
        # Longest side is capped; aspect ratio (3:2) is preserved.
        assert max(decoded.size) <= 128
        assert decoded.size == (128, 85)
    # The variant is much smaller than the original file.
    assert len(body) < image.stat().st_size


def test_render_variant_never_upscales_small_images(tmp_path):
    media.clear_cache()
    image = tmp_path / "small.png"
    _write_image(image, (40, 30))

    body, _ = media.render_variant(image, 512)

    with Image.open(BytesIO(body)) as decoded:
        assert decoded.size == (40, 30)


def test_render_variant_caches_by_mtime(tmp_path):
    media.clear_cache()
    image = tmp_path / "img.png"
    _write_image(image, (800, 600), color="red")

    first = media.render_variant(image, 100)
    # A repeat request returns the very same cached object.
    assert media.render_variant(image, 100) is first

    # Rewriting the file (new mtime + content) invalidates the cache.
    _write_image(image, (800, 600), color="blue")
    second = media.render_variant(image, 100)
    assert second is not first
    assert second[0] != first[0]


def test_render_variant_handles_palette_and_alpha(tmp_path):
    media.clear_cache()
    palette = tmp_path / "palette.png"
    _write_image(palette, (200, 200), color=5, mode="P")
    rgba = tmp_path / "alpha.png"
    Image.new("RGBA", (200, 200), (0, 128, 255, 128)).save(rgba)

    for path in (palette, rgba):
        body, content_type = media.render_variant(path, 64)
        assert body
        with Image.open(BytesIO(body)) as decoded:
            assert max(decoded.size) <= 64
