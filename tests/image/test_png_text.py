"""A text chunk in PNG bytes: written before the pixels, readable without decoding them."""

import io

import cv2
import numpy as np
import pytest
from haybale_image.io.png_text import read_text_chunk, with_text_chunk
from PIL import Image

pytestmark = pytest.mark.unit


def _png(array: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", array)
    assert ok
    return buf.tobytes()


@pytest.fixture
def png() -> bytes:
    return _png(np.full((4, 6, 3), 200, np.uint8))


def test_the_text_reads_back(png):
    data = with_text_chunk(png, "haywire:fields", "héllo")
    assert read_text_chunk(io.BytesIO(data), "haywire:fields") == "héllo"


def test_other_readers_still_decode_the_pixels(png):
    data = with_text_chunk(png, "haywire:fields", "text")
    decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    assert decoded is not None
    assert decoded.shape == (4, 6, 3)
    opened = Image.open(io.BytesIO(data))
    assert opened.info["haywire:fields"] == "text"
    opened.load()


def test_sixteen_bit_keeps_its_depth():
    data = with_text_chunk(_png(np.full((4, 6, 3), 1000, np.uint16)), "k", "text")
    decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    assert decoded is not None
    assert decoded.dtype == np.uint16
    assert read_text_chunk(io.BytesIO(data), "k") == "text"


def test_text_above_pillows_limit_for_compressed_chunks_reads_back(png):
    text = "x" * 3_000_000
    data = with_text_chunk(png, "k", text)
    assert read_text_chunk(io.BytesIO(data), "k") == text
    assert Image.open(io.BytesIO(data)).info["k"] == text


def test_another_keyword_or_no_chunk_reads_as_none(png):
    assert read_text_chunk(io.BytesIO(png), "k") is None
    assert read_text_chunk(io.BytesIO(with_text_chunk(png, "other", "t")), "k") is None


def test_reading_stops_at_the_pixels(png):
    """Only the chunks before the pixels are read, however large the file."""
    data = with_text_chunk(png, "k", "t")
    idat = data.index(b"IDAT") - 4
    assert read_text_chunk(io.BytesIO(data[: idat + 8]), "k") == "t"


def test_another_format_reads_as_none():
    ok, jpeg = cv2.imencode(".jpg", np.zeros((4, 4, 3), np.uint8))
    assert ok
    assert read_text_chunk(io.BytesIO(jpeg.tobytes()), "k") is None
    assert read_text_chunk(io.BytesIO(b""), "k") is None


def test_writing_into_something_else_is_refused():
    with pytest.raises(ValueError, match="PNG"):
        with_text_chunk(b"not a png", "k", "t")


@pytest.mark.parametrize("damage", ["crc", "truncate", "bad_utf8"])
def test_a_damaged_chunk_reads_as_none(png, damage):
    data = bytearray(with_text_chunk(png, "k", "text"))
    start = data.index(b"iTXt")
    if damage == "crc":
        length = int.from_bytes(data[start - 4 : start], "big")
        data[start + 4 + length] ^= 0xFF
    elif damage == "truncate":
        data = data[: start + 6]
    else:
        at = data.index(b"text", start)
        data[at] = 0xFF
    assert read_text_chunk(io.BytesIO(bytes(data)), "k") is None


def test_a_length_past_the_limit_reads_as_none(png):
    data = bytearray(with_text_chunk(png, "k", "text"))
    start = data.index(b"iTXt")
    data[start - 4 : start] = (2**31 - 1).to_bytes(4, "big")
    assert read_text_chunk(io.BytesIO(bytes(data)), "k") is None
