"""ClipBuffer and Segmenter: gathering blocks into clips, and cutting a stream at its pauses."""

from __future__ import annotations

import numpy as np
import pytest

from haybale_audio.dsp.clip import ClipBuffer
from haybale_audio.dsp.segmenter import Segment, Segmenter, rms
from haybale_audio.value import AudioBlock

RATE = 48000
BLOCK = 480  # 10 ms at 48 kHz, so lengths read as whole blocks


def _tone(blocks: int = 1, channels: int = 1, amplitude: float = 0.1) -> list[AudioBlock]:
    out = []
    for n in range(blocks):
        t = (np.arange(BLOCK) + n * BLOCK) / RATE
        wave = (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        out.append(AudioBlock(np.tile(wave, (channels, 1)), RATE))
    return out


def _silence(blocks: int = 1, channels: int = 1, level: float = 0.0) -> list[AudioBlock]:
    return [AudioBlock(np.full((channels, BLOCK), level, np.float32), RATE) for _ in range(blocks)]


def _feed(segmenter: Segmenter, blocks: list[AudioBlock]) -> list[Segment]:
    return [s for s in (segmenter.feed(b) for b in blocks) if s is not None]


@pytest.mark.unit
def test_rms_of_a_tone_and_of_silence() -> None:
    assert rms(_tone(amplitude=0.1)[0]) == pytest.approx(0.1 / np.sqrt(2), rel=0.01)
    assert rms(_silence()[0]) == 0.0
    assert rms(AudioBlock(np.zeros((1, 0), np.float32), RATE)) == 0.0


@pytest.mark.unit
def test_a_pause_of_the_hangover_ends_the_segment_without_the_pause() -> None:
    seg = Segmenter(threshold=0.01, hangover=0.1, preroll=0.0, min_length=0.0)
    out = _feed(seg, _silence(5) + _tone(30) + _silence(9))
    assert out == []
    assert seg.speaking
    (segment,) = _feed(seg, _silence(1))  # the 10th silent block: 100 ms
    assert segment.audio.frames == 30 * BLOCK  # the tone only, the pause left out
    assert segment.start == pytest.approx(5 * BLOCK / RATE)
    assert not seg.speaking
    assert seg.sent == 1


@pytest.mark.unit
def test_a_pause_shorter_than_the_hangover_stays_in_the_segment() -> None:
    seg = Segmenter(threshold=0.01, hangover=0.1, preroll=0.0, min_length=0.0)
    (segment,) = _feed(seg, _tone(20) + _silence(5) + _tone(20) + _silence(10))
    assert segment.audio.frames == 45 * BLOCK
    assert np.allclose(segment.audio.data[:, 20 * BLOCK : 25 * BLOCK], 0.0)


@pytest.mark.unit
def test_the_preroll_keeps_the_blocks_before_the_first_loud_one() -> None:
    seg = Segmenter(threshold=0.01, hangover=0.1, preroll=0.05, min_length=0.0)
    quiet = _silence(20, level=0.005)  # below the threshold, like a soft onset
    (segment,) = _feed(seg, quiet + _tone(30) + _silence(10))
    assert segment.audio.frames == (5 + 30) * BLOCK  # 50 ms of pre-roll
    assert np.allclose(segment.audio.data[:, : 5 * BLOCK], 0.005)
    assert segment.start == pytest.approx(15 * BLOCK / RATE)


@pytest.mark.unit
def test_sound_shorter_than_the_minimum_is_discarded() -> None:
    seg = Segmenter(threshold=0.01, hangover=0.1, preroll=0.05, min_length=0.2)
    # 15 tone blocks are 150 ms: with the 50 ms pre-roll the clip would reach 200 ms, but the
    # minimum counts the sound alone.
    assert _feed(seg, _silence(10) + _tone(15) + _silence(10)) == []
    assert seg.discarded == 1
    (segment,) = _feed(seg, _tone(20) + _silence(10))
    assert segment.audio.frames == (5 + 20) * BLOCK
    assert seg.sent == 1


@pytest.mark.unit
def test_a_segment_reaching_the_maximum_is_sent_and_the_sound_goes_on_in_a_new_one() -> None:
    seg = Segmenter(threshold=0.01, hangover=0.1, preroll=0.0, min_length=0.0, max_length=0.5)
    first, second = _feed(seg, _tone(80) + _silence(10))
    assert first.audio.frames == 50 * BLOCK
    assert second.audio.frames == 30 * BLOCK
    assert second.start == pytest.approx(0.5)


@pytest.mark.unit
def test_a_block_of_another_rate_is_an_error_and_reset_starts_over() -> None:
    seg = Segmenter()
    seg.feed(_tone()[0])
    with pytest.raises(ValueError, match="16000 Hz"):
        seg.feed(AudioBlock(np.zeros((1, 160), np.float32), 16000))
    seg.reset()
    assert not seg.speaking
    assert seg.sent == 0
    seg.feed(AudioBlock(np.zeros((1, 160), np.float32), 16000))  # a new stream takes a new rate


@pytest.mark.unit
def test_cut_ends_the_open_segment_and_is_none_without_one() -> None:
    seg = Segmenter(threshold=0.01, hangover=0.1, preroll=0.0, min_length=0.0)
    assert seg.cut() is None
    _feed(seg, _tone(20) + _silence(3))
    segment = seg.cut()
    assert segment is not None
    assert segment.audio.frames == 20 * BLOCK  # the pause left out
    assert not seg.speaking
    assert seg.sent == 1
    assert seg.cut() is None


def _block(channels: int, frames: int, rate: int, value: float = 0.0) -> AudioBlock:
    return AudioBlock(np.full((channels, frames), value, np.float32), rate)


@pytest.mark.unit
def test_clip_buffer_joins_blocks_and_starts_over() -> None:
    buffer = ClipBuffer(max_seconds=10)
    assert buffer.take() is None
    assert buffer.add(_block(2, 100, 1000, 0.1))
    assert buffer.add(_block(2, 50, 1000, 0.2))
    assert buffer.seconds == pytest.approx(0.15)
    clip = buffer.take()
    assert clip is not None
    assert (clip.channels, clip.frames, clip.sample_rate) == (2, 150, 1000)
    assert np.allclose(clip.data[:, 100:], 0.2)
    assert buffer.take() is None
    assert buffer.add(_block(1, 10, 8000))  # a new clip takes a new format


@pytest.mark.unit
def test_clip_buffer_refuses_another_format() -> None:
    buffer = ClipBuffer(max_seconds=10)
    buffer.add(_block(1, 100, 16000))
    with pytest.raises(ValueError, match="1 ch at 16000 Hz"):
        buffer.add(_block(1, 100, 48000))


@pytest.mark.unit
def test_clip_buffer_drops_blocks_past_the_limit() -> None:
    buffer = ClipBuffer(max_seconds=0.25)
    assert buffer.add(_block(1, 200, 1000))
    assert not buffer.add(_block(1, 100, 1000))
    assert buffer.dropped == 1
    clip = buffer.take()
    assert clip is not None
    assert clip.frames == 200
    assert buffer.dropped == 0


@pytest.mark.unit
def test_the_postroll_keeps_the_start_of_the_closing_pause() -> None:
    seg = Segmenter(threshold=0.01, hangover=0.1, preroll=0.0, min_length=0.0, postroll=0.035)
    (segment,) = _feed(seg, _tone(30) + _silence(10))
    assert segment.audio.frames == 30 * BLOCK + int(0.035 * RATE)  # 3.5 blocks of the pause
    assert np.allclose(segment.audio.data[:, 30 * BLOCK :], 0.0)


@pytest.mark.unit
def test_the_postroll_does_not_count_towards_the_minimum() -> None:
    seg = Segmenter(threshold=0.01, hangover=0.1, preroll=0.0, min_length=0.2, postroll=0.1)
    assert _feed(seg, _tone(15) + _silence(10)) == []  # 150 ms of sound, 250 ms with the post-roll
    assert seg.discarded == 1
