import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageCms, ImageOps

from haybale_image.io.codecs import EncodeOptions, encode_image, read_image
from haybale_image.io.formats import DEPTHS, Format, best_depth, format_for
from haybale_image.value import ImageMetadata, ImageValue, Layout, convert_layout

pytestmark = pytest.mark.unit

_EXT = {
    Format.PNG: ".png",
    Format.JPEG: ".jpg",
    Format.WEBP: ".webp",
    Format.TIFF: ".tiff",
    Format.BMP: ".bmp",
    Format.GIF: ".gif",
    Format.TGA: ".tga",
    Format.AVIF: ".avif",
}
_LOSSY = {Format.JPEG, Format.WEBP, Format.AVIF}
_NO_ALPHA = {Format.JPEG, Format.BMP, Format.GIF}


def _gradient(layout: Layout, depth: int, *, banded: bool = False) -> ImageValue:
    """A smooth 32×48 test image; ``banded`` limits it to 128 colours for GIF's palette."""
    h, w = 32, 48
    x = np.tile(np.linspace(0, 1, w), (h, 1))
    y = np.tile(np.linspace(0, 1, h)[:, None], (1, w))
    if banded:
        x, y = np.round(x * 15) / 15, np.round(y * 7) / 7
    if layout is Layout.GRAY:
        f = x
    else:
        chans = [x, y, 1 - x]
        if layout is Layout.RGBA:
            chans.append(0.5 + 0.5 * y)
        f = np.stack(chans, axis=-1)
    dtype = {8: np.uint8, 16: np.uint16, 32: np.float32}[depth]
    src = ImageValue.from_array(f.astype(np.float32), source_depth=depth)
    return ImageValue.from_array(src.array(dtype), source_depth=depth)


def _expected_layout(fmt: Format, layout: Layout) -> Layout:
    if fmt in (Format.WEBP, Format.GIF) and layout is Layout.GRAY:
        return Layout.RGB  # WebP has no gray mode; GIF reads back as a palette
    if fmt in _NO_ALPHA and layout is Layout.RGBA:
        return Layout.RGB
    return layout


def _write(tmp_path: Path, img: ImageValue, fmt: Format, name: str = "img", **opts) -> Path:
    path = tmp_path / f"{name}{_EXT[fmt]}"
    path.write_bytes(encode_image(img, fmt, EncodeOptions(**opts)))
    return path


_CASES = [(fmt, layout, depth) for fmt, depths in DEPTHS.items() for layout in Layout for depth in depths]


@pytest.mark.parametrize(("fmt", "layout", "depth"), _CASES, ids=[f"{f}-{la}-{d}" for f, la, d in _CASES])
def test_round_trip(tmp_path, fmt, layout, depth):
    src = _gradient(layout, depth, banded=fmt is Format.GIF)
    loaded = read_image(_write(tmp_path, src, fmt))
    assert loaded.layout is _expected_layout(fmt, layout)
    assert loaded.source_depth == depth
    assert (loaded.height, loaded.width) == (src.height, src.width)
    want = convert_layout(src, loaded.layout).array(np.float32)
    got = loaded.array(np.float32)
    if fmt in _LOSSY:
        assert np.abs(got - want).mean() <= 3 / 255
    else:
        dtype = {8: np.uint8, 16: np.uint16, 32: np.float32}[depth]
        np.testing.assert_array_equal(loaded.array(dtype), convert_layout(src, loaded.layout).array(dtype))


def test_extension_aliases():
    assert format_for(Path("a.JPG")) is Format.JPEG
    assert format_for(Path("a.jpeg")) is Format.JPEG
    assert format_for(Path("a.jpe")) is Format.JPEG
    assert format_for(Path("a.TIF")) is Format.TIFF
    assert format_for(Path("dir.x/a.png")) is Format.PNG


def test_unknown_extension_raises():
    with pytest.raises(ValueError, match=r"unsupported extension '\.xyz'; use \.png, \.jpg"):
        format_for(Path("a.xyz"))


def test_no_extension_raises():
    with pytest.raises(ValueError, match="has no extension"):
        format_for(Path("folder/image"))


def test_best_depth():
    assert best_depth(Format.PNG, 32) == 16
    assert best_depth(Format.JPEG, 16) == 8
    assert best_depth(Format.TIFF, 32) == 32
    assert best_depth(Format.PNG, 8) == 8


