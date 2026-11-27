"""Segmenter — cuts a stream of audio blocks into clips at the pauses."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from haybale_audio.dsp.clip import ClipBuffer
from haybale_audio.value import AudioBlock


def rms(block: AudioBlock) -> float:
    """Return the root mean square of *block* over all its channels; 0 for an empty block."""
    if block.data.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(block.data, dtype=np.float64))))


@dataclass
class Segment:
    """A finished segment: the audio as it arrived, and where it starts in the stream."""

    audio: AudioBlock
    start: float  # seconds since the first block the segmenter saw

    @property
    def duration(self) -> float:
        return self.audio.duration


class Segmenter:
    """Cuts blocks into segments: a loud block starts or extends one, a pause ends it.

    A block is loud when its RMS is above ``threshold``. The first loud block opens a segment,
    with up to ``preroll`` seconds of the blocks before it, so a quiet onset is kept. From then on
    every block is appended; ``hangover`` seconds of silence end the segment. Of that trailing
    silence the first ``postroll`` seconds are kept, so a soft ending is not cut off, and the rest
    is left out. A segment whose audio from its first loud block to its last is shorter than
    ``min_length`` is discarded and counted; one that reaches ``max_length`` is sent at once and
    the next loud block opens a new one.

    The first block fixes the channel count and sample rate; a later block that differs is an
    error, as in :class:`ClipBuffer`. Not thread-safe: one flow feeds it.
    """

    def __init__(
        self,
        threshold: float = 0.01,
        hangover: float = 0.5,
        preroll: float = 0.2,
        min_length: float = 0.3,
        max_length: float = 30.0,
        postroll: float = 0.0,
    ) -> None:
        self.threshold = threshold
        self.hangover = hangover
        self.preroll = preroll
        self.postroll = postroll
        self.min_length = min_length
        self.max_length = max_length
        self.level = 0.0  # RMS of the last block
        self.sent = 0
        self.discarded = 0
        self._buffer = ClipBuffer(float("inf"))
        self._before: deque[AudioBlock] = deque()  # pre-roll candidates while no segment is open
        self._before_frames = 0
        self._silence: list[AudioBlock] = []  # silence inside an open segment, not yet appended
        self._silence_frames = 0
        self._open = False
        self._lead_frames = 0  # pre-roll frames at the start of the open segment
        self._start_frame = 0  # stream frame where the open segment starts
        self._frames = 0  # frames seen so far
        self._rate = 0

    @property
    def speaking(self) -> bool:
        """Whether a segment is open."""
        return self._open

    @property
    def seconds(self) -> float:
        """Length of the open segment so far, its pending silence included."""
        if not self._open or not self._rate:
            return 0.0
        return self._buffer.seconds + self._silence_frames / self._rate

    def cut(self) -> Segment | None:
        """End the open segment now, as a pause would; None when none is open or it is too short."""
        if not self._open:
            return None
        return self._end()

    def reset(self) -> None:
        """Drop the open segment and the pre-roll; the counters and the stream time start over."""
        self._buffer.take()
        self._before.clear()
        self._silence.clear()
        self._before_frames = self._silence_frames = self._lead_frames = 0
        self._open = False
        self._frames = self._start_frame = self._rate = 0
        self.sent = self.discarded = 0
        self.level = 0.0

    def feed(self, block: AudioBlock) -> Segment | None:
        """Take the next block; return the segment it finishes, if any.

        Raises:
            ValueError: *block* has another channel count or sample rate than the first.
        """
        if self._rate and block.sample_rate != self._rate:
            raise ValueError(f"block is at {block.sample_rate} Hz, but the stream is at {self._rate} Hz")
        self._rate = block.sample_rate
        self.level = rms(block)
        loud = self.level > self.threshold
        position = self._frames
        self._frames += block.frames
        if not self._open:
            if not loud:
                self._remember(block)
                return None
            self._begin(block, position)
        elif loud:
            for pause in self._silence:
                self._buffer.add(pause)
            self._silence.clear()
            self._silence_frames = 0
            self._buffer.add(block)
        else:
            self._silence.append(block)
            self._silence_frames += block.frames
            if self._silence_frames / self._rate >= self.hangover:
                return self._end()
            return None
        if self._buffer.seconds >= self.max_length:
            return self._end()
        return None

    def _keep_postroll(self, pause: list[AudioBlock]) -> int:
        """Append the first ``postroll`` seconds of ``pause`` to the open segment; return its frames."""
        left = int(round(max(0.0, self.postroll) * self._rate)) if self._rate else 0
        kept = 0
        for block in pause:
            if left <= 0:
                break
            part = (
                block if block.frames <= left else AudioBlock(block.data[:, :left].copy(), block.sample_rate)
            )
            self._buffer.add(part)
            kept += part.frames
            left -= part.frames
        return kept

    def _remember(self, block: AudioBlock) -> None:
        self._before.append(block)
        self._before_frames += block.frames
        limit = self.preroll * block.sample_rate
        while self._before and self._before_frames > limit:
            self._before_frames -= self._before.popleft().frames

    def _begin(self, block: AudioBlock, position: int) -> None:
        self._open = True
        self._lead_frames = self._before_frames
        self._start_frame = position - self._before_frames
        for earlier in self._before:
            self._buffer.add(earlier)
        self._before.clear()
        self._before_frames = 0
        self._buffer.add(block)

    def _end(self) -> Segment | None:
        pause, self._silence, self._silence_frames = self._silence, [], 0
        tail = self._keep_postroll(pause)
        audio = self._buffer.take()
        for block in pause:  # the whole pause is the next segment's pre-roll
            self._remember(block)
        self._open = False
        if audio is None:
            return None
        if (audio.frames - self._lead_frames - tail) / audio.sample_rate < self.min_length:
            self.discarded += 1
            return None
        self.sent += 1
        return Segment(audio, self._start_frame / audio.sample_rate)
