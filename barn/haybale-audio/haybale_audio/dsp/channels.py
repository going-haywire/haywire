"""Channel operations on AudioBlocks."""

from collections.abc import Sequence

import numpy as np

from haybale_audio.value import AudioBlock


def select(block: AudioBlock, channels: Sequence[int]) -> AudioBlock:
    """Return a block of the given channels, in that order. A channel may repeat.

    Raises:
        ValueError: ``channels`` is empty or names a channel the block does not have.
    """
    if not channels:
        raise ValueError("no channels selected")
    bad = [c for c in channels if not 0 <= c < block.channels]
    if bad:
        raise ValueError(f"channel {bad[0]} does not exist in a {block.channels}-channel block")
    return AudioBlock(np.ascontiguousarray(block.data[list(channels)]), block.sample_rate)


def split(block: AudioBlock) -> list[AudioBlock]:
    """Return one single-channel block per channel."""
    return [select(block, [c]) for c in range(block.channels)]


def merge(blocks: Sequence[AudioBlock]) -> AudioBlock:
    """Stack single- or multi-channel blocks into one block, in order.

    Raises:
        ValueError: ``blocks`` is empty, or the blocks differ in sample rate or frame count.
    """
    if not blocks:
        raise ValueError("nothing to merge")
    first = blocks[0]
    for other in blocks[1:]:
        if (other.sample_rate, other.frames) != (first.sample_rate, first.frames):
            raise ValueError(
                f"blocks differ: {first.frames} frames at {first.sample_rate} Hz "
                f"against {other.frames} frames at {other.sample_rate} Hz"
            )
    return AudioBlock(np.concatenate([b.data for b in blocks], axis=0), first.sample_rate)


def to_mono(block: AudioBlock) -> AudioBlock:
    """Return the average of all channels as one channel."""
    return AudioBlock(
        np.ascontiguousarray(block.data.mean(axis=0, keepdims=True, dtype=np.float32)), block.sample_rate
    )
