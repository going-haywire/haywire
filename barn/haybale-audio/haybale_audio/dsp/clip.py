"""ClipBuffer — gathers the blocks of an audio flow into one clip."""

from __future__ import annotations

import threading

import numpy as np

from haybale_audio.value import AudioBlock


class ClipBuffer:
    """Appends blocks until :meth:`take` returns them as one block; safe across threads.

    The first block fixes the channel count and sample rate; a later block that differs
    is an error. Blocks past ``max_seconds`` are dropped and counted.
    """

    def __init__(self, max_seconds: float) -> None:
        self.max_seconds = max_seconds
        self._lock = threading.Lock()
        self._blocks: list[np.ndarray] = []
        self._format: tuple[int, int] | None = None
        self._frames = 0
        self.dropped = 0

    @property
    def seconds(self) -> float:
        """Length of the audio gathered so far."""
        with self._lock:
            return self._frames / self._format[1] if self._format else 0.0

    def add(self, block: AudioBlock) -> bool:
        """Append *block*; return ``False`` if the clip is full and the block was dropped.

        Raises:
            ValueError: *block* has another channel count or sample rate than the first.
        """
        fmt = (block.channels, block.sample_rate)
        with self._lock:
            if self._format is None:
                self._format = fmt
            elif fmt != self._format:
                raise ValueError(
                    f"block is {block.channels} ch at {block.sample_rate} Hz, but the clip is "
                    f"{self._format[0]} ch at {self._format[1]} Hz"
                )
            if (self._frames + block.frames) / block.sample_rate > self.max_seconds:
                self.dropped += 1
                return False
            self._blocks.append(block.data)
            self._frames += block.frames
            return True

    def take(self) -> AudioBlock | None:
        """Return the gathered audio as one block and start a new clip; ``None`` if empty."""
        with self._lock:
            blocks, fmt = self._blocks, self._format
            self._blocks, self._format, self._frames, self.dropped = [], None, 0, 0
        if not blocks or fmt is None:
            return None
        return AudioBlock(np.concatenate(blocks, axis=1), fmt[1])
