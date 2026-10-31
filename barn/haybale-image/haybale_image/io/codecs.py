"""Decode image files into ``ImageValue`` and encode ``ImageValue`` into file bytes.

OpenCV handles the pixels wherever it can (16-bit colour, float TIFF, speed);
Pillow reads every file's header for the ICC profile, EXIF block and orientation,
decodes what OpenCV cannot (GIF, TGA, palette, CMYK and similar modes) and writes
8-bit files that carry metadata. Metadata is dropped when writing above 8 bits.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from haybale_image.helpers import from_cv_bgr, from_pil, to_pil
from haybale_image.io.formats import HOLDS_METADATA, Format, best_depth
from haybale_image.value import NO_METADATA, ChannelOrder, ImageMetadata, ImageValue, Layout, convert_layout

_ORIENTATION = 0x0112
_PIL_DECODED_MODES = frozenset({"P", "LA", "I", "F", "CMYK", "1"})
_PIL_DECODED_FORMATS = frozenset({"GIF", "TGA"})
_PIL_WRITTEN = frozenset({Format.TGA, Format.GIF})
_HOLDS_ALPHA = frozenset({Format.PNG, Format.WEBP, Format.TIFF, Format.AVIF, Format.TGA})
_CV_EXTENSION = {
    Format.PNG: ".png",
    Format.JPEG: ".jpg",
    Format.WEBP: ".webp",
    Format.TIFF: ".tiff",
    Format.BMP: ".bmp",
    Format.AVIF: ".avif",
}
_TIFF_COMPRESSION = {"none": 1, "lzw": 5, "deflate": 32946}
_PIL_TIFF_COMPRESSION = {"none": None, "lzw": "tiff_lzw", "deflate": "tiff_adobe_deflate"}
_DTYPE_BY_DEPTH: dict[int, type[np.generic]] = {8: np.uint8, 16: np.uint16, 32: np.float32}
_PIL_TRANSPOSE = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


@dataclass(frozen=True)
class EncodeOptions:
    """How ``encode_image`` writes a file.

    Attributes:
        depth: Bit depth to write (8, 16 or 32 for float); ``None`` writes the
            image's ``source_depth``. Rounded down to what the format stores.
        jpeg_quality: JPEG quality, 0–100.
        png_compression: PNG zlib level, 0 (none) to 9 (smallest).
        webp_quality: Lossy WebP quality, 1–100.
        webp_lossless: Write lossless WebP; ``webp_quality`` is then ignored.
        tiff_compression: ``"none"``, ``"lzw"`` or ``"deflate"``.
        avif_quality: AVIF quality, 0–100.
    """

    depth: int | None = None
    jpeg_quality: int = 95
    png_compression: int = 3
    webp_quality: int = 90
    webp_lossless: bool = False
    tiff_compression: str = "lzw"
    avif_quality: int = 80


def read_image(path: Path) -> ImageValue:
    """Decode the image file at ``path``; for GIF the first frame.

    The EXIF orientation is applied to the pixels and reset to 1 in the carried
    EXIF block. Gray files stay gray, palette files with transparency become RGBA,
    CMYK becomes RGB; 16-bit and float files record ``source_depth`` 16 / 32. A
    TIFF carries its ICC profile but no EXIF block.

    Raises:
        OSError: ``path`` cannot be read.
        ValueError: The file is not a decodable image.
    """
    data = path.read_bytes()
    header, orientation, metadata = _read_header(data)
    try:
        if header is not None and (
            header.format in _PIL_DECODED_FORMATS or header.mode in _PIL_DECODED_MODES
        ):
            header.seek(0)
            header.load()
            if orientation in _PIL_TRANSPOSE:
                header = header.transpose(_PIL_TRANSPOSE[orientation])
            return from_pil(header, metadata)
        pixels = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    except (OSError, EOFError, SyntaxError, ValueError, struct.error, cv2.error) as exc:
        raise ValueError(f"cannot read image {path.name}") from exc
    if pixels is None:
        raise ValueError(f"cannot read image {path.name}")
    return from_cv_bgr(np.ascontiguousarray(_orient(pixels, orientation)), metadata)


def encode_image(img: ImageValue, fmt: Format, options: EncodeOptions) -> bytes:
    """Return the bytes of ``img`` written as ``fmt``.

    Alpha is dropped for formats without it (JPEG, BMP, GIF). ICC and EXIF are
    written only for an 8-bit file in a format that holds them (see
    ``HOLDS_METADATA``); a 16-bit or float file carries none.

    Raises:
        ValueError: ``options.tiff_compression`` is not ``none``, ``lzw`` or
            ``deflate``, or the codec cannot encode the image.
    """
    if options.tiff_compression not in _TIFF_COMPRESSION:
        known = ", ".join(_TIFF_COMPRESSION)
        raise ValueError(f"tiff_compression must be one of {known}, got {options.tiff_compression!r}")
    depth = best_depth(fmt, options.depth or img.source_depth)
    if img.layout is Layout.RGBA and fmt not in _HOLDS_ALPHA:
        img = convert_layout(img, Layout.RGB)
    has_metadata = img.metadata != NO_METADATA
    if fmt in _PIL_WRITTEN or (fmt in HOLDS_METADATA and has_metadata and depth == 8):
        return _encode_pil(img, fmt, options)
    return _encode_cv(img, fmt, depth, options)


def _read_header(data: bytes) -> tuple[Image.Image | None, int, ImageMetadata]:
    """Open ``data`` lazily with Pillow; return the image, EXIF orientation and metadata to carry.

    Returns ``(None, 1, NO_METADATA)`` when Pillow cannot parse the header.
    """
    try:
        header = Image.open(BytesIO(data))
    except (UnidentifiedImageError, OSError, EOFError, SyntaxError, ValueError, struct.error):
        return None, 1, NO_METADATA
    icc = header.info.get("icc_profile") or None
    orientation, exif_bytes = 1, None
    try:
        # PngImageFile.getexif() decodes every pixel unless an eXIf chunk precedes IDAT;
        # the base implementation reads only ``info`` (and the TIFF IFD), never pixels.
        exif = Image.Image.getexif(header)
        orientation = int(exif.get(_ORIENTATION, 1))
        if "exif" in header.info:
            if _ORIENTATION in exif:
                exif[_ORIENTATION] = 1
            exif_bytes = exif.tobytes()
    except (OSError, EOFError, SyntaxError, ValueError, struct.error):
        orientation, exif_bytes = 1, None  # damaged EXIF: keep the ICC, skip orientation
    return header, orientation, ImageMetadata(icc=icc, exif=exif_bytes)


def _orient(a: np.ndarray, orientation: int) -> np.ndarray:
    """Apply EXIF ``orientation`` (2–8) to an ``H×W(×C)`` array; other values return ``a``."""
    if orientation == 2:
        return a[:, ::-1]
    if orientation == 3:
        return a[::-1, ::-1]
    if orientation == 4:
        return a[::-1]
    if orientation == 5:
        return a.swapaxes(0, 1)
    if orientation == 6:
        return np.rot90(a, k=-1)
    if orientation == 7:
        return a.swapaxes(0, 1)[::-1, ::-1]
    if orientation == 8:
        return np.rot90(a, k=1)
    return a


def _encode_cv(img: ImageValue, fmt: Format, depth: int, options: EncodeOptions) -> bytes:
    params: list[int] = []
    if fmt is Format.JPEG:
        params = [cv2.IMWRITE_JPEG_QUALITY, options.jpeg_quality]
    elif fmt is Format.PNG:
        params = [cv2.IMWRITE_PNG_COMPRESSION, options.png_compression]
    elif fmt is Format.WEBP:
        params = [cv2.IMWRITE_WEBP_QUALITY, 101 if options.webp_lossless else options.webp_quality]
    elif fmt is Format.TIFF:
        params = [cv2.IMWRITE_TIFF_COMPRESSION, _TIFF_COMPRESSION[options.tiff_compression]]
    elif fmt is Format.AVIF:
        params = [cv2.IMWRITE_AVIF_QUALITY, options.avif_quality]
    pixels = img.array(_DTYPE_BY_DEPTH[depth], ChannelOrder.BGR)
    try:
        ok, buf = cv2.imencode(_CV_EXTENSION[fmt], pixels, params)
    except cv2.error as exc:
        raise ValueError(f"cannot encode {fmt.name}: {exc}") from exc
    if not ok:
        raise ValueError(f"cannot encode {fmt.name}")
    return buf.tobytes()


def _encode_pil(img: ImageValue, fmt: Format, options: EncodeOptions) -> bytes:
    kwargs: dict[str, Any] = {}
    if fmt in HOLDS_METADATA:
        if img.metadata.icc is not None:
            kwargs["icc_profile"] = img.metadata.icc
        if img.metadata.exif is not None:
            kwargs["exif"] = img.metadata.exif
    if fmt is Format.JPEG:
        kwargs["quality"] = options.jpeg_quality
    elif fmt is Format.PNG:
        kwargs["compress_level"] = options.png_compression
    elif fmt is Format.WEBP:
        kwargs["lossless"] = options.webp_lossless
        kwargs["quality"] = options.webp_quality
    elif fmt is Format.TIFF:
        kwargs["compression"] = _PIL_TIFF_COMPRESSION[options.tiff_compression]
    elif fmt is Format.AVIF:
        kwargs["quality"] = options.avif_quality
    out = BytesIO()
    try:
        to_pil(img).save(out, format=fmt.name, **kwargs)
    except (OSError, ValueError, KeyError) as exc:
        raise ValueError(f"cannot encode {fmt.name}: {exc}") from exc
    return out.getvalue()
