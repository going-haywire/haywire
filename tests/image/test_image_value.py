import numpy as np
import pytest

from haybale_image.value import ChannelOrder, ImageValue, Layout

pytestmark = pytest.mark.unit


# --- construction from arrays ---------------------------------------------


def test_gray_rgb_rgba_layouts_from_shape():
    cases = [((4, 6), Layout.GRAY, 1), ((4, 6, 3), Layout.RGB, 3), ((4, 6, 4), Layout.RGBA, 4)]
    for shape, layout, channels in cases:
        v = ImageValue.from_array(np.zeros(shape, dtype=np.uint8))
        assert v.layout is layout
        assert v.channels == channels
        assert v.width == 6
        assert v.height == 4
        assert v.residency == "array"


def test_hw1_is_gray():
    v = ImageValue.from_array(np.zeros((4, 6, 1), dtype=np.uint8))
    assert v.layout is Layout.GRAY
    assert v.channels == 1


@pytest.mark.parametrize("shape", [(4, 6, 2), (4, 6, 5), (2, 4, 6, 3), (6,)])
def test_bad_shapes_raise_value_error(shape):
    with pytest.raises(ValueError, match="shape"):
        ImageValue.from_array(np.zeros(shape, dtype=np.uint8))


@pytest.mark.parametrize("dtype", [np.int32, np.bool_, np.float64])
def test_bad_dtypes_raise_type_error(dtype):
    with pytest.raises(TypeError, match="dtype"):
        ImageValue.from_array(np.zeros((4, 6, 3), dtype=dtype))


@pytest.mark.parametrize(
    ("dtype", "depth"), [(np.uint8, 8), (np.uint16, 16), (np.float16, 32), (np.float32, 32)]
)
def test_source_depth_defaults_from_dtype(dtype, depth):
    assert ImageValue.from_array(np.zeros((2, 2, 3), dtype=dtype)).source_depth == depth


def test_explicit_source_depth_kept_and_validated():
    a = np.zeros((2, 2, 3), dtype=np.float32)
    assert ImageValue.from_array(a, source_depth=16).source_depth == 16
    with pytest.raises(ValueError, match="source_depth"):
        ImageValue.from_array(a, source_depth=12)


def test_non_contiguous_input_wraps():
    a = np.zeros((4, 6, 3), dtype=np.uint8)
    cropped = ImageValue.from_array(a[1:3, ::2])
    assert (cropped.height, cropped.width) == (2, 3)
    flipped = ImageValue.from_array(a[..., ::-1])
    assert flipped.layout is Layout.RGB


def test_order_argument_is_a_channel_order():
    v = ImageValue.from_array(np.zeros((2, 2, 3), dtype=np.uint8), order=ChannelOrder.BGR)
    assert v.layout is Layout.RGB