def test_depth_option_overrides_source(tmp_path):
    src = _gradient(Layout.RGB, 8)
    loaded = read_image(_write(tmp_path, src, Format.PNG, depth=16))
    assert loaded.source_depth == 16
    np.testing.assert_array_equal(loaded.array(np.uint8), src.array(np.uint8))


def test_unicode_path_round_trip(tmp_path):
    src = _gradient(Layout.RGB, 8)
    path = tmp_path / "Größe 1.png"
    path.write_bytes(encode_image(src, Format.PNG, EncodeOptions()))
    np.testing.assert_array_equal(read_image(path).array(np.uint8), src.array(np.uint8))


def test_corrupt_file_raises(tmp_path):
    good = encode_image(_gradient(Layout.RGB, 8), Format.PNG, EncodeOptions())
    truncated = tmp_path / "truncated.png"
    truncated.write_bytes(good[: len(good) // 2])
    with pytest.raises(ValueError, match=r"cannot read image truncated\.png"):
        read_image(truncated)
    text = tmp_path / "notes.png"
    text.write_text("not an image")
    with pytest.raises(ValueError, match=r"cannot read image notes\.png"):
        read_image(text)


def test_palette_with_transparency_is_rgba(tmp_path):
    im = Image.new("P", (4, 4), 0)
    im.putpalette([255, 0, 0, 0, 255, 0] + [0] * 762)
    im.putpixel((0, 0), 1)
    path = tmp_path / "pal.png"
    im.save(path, transparency=0)
    img = read_image(path)
    assert img.layout is Layout.RGBA
    assert tuple(img.array(np.uint8)[0, 0]) == (0, 255, 0, 255)
    assert img.array(np.uint8)[1, 1, 3] == 0


def test_cmyk_jpeg_is_rgb(tmp_path):
    path = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (4, 4), (0, 255, 255, 0)).save(path, quality=100)
    img = read_image(path)
    assert img.layout is Layout.RGB
    r, g, b = img.array(np.uint8)[0, 0].astype(int)
    assert r > 200
    assert g < 60
    assert b < 60


def test_gray16_png(tmp_path):
    data = np.arange(12, dtype=np.uint16).reshape(3, 4) * 5000
    path = tmp_path / "g16.png"
    Image.fromarray(data).save(path)
    img = read_image(path)
    assert img.layout is Layout.GRAY
    assert img.source_depth == 16
    np.testing.assert_array_equal(img.array(np.uint16), data)


def test_gif_first_frame(tmp_path):
    frames = [Image.new("RGB", (4, 4), c) for c in ((255, 0, 0), (0, 0, 255))]
    path = tmp_path / "anim.gif"
    frames[0].save(path, save_all=True, append_images=frames[1:])
    img = read_image(path)
    assert img.layout is Layout.RGB
    assert tuple(img.array(np.uint8)[0, 0]) == (255, 0, 0)


def test_tga_round_trip(tmp_path):
    src = _gradient(Layout.RGBA, 8)
    path = _write(tmp_path, src, Format.TGA)
    assert Image.open(path).format == "TGA"
    np.testing.assert_array_equal(read_image(path).array(np.uint8), src.array(np.uint8))


def _jpeg_with_orientation(path: Path, orientation: int) -> np.ndarray:
    a = np.zeros((2, 3, 3), np.uint8)
    a[0, 0] = (255, 0, 0)
    a[0, 2] = (0, 255, 0)
    a[1, 0] = (0, 0, 255)
    im = Image.fromarray(a)
    exif = im.getexif()
    exif[0x0112] = orientation
    im.save(path, quality=100, subsampling=0, exif=exif)
    return np.asarray(ImageOps.exif_transpose(Image.open(path)))


def test_exif_orientation_applied(tmp_path):
    path = tmp_path / "rot.jpg"
    _jpeg_with_orientation(path, 6)
    img = read_image(path)
    assert (img.height, img.width) == (3, 2)
    assert img.metadata.exif is not None
    exif = Image.Exif()
    exif.load(img.metadata.exif)
    assert exif[0x0112] == 1


@pytest.mark.parametrize("orientation", range(1, 9))
def test_exif_orientation_matches_pillow(tmp_path, orientation):
    path = tmp_path / f"o{orientation}.jpg"
    want = _jpeg_with_orientation(path, orientation)
    got = read_image(path).array(np.uint8).astype(int)
    assert got.shape == want.shape
    assert np.abs(got - want.astype(int)).max() < 40


def test_no_exif_carries_none(tmp_path):
    path = _write(tmp_path, _gradient(Layout.RGB, 8), Format.JPEG)
    assert read_image(path).metadata.exif is None


@pytest.fixture
def srgb_icc() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


@pytest.mark.parametrize("fmt", [Format.PNG, Format.JPEG, Format.WEBP, Format.TIFF])
def test_icc_passthrough(tmp_path, srgb_icc, fmt):
    src = _gradient(Layout.RGB, 8).with_metadata(ImageMetadata(icc=srgb_icc))
    path = _write(tmp_path, src, fmt)
    assert Image.open(path).info.get("icc_profile") == srgb_icc
    assert read_image(path).metadata.icc == srgb_icc


def test_exif_passthrough_jpeg(tmp_path):
    exif = Image.Exif()
    exif[0x010F] = "Haywire"  # Make
    src = _gradient(Layout.RGB, 8).with_metadata(ImageMetadata(exif=exif.tobytes()))
    path = _write(tmp_path, src, Format.JPEG)
    assert Image.open(path).getexif()[0x010F] == "Haywire"


def test_png_header_read_does_not_decode(tmp_path, srgb_icc, monkeypatch):
    from PIL import ImageFile

    src = _gradient(Layout.RGB, 8).with_metadata(ImageMetadata(icc=srgb_icc))
    path = _write(tmp_path, src, Format.PNG)
    assert Image.open(path).info.get("icc_profile") == srgb_icc
    loads = []
    real = ImageFile.ImageFile.load

    def fake(self):
        loads.append(1)
        return real(self)

    monkeypatch.setattr(ImageFile.ImageFile, "load", fake)
    loaded = read_image(path)
    assert loads == []
    assert loaded.metadata.icc == srgb_icc


def test_png_exif_passthrough(tmp_path):
    exif = Image.Exif()
    exif[0x010F] = "Haywire"
    path = tmp_path / "e.png"
    Image.fromarray(np.zeros((4, 6, 3), np.uint8)).save(path, exif=exif)
    carried = read_image(path).metadata.exif
    assert carried is not None
    e = Image.Exif()
    e.load(carried)
    assert e[0x010F] == "Haywire"


def test_sixteen_bit_drops_metadata(tmp_path, srgb_icc):
    src = _gradient(Layout.RGB, 16).with_metadata(ImageMetadata(icc=srgb_icc))
    loaded = read_image(_write(tmp_path, src, Format.PNG))
    assert loaded.source_depth == 16
    assert loaded.metadata.icc is None


def test_encode_options_reach_the_codec():
    src = _gradient(Layout.RGB, 8)
    low = encode_image(src, Format.JPEG, EncodeOptions(jpeg_quality=10))
    high = encode_image(src, Format.JPEG, EncodeOptions(jpeg_quality=100))
    assert len(low) < len(high)
    none = encode_image(src, Format.TIFF, EncodeOptions(tiff_compression="none"))
    lzw = encode_image(src, Format.TIFF, EncodeOptions(tiff_compression="lzw"))
    deflate = encode_image(src, Format.TIFF, EncodeOptions(tiff_compression="deflate"))
    assert len(lzw) < len(none)
    assert len(deflate) < len(none)
    lossless = read_image_bytes(encode_image(src, Format.WEBP, EncodeOptions(webp_lossless=True)))
    np.testing.assert_array_equal(lossless, src.array(np.uint8))


def test_unknown_tiff_compression_raises():
    with pytest.raises(ValueError, match="tiff_compression"):
        encode_image(_gradient(Layout.RGB, 8), Format.TIFF, EncodeOptions(tiff_compression="zip"))


def read_image_bytes(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))


def test_huge_png_header_falls_back_to_cv2(tmp_path, monkeypatch):
    path = _write(tmp_path, _gradient(Layout.RGB, 8), Format.PNG)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    with pytest.raises(Image.DecompressionBombError):
        Image.open(path)
    loaded = read_image(path)
    assert loaded.array(np.uint8).size > 0
    assert loaded.metadata == ImageMetadata()


def test_huge_gif_names_the_file(tmp_path, monkeypatch):
    path = tmp_path / "huge.gif"
    Image.new("P", (10, 10)).save(path)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    with pytest.raises(ValueError, match="huge.gif"):
        read_image(path)
