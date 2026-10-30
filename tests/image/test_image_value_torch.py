import numpy as np
import pytest

from haybale_image.value import ChannelOrder, ImageValue

torch = pytest.importorskip("torch")

pytestmark = pytest.mark.unit


def _gpu() -> str | None:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return None


def test_tensor_shape_dtype_device():
    v = ImageValue.from_array(np.zeros((5, 7, 3), dtype=np.uint8), order=ChannelOrder.BGR)
    t = v.tensor("cpu", torch.float16)
    assert tuple(t.shape) == (1, 3, 5, 7)
    assert t.dtype == torch.float16
    assert t.device.type == "cpu"


def test_tensor_matches_array_path():
    a = np.random.default_rng(0).integers(0, 256, (5, 7, 3), dtype=np.uint8)
    v = ImageValue.from_array(a, order=ChannelOrder.BGR)
    np.testing.assert_allclose(v.tensor("cpu")[0].permute(1, 2, 0).numpy(), v.array(np.float32), atol=1e-6)


def test_u8_round_trip_is_exact_through_f16():
    a = np.arange(768, dtype=np.uint16).astype(np.uint8).reshape(16, 16, 3)
    v = ImageValue.from_array(a, order=ChannelOrder.BGR)
    back = ImageValue.from_tensor(v.tensor("cpu", torch.float16)).array(np.uint8, ChannelOrder.BGR)
    np.testing.assert_array_equal(back, a)


@pytest.mark.parametrize("shape", [(1, 1, 3), (1081, 1921, 4)])
def test_odd_sizes_round_trip(shape):
    a = np.random.default_rng(1).integers(0, 256, shape, dtype=np.uint8)
    v = ImageValue.from_array(a)
    back = ImageValue.from_tensor(v.tensor("cpu", torch.float32)).array(np.uint8)
    np.testing.assert_array_equal(back, a)


def test_negative_stride_input_uploads():
    a = np.random.default_rng(2).integers(0, 256, (4, 6, 3), dtype=np.uint8)
    v = ImageValue.from_array(a[..., ::-1])
    expected = torch.from_numpy(np.ascontiguousarray(a[..., ::-1])).permute(2, 0, 1).float() / 255
    torch.testing.assert_close(v.tensor("cpu")[0], expected)


def test_from_tensor_accepts_chw_and_nchw():
    assert ImageValue.from_tensor(torch.zeros(3, 4, 5)).width == 5
    assert ImageValue.from_tensor(torch.zeros(1, 3, 4, 5)).height == 4
    with pytest.raises(ValueError, match="shape"):
        ImageValue.from_tensor(torch.zeros(2, 3, 4, 5))


def test_tensor_to_u8_clips():
    t = torch.tensor([1.03, -0.01, 0.5]).reshape(1, 1, 3)
    np.testing.assert_array_equal(ImageValue.from_tensor(t).array(np.uint8), [[255, 0, 128]])


def test_tensor_accessor_cached():
    v = ImageValue.from_array(np.zeros((2, 2, 3), dtype=np.uint8))
    assert v.tensor("cpu", torch.float16) is v.tensor("cpu", torch.float16)
    assert v.tensor("cpu", torch.float32) is not v.tensor("cpu", torch.float16)


def test_gpu_residency():
    dev = _gpu()
    if dev is None:
        pytest.skip("no CUDA or MPS device")
    v = ImageValue.from_array(np.zeros((4, 4, 3), dtype=np.uint8), order=ChannelOrder.BGR)
    t = v.tensor(dev, torch.float16)
    assert t.device.type == dev
    assert ImageValue.from_tensor(t).residency.startswith(dev)
