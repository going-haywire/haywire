"""A jitter buffer that turns blocks of any rate and size into frames at a fixed rate."""

import numpy as np

from haybale_audio.dsp.channels import fit
from haybale_audio.dsp.fifo import FrameFifo
from haybale_audio.dsp.resample import DriftController, StreamResampler
from haybale_audio.value import AudioBlock


class PullBuffer:
    """Queues blocks written by a producer and hands out frames to a consumer that pulls at its own pace.

    Blocks are converted to ``sample_rate`` and fitted to ``channels``. The drift controller adjusts
    the conversion ratio to hold the queue at ``prefill_blocks`` blocks of ``block_frames`` frames, so
    the producer's and the consumer's clocks may differ slightly. ``read`` returns ``None`` until the
    prefill is queued, and again after the queue runs dry.

    ``write`` and ``read`` may run on different threads.
    """

    def __init__(self, sample_rate: int, channels: int, block_frames: int, prefill_blocks: int = 4) -> None:
        if prefill_blocks <= 0 or block_frames <= 0:
            raise ValueError(
                f"prefill_blocks and block_frames must be positive, got {prefill_blocks} and {block_frames}"
            )
        self.sample_rate = sample_rate
        self.channels = channels
        self.target = block_frames * prefill_blocks
        self.restarts = 0  # times the queue ran dry
        self._fifo = FrameFifo(channels, self.target * 4)
        self._resampler = StreamResampler(sample_rate)
        self._drift = DriftController(self.target)
        self._playing = False

    @property
    def depth(self) -> int:
        """Frames queued."""
        return self._fifo.depth

    @property
    def overruns(self) -> int:
        """Frames dropped because the queue was full."""
        return self._fifo.overruns

    @property
    def playing(self) -> bool:
        return self._playing

    def write(self, block: AudioBlock) -> None:
        trim = self._drift.update(self._fifo.depth) if self._playing else 0.0
        converted = self._resampler.process(block, trim)
        if converted is not None:
            self._fifo.push(fit(converted.data, self.channels))

    def read(self, frames: int) -> np.ndarray | None:
        """Return (channels, ``frames``) float32, or ``None`` while the prefill is not queued.

        A read that finds fewer frames than asked is padded with silence and playback waits for the
        prefill again.
        """
        if not self._playing:
            if self._fifo.depth < self.target:
                return None
            self._playing = True
        before = self._fifo.underruns
        out = self._fifo.pop(frames)
        if self._fifo.underruns != before:
            self.restarts += 1
            self._playing = False
        return out
