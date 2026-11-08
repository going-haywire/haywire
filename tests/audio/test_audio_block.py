"""AudioBlock: planar float32, read-only, validated."""

import numpy as np
import pytest

from haybale_audio.value import AudioBlock

pytestmark = pytest.mark.unit


def test_shape_properties():
    block = AudioBlock(np.zeros((2, 256), np.float32), 48000)
    assert (block.channels, block.frames) == (2, 256)
    assert block.duration == pytest.approx(256 / 48000)


def test_data_is_read_only():
    block = AudioBlock.silence(1, 8, 48000)
    with pytest.raises(ValueError, match="read-only"):
        block.data[0, 0] = 1.0


@pytest.mark.parametrize(
    "data",
    [np.zeros((2, 8), np.float64), np.zeros(8, np.float32), np.zeros((2, 2, 8), np.float32)],
    ids=["float64", "1-d", "3-d"],
)
def test_rejects_wrong_array(data):
    with pytest.raises(ValueError, match="float32"):
        AudioBlock(data, 48000)


def test_rejects_non_positive_rate():
    with pytest.raises(ValueError, match="sample_rate"):
        AudioBlock.silence(1, 8, 0)
