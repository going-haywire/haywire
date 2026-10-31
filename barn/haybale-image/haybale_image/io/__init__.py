"""Image file IO: formats by extension and the codecs that read and write them."""

from haybale_image.io.codecs import EncodeOptions, encode_image, read_image
from haybale_image.io.formats import (
    DEPTHS,
    FORMAT_BY_EXTENSION,
    HOLDS_METADATA,
    Format,
    best_depth,
    format_for,
)

__all__ = [
    "DEPTHS",
    "FORMAT_BY_EXTENSION",
    "HOLDS_METADATA",
    "EncodeOptions",
    "Format",
    "best_depth",
    "encode_image",
    "format_for",
    "read_image",
]
