import numpy as np
import pytest

from haybale_image.value import ChannelOrder, ImageMetadata, ImageValue, Layout, convert_layout

pytestmark = pytest.mark.unit


def rgb(data=(((1, 2, 3),),), **kw):
    return ImageValue.from_array(np.array(data, np.uint8), **kw)


def gray(data):
    return ImageValue.from_array(np.array(data, np.uint8))


def rgba(data):
    return ImageValue.from_array(np.array(data, np.uint8))


def rgb_u16(**kw):
    return ImageValue.from_array(np.full((2, 2, 3), 1000, np.uint16), **kw)


def test_same_layout_is_identity():
    img = rgb()
    assert convert_layout(img, Layout.RGB) is img


def test_gray_to_rgb_replicates():
    assert (convert_layout(gray([[10]]), Layout.RGB).array(np.uint8) == [[[10, 10, 10]]]).all()


def test_gray_to_rgba_replicates_and_opaque():
    out = convert_layout(gray([[10]]), Layout.RGBA).array(np.uint8)
    assert (out == [[[10, 10, 10, 255]]]).all()


def test_rgba_to_rgb_drops_alpha():
    assert (convert_layout(rgba([[[1, 2, 3, 0]]]), Layout.RGB).array(np.uint8) == [[[1, 2, 3]]]).all()


def test_rgb_to_rgba_alpha_is_opaque_u16():
    assert convert_layout(rgb_u16(), Layout.RGBA).array(np.uint16)[..., 3].min() == 65535


def test_rgb_to_rgba_alpha_is_opaque_float():
    img = ImageValue.from_array(np.zeros((1, 1, 3), np.float32))
    assert convert_layout(img, Layout.RGBA).array(np.float32)[0, 0, 3] == 1.0


def test_rgb_to_gray_rec601():
    assert convert_layout(rgb([[[255, 0, 0]]]), Layout.GRAY).array(np.uint8)[0, 0] == 76


def test_rgba_to_gray_ignores_alpha():
    assert convert_layout(rgba([[[0, 255, 0, 7]]]), Layout.GRAY).array(np.uint8)[0, 0] == 150


def test_bgr_storage_weights_follow_order():
    img = ImageValue.from_array(np.array([[[0, 0, 255]]], np.uint8), order=ChannelOrder.BGR)  # red
    assert convert_layout(img, Layout.GRAY).array(np.uint8)[0, 0] == 76


def test_keeps_storage_and_metadata():
    out = convert_layout(rgb_u16(metadata=ImageMetadata(icc=b"i")), Layout.GRAY)
    assert out.source_depth == 16
    assert out.metadata.icc == b"i"
    assert out.residency == "array"
    assert out.array(np.uint16).dtype == np.uint16


def test_keeps_channel_order():
    img = ImageValue.from_array(np.array([[[1, 2, 3]]], np.uint8), order=ChannelOrder.BGR)
    out = convert_layout(img, Layout.RGBA)
    assert (out.array(np.uint8, ChannelOrder.BGR) == [[[1, 2, 3, 255]]]).all()


@pytest.mark.parametrize("src", list(Layout))
@pytest.mark.parametrize("dst", list(Layout))
def test_empty_converts(src, dst):
    out = convert_layout(ImageValue.empty(src), dst)
    assert out.layout is dst
    assert out.is_empty
