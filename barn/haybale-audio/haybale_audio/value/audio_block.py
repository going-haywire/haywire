"""AudioBlock — one block of planar float32 samples."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, eq=False)
class AudioBlock:
    """Samples shaped ``(channels, frames)``, float32, with the rate they were taken at.

    The array is read-only: a block fans out to several nodes by reference, so none may
    change it. Block size and sample rate vary per block; a node that needs uniform input
    checks it, and a Reblock/Resample node fixes a mismatch.
    """

    data: np.ndarray
    sample_rate: int

    def __post_init__(self) -> None:
        if self.data.ndim != 2 or self.data.dtype != np.float32:
            raise ValueError(
                f"AudioBlock needs (channels, frames) float32, got {self.data.dtype} {self.data.shape}"
            )
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")
        self.data.flags.writeable = False

    @property
    def channels(self) -> int:
        return self.data.shape[0]

    @property
    def frames(self) -> int:
        return self.data.shape[1]

    @property
    def duration(self) -> float:
        """Length in seconds."""
        return self.frames / self.sample_rate

    @classmethod
    def silence(cls, channels: int, frames: int, sample_rate: int) -> "AudioBlock":
        return cls(np.zeros((channels, frames), np.float32), sample_rate)
