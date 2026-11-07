"""A text chunk in PNG bytes, placed before the pixels and read without decoding them."""

from __future__ import annotations

import struct
import zlib
from typing import BinaryIO

#: The keyword Save Image and Load Image keep an image's fields under.
FIELDS_KEYWORD = "haywire:fields"

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_IHDR_END = len(_SIGNATURE) + 4 + 4 + 13 + 4  # length, type, a fixed 13 bytes of data, CRC
_MAX_CHUNK_BYTES = 64 * 1024 * 1024
_PIXEL_CHUNKS = (b"IDAT", b"IEND")


def with_text_chunk(png: bytes, keyword: str, text: str) -> bytes:
    """Return ``png`` with ``text`` added under ``keyword``; the pixels are untouched.

    The text is stored uncompressed: Pillow refuses a compressed chunk that unpacks
    to more than 1 MB.

    Args:
        png: A complete PNG file of any bit depth.
        keyword: 1 to 79 Latin-1 characters.
        text: The text to store.

    Raises:
        ValueError: ``png`` is not a PNG file.
    """
    if not png.startswith(_SIGNATURE):
        raise ValueError("not a PNG file")
    # iTXt: keyword, NUL, not compressed, compression method, empty language, empty translation.
    body = b"iTXt" + keyword.encode("latin-1") + b"\0\0\0\0\0" + text.encode()
    chunk = struct.pack(">I", len(body) - 4) + body + struct.pack(">I", zlib.crc32(body))
    # Before the pixels, so a reader finds it without going through them.
    return png[:_IHDR_END] + chunk + png[_IHDR_END:]


def read_text_chunk(stream: BinaryIO, keyword: str) -> str | None:
    """Return the text ``with_text_chunk`` stored under ``keyword``, reading only up to the pixels.

    Returns ``None`` if the stream is not a PNG file, holds no such chunk before its
    pixels, or the chunk is damaged, compressed or above 64 MB.

    Args:
        stream: A seekable binary stream at the start of the file.
        keyword: The keyword to look for.
    """
    if stream.read(len(_SIGNATURE)) != _SIGNATURE:
        return None
    wanted = keyword.encode("latin-1") + b"\0"
    while True:
        header = stream.read(8)
        if len(header) < 8:
            return None
        length, kind = struct.unpack(">I4s", header)
        if kind in _PIXEL_CHUNKS:
            return None
        if kind != b"iTXt":
            stream.seek(length + 4, 1)
            continue
        if length > _MAX_CHUNK_BYTES:
            return None
        data = stream.read(length)
        crc = stream.read(4)
        if len(data) < length or len(crc) < 4 or struct.unpack(">I", crc)[0] != zlib.crc32(kind + data):
            return None
        if data.startswith(wanted):
            return _itxt_text(data[len(wanted) :])


def _itxt_text(data: bytes) -> str | None:
    """Return the text of an iTXt chunk's bytes after its keyword, or ``None`` if compressed or not UTF-8."""
    if len(data) < 2 or data[0] != 0:
        return None
    language_end = data.find(b"\0", 2)
    translation_end = data.find(b"\0", language_end + 1) if language_end >= 0 else -1
    if translation_end < 0:
        return None
    try:
        return data[translation_end + 1 :].decode()
    except UnicodeDecodeError:
        return None
