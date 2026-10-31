import numpy as np
import pytest
from PIL import Image

from haybale_image.helpers import from_cv_bgr, from_pil, premultiply, to_cv_bgr, to_pil, unpremultiply
from haybale_image.value import ChannelOrder, ImageValue, Layout

pytestmark = pytest.mark.unit


def px(img: ImageValue, dtype=np.uint8):
    return img.array(dtype)[0, 0]


def test_from_pil_1():
    im = Image.new("1", (2, 2), 1)
    img = from_pil(im)
    assert img.layout is Layout.GRAY
    assert img.source_depth == 8
    assert px(img) == 255


def test_from_pil_l():
    img = from_pil(Image.new("L", (2, 2), 77))
    assert img.layout is Layout.GRAY
    assert img.source_depth == 8
    assert px(img) == 77


def test_from_pil_la_replicates_gray_into_rgba():
    img = from_pil(Image.new("LA", (2, 2), (50, 200)))
    assert img.layout is Layout.RGBA
    assert list(px(img)) == [50, 50, 50, 200]


def test_from_pil_p_without_transparency_is_rgb():
    im = Image.new("P", (2, 2), 1)
    im.putpalette([0, 0, 0, 10, 20, 30] + [0] * 756)
    img = from_pil(im)
    assert img.layout is Layout.RGB
    assert list(px(img)) == [10, 20, 30]


def test_from_pil_p_with_transparency_is_rgba():
    im = Image.new("P", (2, 2), 1)
    im.putpalette([0, 0, 0, 10, 20, 30] + [0] * 756)
    im.info["transparency"] = 1
    img = from_pil(im)
    assert img.layout is Layout.RGBA
    assert list(px(img)) == [10, 20, 30, 0]


def test_from_pil_rgb():
    img = from_pil(Image.new("RGB", (2, 2), (1, 2, 3)))
    assert img.layout is Layout.RGB
    assert list(px(img)) == [1, 2, 3]


def test_from_pil_rgba():
    img = from_pil(Image.new("RGBA", (2, 2), (1, 2, 3, 4)))
    assert img.layout is Layout.RGBA
    assert list(px(img)) == [1, 2, 3, 4]


def test_from_pil_cmyk_is_rgb():
    img = from_pil(Image.new("CMYK", (2, 2), (0, 0, 0, 0)))
    assert img.layout is Layout.RGB
    assert list(px(img)) == [255, 255, 255]


def test_from_pil_ycbcr_is_rgb():
    img = from_pil(Image.new("YCbCr", (2, 2), (255, 128, 128)))
    assert img.layout is Layout.RGB
    assert list(px(img)) == [255, 255, 255]


def test_from_pil_i16():
    arr = np.full((2, 2), 1234, np.uint16)
    im = Image.fromarray(arr)
    assert im.mode == "I;16"
    img = from_pil(im)
    assert img.layout is Layout.GRAY
    assert img.source_depth == 16
    assert px(img, np.uint16) == 1234


def test_from_pil_i16b_byte_order():
    im = Image.frombytes("I;16B", (2, 1), bytes([0x12, 0x34, 0x00, 0x01]))
    img = from_pil(im)
    assert img.source_depth == 16
    assert list(img.array(np.uint16)[0]) == [0x1234, 1]


def test_from_pil_i_clips_to_u16():
    im = Image.new("I", (2, 1))
    im.putdata([-5, 70000])
    img = from_pil(im)
    assert img.layout is Layout.GRAY
    assert img.source_depth == 16
    assert list(img.array(np.uint16)[0]) == [0, 65535]


def test_from_pil_f():
    img = from_pil(Image.new("F", (2, 2), 0.25))
    assert img.layout is Layout.GRAY
    assert img.source_depth == 32
    assert px(img, np.float32) == pytest.approx(0.25)


def test_from_pil_other_mode_converts():
    img = from_pil(Image.new("HSV", (2, 2), (0, 0, 255)))
    assert img.layout is Layout.RGB
    assert list(px(img)) == [255, 255, 255]


def test_to_pil_gray16_round_trip():
    arr = np.arange(6, dtype=np.uint16).reshape(2, 3) * 1000
    img = from_pil(to_pil(ImageValue.from_array(arr), 16))
    assert np.array_equal(img.array(np.uint16), arr)


def test_to_pil_modes():
    g = ImageValue.from_array(np.full((2, 2), 9, np.uint8))
    assert to_pil(g).mode == "L"
    assert to_pil(g, 16).mode == "I;16"
    assert to_pil(g, 32).mode == "F"
    assert to_pil(ImageValue.from_array(np.zeros((2, 2, 3), np.uint8))).mode == "RGB"
    assert to_pil(ImageValue.from_array(np.zeros((2, 2, 4), np.uint8)), 16).mode == "RGBA"


def test_cv_bgr_round_trip_no_copy():
    bgr = np.zeros((2, 2, 3), np.uint8)
    bgr[..., 0] = 10  # B
    bgr[..., 2] = 30  # R
    img = from_cv_bgr(bgr)
    assert list(px(img)) == [30, 0, 10]
    back = to_cv_bgr(img)
    assert np.shares_memory(back, bgr)
    assert np.array_equal(back, bgr)
    assert img.array(np.uint8, ChannelOrder.BGR) is not None


def test_premultiply_round_trip():
    arr = np.zeros((1, 2, 4), np.float32)
    arr[0, 0] = (0.8, 0.4, 0.2, 0.5)
    arr[0, 1] = (0.9, 0.9, 0.9, 0.0)
    pm = premultiply(ImageValue.from_array(arr))
    assert pm.dtype == np.float32
    assert pm[0, 0, :3] == pytest.approx([0.4, 0.2, 0.1], abs=1e-6)
    back = unpremultiply(pm)
    assert back[0, 0] == pytest.approx(arr[0, 0], abs=1e-6)
    assert list(back[0, 1]) == [0, 0, 0, 0]


def test_premultiply_rejects_rgb():
    img = ImageValue.from_array(np.zeros((2, 2, 3), np.uint8))
    with pytest.raises(ValueError, match="needs"):
        premultiply(img)
    with pytest.raises(ValueError, match="needs"):
        unpremultiply(np.zeros((2, 2, 3), np.float32))
