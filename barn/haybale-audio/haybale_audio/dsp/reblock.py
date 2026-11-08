"""Reblocker — turns blocks of any size into blocks of one fixed size."""

import numpy as np

from haybale_audio.value import AudioBlock


class Reblocker:
    """Collects frames and hands out blocks of exactly ``block_size`` frames.

    Input blocks must keep one channel count and sample rate; the first block after a change
    discards the frames still held, which belong to the old format.
    """

    def __init__(self, block_size: int) -> None:
        if block_size <= 0:
            raise ValueError(f"block_size must be positive, got {block_size}")
        self.block_size = block_size
        self._held: np.ndarray | None = None
        self._rate = 0

    @property
    def pending_frames(self) -> int:
        return 0 if self._held is None else self._held.shape[1]

    def push(self, block: AudioBlock) -> list[AudioBlock]:
        """Add ``block`` and return every complete block now available, in order."""
        held = self._held
        if held is None or held.shape[0] != block.channels or self._rate != block.sample_rate:
            held = np.zeros((block.channels, 0), np.float32)
            self._rate = block.sample_rate
        data = np.concatenate([held, block.data], axis=1) if held.shape[1] else block.data
        whole = data.shape[1] // self.block_size
        out = [
            AudioBlock(
                np.ascontiguousarray(data[:, i * self.block_size : (i + 1) * self.block_size]), self._rate
            )
            for i in range(whole)
        ]
        self._held = np.array(data[:, whole * self.block_size :])  # a copy, not a view of the input
        return out

    def reset(self) -> None:
        self._held = None
