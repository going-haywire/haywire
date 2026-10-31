"""Conversions between ``ImageValue`` and PIL / OpenCV BGR arrays, and alpha premultiplication."""

from __future__ import annotations

import numpy as np
from PIL import Image

from haybale_image.value import NO_METADATA, ChannelOrder, ImageMetadata, ImageValue, Layout


def from_pil(im: Image.Image, metadata: ImageMetadata = NO_METADATA) -> ImageValue:
    """Wrap a PIL image as an ``ImageValue``.

    Args:
        im: Any PIL image. Gray modes stay gray, ``LA`` and transparent ``P`` become
            RGBA, ``CMYK``/``YCbCr`` and unknown modes are converted to RGB(A).
        metadata: ICC and EXIF blocks to carry with the image.

    Returns:
        The image; 16-bit and float sources record ``source_depth`` 16 / 32.
    """
    mode = im.mode
    if mode == "1":
        return ImageValue.from_array(np.asarray(im.convert("L")), metadata=metadata)
    if mode == "L":
        return ImageValue.from_array(np.asarray(im), metadata=metadata)
    if mode == "LA":
        la = np.asarray(im)
        rgba = np.concatenate([np.repeat(la[..., :1], 3, axis=2), la[..., 1:]], axis=2)
        return ImageValue.from_array(rgba, metadata=metadata)
    if mode == "P":
        target = "RGBA" if "transparency" in im.info else "RGB"
        return ImageValue.from_array(np.asarray(im.convert(target)), metadata=metadata)
    if mode in ("RGB", "RGBA"):
        return ImageValue.from_array(np.asarray(im), metadata=metadata)
    if mode in ("CMYK", "YCbCr"):
        return ImageValue.from_array(np.asarray(im.convert("RGB")), metadata=metadata)
    if mode in ("I;16", "I;16L", "I;16B", "I;16N"):
        # Native byte order explicitly: I;16B arrives as a big-endian view.
        data = np.asarray(im).astype(np.uint16)
        return ImageValue.from_array(data, source_depth=16, metadata=metadata)
    if mode == "I":
        data = np.clip(np.asarray(im), 0, 65535).astype(np.uint16)
        return ImageValue.from_array(data, source_depth=16, metadata=metadata)
    if mode == "F":
        data = np.asarray(im).astype(np.float32)
        return ImageValue.from_array(data, source_depth=32, metadata=metadata)
    target = "RGBA" if "A" in im.getbands() else "RGB"
    return ImageValue.from_array(np.asarray(im.convert(target)), metadata=metadata)


def to_pil(img: ImageValue, depth: int = 8) -> Image.Image:
    """Convert an ``ImageValue`` to a PIL image.

    Args:
        img: The image.
        depth: Bit depth for gray images: 8 (``L``), 16 (``I;16``) or 32 (``F``).
            Ignored for RGB and RGBA, which are always 8-bit (Pillow has no
            16-bit RGB; use OpenCV for that).

    Raises:
        ValueError: ``depth`` is not 8, 16 or 32.
    """
    if depth not in (8, 16, 32):
        raise ValueError(f"depth must be 8, 16 or 32, got {depth}")
    if img.layout is Layout.GRAY:
        dtype = {8: np.uint8, 16: np.uint16, 32: np.float32}[depth]
        return Image.fromarray(np.ascontiguousarray(img.array(dtype)))
    return Image.fromarray(np.ascontiguousarray(img.array(np.uint8)))


def from_cv_bgr(
    a: np.ndarray, metadata: ImageMetadata = NO_METADATA, source_depth: int | None = None
) -> ImageValue:
    """Wrap an OpenCV ``H×W×3``/``H×W×4`` BGR(A) (or gray) array without copying."""
    return ImageValue.from_array(a, order=ChannelOrder.BGR, source_depth=source_depth, metadata=metadata)


def to_cv_bgr(img: ImageValue, dtype: type[np.generic] = np.uint8) -> np.ndarray:
    """Return the pixels as a BGR(A) array of ``dtype`` (a view when storage allows)."""
    return img.array(dtype, ChannelOrder.BGR)


def premultiply(img: ImageValue) -> np.ndarray:
    """Return float32 ``H×W×4`` RGB-order pixels with colour multiplied by alpha.

    Raises:
        ValueError: ``img`` is not RGBA.
    """
    if img.layout is not Layout.RGBA:
        raise ValueError(f"premultiply needs an RGBA image, got {img.layout.name}")
    out = np.array(img.array(np.float32), dtype=np.float32, copy=True)
    out[..., :3] *= out[..., 3:4]
    return out


def unpremultiply(rgba: np.ndarray) -> np.ndarray:
    """Divide colour by alpha (float32 ``H×W×4``); alpha-0 pixels become 0.

    Raises:
        ValueError: ``rgba`` is not ``H×W×4``.
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError(f"unpremultiply needs an H×W×4 array, got shape {rgba.shape}")
    out = np.array(rgba, dtype=np.float32, copy=True)
    alpha = out[..., 3:4]
    nz = alpha > 0
    np.divide(out[..., :3], alpha, out=out[..., :3], where=nz)
    out[..., :3] = np.where(nz, out[..., :3], 0.0)
    return out
