"""Image file formats: which extension means which format, and what each format can hold."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path


class Format(StrEnum):
    """An image file format the image IO nodes read and write."""

    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"
    TIFF = "tiff"
    BMP = "bmp"
    GIF = "gif"
    TGA = "tga"
    AVIF = "avif"


FORMAT_BY_EXTENSION: dict[str, Format] = {
    ".png": Format.PNG,
    ".jpg": Format.JPEG,
    ".jpeg": Format.JPEG,
    ".jpe": Format.JPEG,
    ".webp": Format.WEBP,
    ".tif": Format.TIFF,
    ".tiff": Format.TIFF,
    ".bmp": Format.BMP,
    ".gif": Format.GIF,
    ".tga": Format.TGA,
    ".avif": Format.AVIF,
}
"""Lower-case file extension (with the dot) → format."""

DEPTHS: dict[Format, tuple[int, ...]] = {fmt: (8,) for fmt in Format} | {
    Format.PNG: (8, 16),
    Format.TIFF: (8, 16, 32),
}
"""Bit depths each format can store, ascending; 32 means float32."""

HOLDS_METADATA: frozenset[Format] = frozenset(
    {Format.PNG, Format.JPEG, Format.WEBP, Format.TIFF, Format.AVIF}
)
"""Formats that can carry an ICC profile and EXIF block."""


def format_for(path: Path) -> Format:
    """Return the format named by ``path``'s extension, ignoring case.

    Raises:
        ValueError: ``path`` has no extension, or one not in ``FORMAT_BY_EXTENSION``.
    """
    suffix = path.suffix.lower()
    if not suffix:
        raise ValueError(f"'{path.name}' has no extension; use {_known_extensions()}")
    fmt = FORMAT_BY_EXTENSION.get(suffix)
    if fmt is None:
        raise ValueError(f"unsupported extension '{suffix}'; use {_known_extensions()}")
    return fmt


def best_depth(fmt: Format, requested: int) -> int:
    """Return the deepest depth ``fmt`` stores that is at most ``requested``, else its smallest.

    ``best_depth(Format.PNG, 32)`` is 16; ``best_depth(Format.JPEG, 16)`` is 8.
    """
    fitting = [d for d in DEPTHS[fmt] if d <= requested]
    return fitting[-1] if fitting else DEPTHS[fmt][0]


def _known_extensions() -> str:
    return ", ".join(FORMAT_BY_EXTENSION)
