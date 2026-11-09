"""Summing audio into one block."""

from collections.abc import Sequence

import numpy as np

from haybale_audio.dsp.channels import fit


def mix(parts: Sequence[tuple[np.ndarray, float]], channels: int, frames: int) -> np.ndarray:
    """Return the sum of ``parts`` as a (``channels``, ``frames``) array.

    Each part is a (channels, frames) array with its gain.

    A part with fewer channels is repeated or padded to ``channels``. The sum is not limited, so it can
    exceed ±1.
    """
    out = np.zeros((channels, frames), dtype=np.float32)
    for data, gain in parts:
        out += fit(data, channels) * np.float32(gain)
    return out
