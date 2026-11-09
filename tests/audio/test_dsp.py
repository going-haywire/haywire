"""Reblocker, StreamResampler, DriftController and the channel operations."""

import numpy as np
import pytest

from haybale_audio.dsp import channels
from haybale_audio.dsp.reblock import Reblocker
from haybale_audio.dsp.resample import DriftController, StreamResampler
from haybale_audio.value import AudioBlock

pytestmark = pytest.mark.unit


def _ramp(ch: int, frames: int, start: int = 0) -> AudioBlock:
    row = np.arange(start, start + frames, dtype=np.float32)
    return AudioBlock(np.stack([row * (c + 1) for c in range(ch)]), 48000)


class TestReblocker:
    def test_keeps_every_frame_in_order(self):
        rb = Reblocker(256)
        sizes = [100, 300, 17, 1024, 5]
        out, start = [], 0
        for n in sizes:
            out += rb.push(_ramp(2, n, start))
            start += n
        total = sum(sizes)
        assert [b.frames for b in out] == [256] * (total // 256)
        assert rb.pending_frames == total % 256
        joined = np.concatenate([b.data for b in out], axis=1)
        np.testing.assert_array_equal(joined[0], np.arange(joined.shape[1], dtype=np.float32))

    def test_input_larger_than_block_yields_several(self):
        assert len(Reblocker(64).push(_ramp(1, 640))) == 10

    def test_held_frames_do_not_alias_the_input(self):
        rb = Reblocker(256)
        block = _ramp(1, 100)
        rb.push(block)
        assert not np.shares_memory(rb._held, block.data)

    def test_format_change_discards_old_frames(self):
        rb = Reblocker(256)
        rb.push(_ramp(2, 100))
        out = rb.push(_ramp(1, 256))
        assert [(b.channels, b.frames) for b in out] == [(1, 256)]
        assert rb.pending_frames == 0

    def test_rejects_bad_size(self):
        with pytest.raises(ValueError, match="block_size"):
            Reblocker(0)


class TestStreamResampler:
    def test_converts_rate_and_length(self):
        rs = StreamResampler(48000)
        tone = np.sin(2 * np.pi * 1000 * np.arange(44100) / 44100).astype(np.float32)[None, :]
        frames = 0
        for i in range(0, 44100 - 441, 441):
            out = rs.process(AudioBlock(np.ascontiguousarray(tone[:, i : i + 441]), 44100))
            if out is not None:
                assert out.sample_rate == 48000
                frames += out.frames
        assert frames == pytest.approx(48000 * (44100 - 441) / 44100, abs=200), "converter latency only"

    def test_same_rate_passes_a_tone_through(self):
        rs = StreamResampler(48000)
        tone = np.sin(2 * np.pi * 1000 * np.arange(48000) / 48000).astype(np.float32)
        out = [
            rs.process(AudioBlock(tone[None, i : i + 256].copy(), 48000)) for i in range(0, 48000 - 256, 256)
        ]
        y = np.concatenate([b.data[0] for b in out if b is not None])
        assert np.max(np.abs(np.diff(y[2000:]))) == pytest.approx(2 * np.pi * 1000 / 48000, rel=0.01), (
            "a click would show as a larger step"
        )

    def test_positive_trim_makes_fewer_frames(self):
        def frames(trim: float) -> int:
            rs, total = StreamResampler(48000), 0
            for _ in range(200):
                out = rs.process(AudioBlock.silence(1, 256, 48000), trim)
                total += out.frames if out else 0
            return total

        assert frames(0.01) < frames(0.0) < frames(-0.01)

    def test_format_change_restarts_conversion(self):
        rs = StreamResampler(48000)
        rs.process(AudioBlock.silence(2, 256, 48000))
        out = rs.process(AudioBlock.silence(1, 256, 48000))
        assert out is None or out.channels == 1

    def test_rejects_bad_rate(self):
        with pytest.raises(ValueError, match="target_rate"):
            StreamResampler(0)


class TestDriftControllerLimits:
    def test_trim_is_limited_however_far_the_queue_is_off(self):
        ctl = DriftController(1024, max_trim=1e-3)
        for _ in range(5000):
            trim = ctl.update(100_000)
        assert trim == pytest.approx(1e-3)

    def test_the_integral_unwinds_within_seconds_after_a_long_excess(self):
        ctl = DriftController(1024)
        for _ in range(5000):
            ctl.update(100_000)  # a queue far above target for 27 s of blocks
        trims = [ctl.update(0) for _ in range(600)]  # then empty for three seconds of blocks
        assert trims[-1] < 0, "the controller has turned around within three seconds"

    def test_reset_forgets_the_history(self):
        ctl = DriftController(1024)
        for _ in range(1000):
            ctl.update(5000)
        ctl.reset()
        assert ctl.update(1024) == 0.0


class TestDriftController:
    def test_trim_sign_follows_depth(self):
        ctl = DriftController(1024)
        assert ctl.update(2048) > 0, "too deep: fewer frames out"
        ctl.reset()
        assert ctl.update(512) < 0

    @pytest.mark.parametrize("offset", [200e-6, -200e-6], ids=["fast producer", "slow producer"])
    def test_holds_depth_against_a_clock_offset(self, offset):
        """Closed loop in simulated time, as spike S9: no underrun, trim settles on the offset."""
        n, rate, target = 256, 48000, 1024
        rs, ctl = StreamResampler(rate), DriftController(target)
        depth, trim, in_clock, primed = 0.0, 0.0, 0.0, False
        trims, depths = [], []
        for tick in range(1, int(180 * rate / n)):
            while in_clock <= tick * n / rate:
                out = rs.process(AudioBlock.silence(1, n, rate), trim)
                depth += out.frames if out else 0
                in_clock += n / (rate * (1 + offset))
                trim = ctl.update(int(depth))
            primed = primed or depth >= target  # the consumer starts once the FIFO is prefilled
            if primed:
                assert depth >= n, f"underrun at tick {tick}"
                depth -= n
                trims.append(trim)
                depths.append(depth)
        assert max(depths) < 16 * n, "overrun"
        assert np.mean(trims[-int(30 * rate / n) :]) == pytest.approx(offset, rel=0.15)


class TestChannels:
    def test_select_reorders_and_repeats(self):
        out = channels.select(_ramp(3, 4), [2, 0, 0])
        assert out.channels == 3
        np.testing.assert_array_equal(out.data[0], _ramp(3, 4).data[2])
        np.testing.assert_array_equal(out.data[1], out.data[2])

    def test_select_rejects_missing_channel(self):
        with pytest.raises(ValueError, match="channel 2 does not exist"):
            channels.select(_ramp(2, 4), [0, 2])

    def test_select_rejects_empty(self):
        with pytest.raises(ValueError, match="no channels"):
            channels.select(_ramp(2, 4), [])

    def test_split_then_merge_is_identity(self):
        block = _ramp(4, 16)
        np.testing.assert_array_equal(channels.merge(channels.split(block)).data, block.data)

    def test_merge_rejects_mismatch(self):
        with pytest.raises(ValueError, match="blocks differ"):
            channels.merge([_ramp(1, 8), _ramp(1, 9)])

    def test_merge_rejects_nothing(self):
        with pytest.raises(ValueError, match="nothing to merge"):
            channels.merge([])

    def test_to_mono_averages(self):
        out = channels.to_mono(AudioBlock(np.array([[1.0, 1.0], [3.0, -1.0]], np.float32), 48000))
        np.testing.assert_array_equal(out.data, [[2.0, 0.0]])


class TestParseChannels:
    @pytest.mark.parametrize(
        ("spec", "expected"),
        [("0", [0]), ("1, 0", [1, 0]), ("0,0", [0, 0]), ("2-3", [2, 3]), ("0, 2-4, 7", [0, 2, 3, 4, 7])],
    )
    def test_parses(self, spec, expected):
        assert channels.parse_channels(spec) == expected

    @pytest.mark.parametrize(
        ("spec", "message"),
        [("", "no channels"), (" , ", "no channels"), ("a", "not a channel"), ("3-1", "backwards")],
    )
    def test_rejects(self, spec, message):
        with pytest.raises(ValueError, match=message):
            channels.parse_channels(spec)
