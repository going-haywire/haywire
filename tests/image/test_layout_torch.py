import numpy as np
import pytest

from haybale_image.value import ChannelOrder, ImageMetadata, ImageValue, Layout, convert_layout

torch = pytest.importorskip("torch")

pytestmark = pytest.mark.unit


def _t(a, dtype=np.uint8, **kw):
    a = np.asarray(a, dtype)
    a = a[None] if a.ndim == 2 else np.moveaxis(a, 2, 0)
    return ImageValue.from_tensor(torch.from_numpy(np.ascontiguousarray(a)), **kw)


def rgb(data=(((1, 2, 3),),), **kw):
    return _t(data, **kw)


def test_same_layout_is_identity():
    img = rgb()
    assert convert_layout(img, Layout.RGB) is img


def test_gray_to_rgb_replicates():
    out = convert_layout(_t([[10]]), Layout.RGB)
    assert (out.array(np.uint8) == [[[10, 10, 10]]]).all()
    assert out.residency == "cpu"


def test_gray_to_rgba_opaque():
    assert (convert_layout(_t([[10]]), Layout.RGBA).array(np.uint8) == [[[10, 10, 10, 255]]]).all()


def test_rgba_to_rgb_drops_alpha():
    out = convert_layout(_t([[[1, 2, 3, 0]]]), Layout.RGB)
    assert (out.array(np.uint8) == [[[1, 2, 3]]]).all()
    assert out.residency == "cpu"


def test_rgb_to_rgba_alpha_is_opaque_float():
    img = _t(np.zeros((1, 1, 3)), np.float32)
    assert convert_layout(img, Layout.RGBA).array(np.float32)[0, 0, 3] == 1.0


def test_rgb_to_gray_rec601():
    out = convert_layout(rgb([[[255, 0, 0]]]), Layout.GRAY)
    assert out.array(np.uint8)[0, 0] == 76
    assert out.residency == "cpu"


def test_bgr_storage_weights_follow_order():
    img = _t([[[0, 0, 255]]], order=ChannelOrder.BGR)
    assert convert_layout(img, Layout.GRAY).array(np.uint8)[0, 0] == 76


def test_keeps_storage_and_metadata():
    img = _t(np.full((2, 2, 3), 0.5), np.float16, source_depth=16, metadata=ImageMetadata(icc=b"i"))
    out = convert_layout(img, Layout.GRAY)
    assert out.source_depth == 16
    assert out.metadata.icc == b"i"
    assert out.residency == "cpu"
    assert out.tensor("cpu", torch.float16).dtype == torch.float16


@pytest.mark.parametrize("src", list(Layout))
@pytest.mark.parametrize("dst", list(Layout))
def test_empty_tensor_converts(src, dst):
    channels = {Layout.GRAY: 1, Layout.RGB: 3, Layout.RGBA: 4}[src]
    img = ImageValue.from_tensor(torch.zeros((channels, 0, 0), dtype=torch.uint8))
    out = convert_layout(img, dst)
    assert out.layout is dst
    assert out.is_empty
