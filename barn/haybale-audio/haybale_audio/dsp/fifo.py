"""A thread-safe queue of audio frames between a producer and a pulling consumer."""

import threading
from collections import deque

import numpy as np


class FrameFifo:
    """Holds up to ``capacity`` frames of ``channels`` channels.

    ``push`` drops the oldest frames when full and counts them in ``overruns``; ``pop`` pads with
    silence when short and counts the missing frames in ``underruns``.
    """

    def __init__(self, channels: int, capacity: int) -> None:
        if channels <= 0 or capacity <= 0:
            raise ValueError(f"channels and capacity must be positive, got {channels} and {capacity}")
        self.channels = channels
        self.capacity = capacity
        self.overruns = 0
        self.underruns = 0
        self._chunks: deque[np.ndarray] = deque()
        self._depth = 0
        self._lock = threading.Lock()

    @property
    def depth(self) -> int:
        """Frames currently held."""
        return self._depth

    def push(self, data: np.ndarray) -> None:
        with self._lock:
            self._chunks.append(data)
            self._depth += data.shape[1]
            excess = self._depth - self.capacity
            if excess > 0:
                self._discard(excess)
                self.overruns += excess

    def pop(self, frames: int) -> np.ndarray:
        """Return (channels, ``frames``) float32, silence-padded when fewer frames are held."""
        out = np.zeros((self.channels, frames), dtype=np.float32)
        with self._lock:
            filled = 0
            while filled < frames and self._chunks:
                chunk = self._chunks[0]
                take = min(frames - filled, chunk.shape[1])
                out[:, filled : filled + take] = chunk[:, :take]
                if take == chunk.shape[1]:
                    self._chunks.popleft()
                else:
                    self._chunks[0] = chunk[:, take:]
                filled += take
            self._depth -= filled
            self.underruns += frames - filled
        return out

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._depth = 0

    def _discard(self, frames: int) -> None:
        while frames > 0 and self._chunks:
            chunk = self._chunks[0]
            if chunk.shape[1] <= frames:
                frames -= chunk.shape[1]
                self._depth -= chunk.shape[1]
                self._chunks.popleft()
            else:
                self._chunks[0] = chunk[:, frames:]
                self._depth -= frames
                frames = 0
