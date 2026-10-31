"""Colour-profile and EXIF bytes that travel with an ``ImageValue``."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageMetadata:
    """Opaque ICC profile and EXIF blocks carried alongside the pixels.

    Attributes:
        icc: Raw ICC profile bytes, or ``None``.
        exif: Raw EXIF bytes, or ``None``.
    """

    icc: bytes | None = None
    exif: bytes | None = None


NO_METADATA = ImageMetadata()
