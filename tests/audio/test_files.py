"""FileBlockReader and BlockWriter: round trip, looping, format checks."""

import numpy as np
import pytest
import soundfile as sf

from haybale_audio.io.files import BlockWriter, FileBlockReader
from haybale_audio.value import AudioBlock

pytestmark = pytest.mark.unit


def _tone(channels: int, frames: int) -> np.ndarray:
    return (np.sin(np.arange(frames) / 10.0)[None, :] * np.linspace(0.1, 0.5, channels)[:, None]).astype(
        np.float32
    )


def test_writer_then_reader_round_trips(tmp_path):
    path = tmp_path / "out" / "tone.wav"
    data = _tone(2, 1000)
    writer = BlockWriter(path)
    for start in range(0, 1000, 256):
        writer.write(AudioBlock(np.ascontiguousarray(data[:, start : start + 256]), 48000))
    writer.close()
    assert writer.frames_written == 1000

    reader = FileBlockReader(path, 256)
    blocks = []
    while (block := reader.read_block()) is not None:
        blocks.append(block)
    reader.close()
    assert [b.frames for b in blocks] == [256, 256, 256, 232], "the last block is the remainder"
    assert (blocks[0].channels, blocks[0].sample_rate) == (2, 48000)
    np.testing.assert_array_equal(np.concatenate([b.data for b in blocks], axis=1), data)


def test_reader_loops(tmp_path):
    path = tmp_path / "short.wav"
    sf.write(str(path), _tone(1, 300).T, 44100, subtype="FLOAT")
    reader = FileBlockReader(path, 256, loop=True)
    frames = [reader.read_block().frames for _ in range(5)]
    reader.close()
    assert frames == [256, 44, 256, 44, 256]


def test_reader_of_empty_file_ends_even_when_looping(tmp_path):
    path = tmp_path / "empty.wav"
    sf.write(str(path), np.zeros((0, 1), np.float32), 48000, subtype="FLOAT")
    reader = FileBlockReader(path, 256, loop=True)
    assert reader.read_block() is None
    reader.close()


def test_writer_rejects_a_changed_format(tmp_path):
    writer = BlockWriter(tmp_path / "a.wav")
    writer.write(AudioBlock.silence(2, 8, 48000))
    with pytest.raises(ValueError, match="2 ch at 48000 Hz"):
        writer.write(AudioBlock.silence(1, 8, 48000))
    writer.close()


def test_writer_rejects_unknown_extension(tmp_path):
    with pytest.raises(ValueError, match="unknown audio format"):
        BlockWriter(tmp_path / "a.xyz").write(AudioBlock.silence(1, 8, 48000))
