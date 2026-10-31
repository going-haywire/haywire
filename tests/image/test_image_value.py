import numpy as np
import pytest

from haybale_image.value import NO_METADATA, ChannelOrder, ImageMetadata, ImageValue, Layout

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


# --- array() accessor -----------------------------------------------------


def _u8(values, shape=None):
    a = np.array(values, dtype=np.uint8)
    return a.reshape(shape) if shape else a


def test_same_storage_is_zero_copy():
    a = np.arange(72, dtype=np.uint8).reshape(4, 6, 3)
    out = ImageValue.from_array(a, order=ChannelOrder.BGR).array(np.uint8, ChannelOrder.BGR)
    assert np.shares_memory(out, a)


def test_order_swap_keeps_alpha_last():
    a = np.arange(16, dtype=np.uint8).reshape(2, 2, 4)
    out = ImageValue.from_array(a, order=ChannelOrder.BGR).array(np.uint8, ChannelOrder.RGB)
    np.testing.assert_array_equal(out, a[..., [2, 1, 0, 3]])


def test_gray_ignores_order():
    v = ImageValue.from_array(np.arange(6, dtype=np.uint8).reshape(2, 3))
    np.testing.assert_array_equal(v.array(order=ChannelOrder.BGR), v.array(order=ChannelOrder.RGB))


def test_u8_to_float_scales():
    out = ImageValue.from_array(_u8([255, 0, 51], (1, 3))).array(np.float32)
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, [[1.0, 0.0, 0.2]], atol=1e-6)


def test_u16_to_float_scales():
    out = ImageValue.from_array(np.full((1, 1), 65535, dtype=np.uint16)).array(np.float32)
    assert out[0, 0] == pytest.approx(1.0)


def test_float_to_u8_clips_and_rounds():
    a = np.array([[-0.1, 0.0, 0.5, 1.0, 1.03]], dtype=np.float32)
    out = ImageValue.from_array(a).array(np.uint8)
    np.testing.assert_array_equal(out, [[0, 0, 128, 255, 255]])


def test_u8_to_u16_is_times_257():
    out = ImageValue.from_array(_u8([255, 1], (1, 2))).array(np.uint16)
    np.testing.assert_array_equal(out, [[65535, 257]])


def test_float16_target():
    out = ImageValue.from_array(_u8([128], (1, 1))).array(np.float16)
    assert out.dtype == np.float16
    assert float(out[0, 0]) == pytest.approx(128 / 255, abs=1e-3)


def test_returned_arrays_are_read_only():
    v = ImageValue.from_array(np.zeros((2, 2, 3), dtype=np.uint8), order=ChannelOrder.BGR)
    for out in (v.array(np.uint8, ChannelOrder.BGR), v.array(np.uint8), v.array(np.float32)):
        with pytest.raises(ValueError, match="read-only"):
            out[0, 0, 0] = 1


def test_accessor_is_cached():
    v = ImageValue.from_array(np.zeros((2, 2, 3), dtype=np.uint8))
    assert v.array(np.float32) is v.array(np.float32)
    assert v.array(np.float16) is not v.array(np.float32)


# --- metadata, empty images, derive ------------------------------------------


def test_empty_has_layout_and_no_pixels():
    for layout, shape in ((Layout.GRAY, (0, 0)), (Layout.RGB, (0, 0, 3)), (Layout.RGBA, (0, 0, 4))):
        img = ImageValue.empty(layout)
        assert img.layout is layout
        assert img.is_empty
        assert img.array(np.uint8).shape == shape
        assert img.source_depth == 8


def test_non_empty_is_not_empty():
    assert not ImageValue.from_array(np.zeros((2, 2), np.uint8)).is_empty


def test_metadata_defaults_to_none():
    assert ImageValue.from_array(np.zeros((2, 2), np.uint8)).metadata == NO_METADATA


def test_derive_carries_metadata():
    meta = ImageMetadata(icc=b"icc", exif=b"exif")
    src = ImageValue.from_array(np.zeros((2, 2), np.uint8), metadata=meta)
    out = src.derive(ImageValue.from_array(np.ones((4, 4, 3), np.uint8)))
    assert out.metadata == meta
    assert out.width == 4


def test_with_metadata_shares_cache_and_primary():
    img = ImageValue.from_array(np.zeros((2, 2, 3), np.uint8))
    a = img.array()
    other = img.with_metadata(ImageMetadata(icc=b"x"))
    assert other.array() is a
    assert other._cache is img._cache
    assert other._primary is img._primary
    assert other.metadata.icc == b"x"
    assert img.metadata == NO_METADATA
