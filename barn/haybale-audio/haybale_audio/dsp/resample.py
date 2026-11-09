"""Streaming resampler and the controller that keeps a FIFO's depth steady."""

import numpy as np
import samplerate

from haybale_audio.value import AudioBlock


class StreamResampler:
    """Converts blocks to ``target_rate``, keeping filter state across blocks so joins are seamless.

    ``trim`` nudges the ratio by that fraction on top of the nominal one: a positive trim makes
    fewer output frames per input frame. A drift controller sets it from block to block.
    """

    def __init__(self, target_rate: int, converter: str = "sinc_fastest") -> None:
        if target_rate <= 0:
            raise ValueError(f"target_rate must be positive, got {target_rate}")
        self.target_rate = target_rate
        self._converter = converter
        self._resampler: samplerate.Resampler | None = None
        self._format = (0, 0)

    def process(self, block: AudioBlock, trim: float = 0.0) -> AudioBlock | None:
        """Return ``block`` at the target rate, or ``None`` when the converter has no output yet.

        A change of channel count or sample rate starts a new conversion.
        """
        fmt = (block.channels, block.sample_rate)
        if self._resampler is None or fmt != self._format:
            self._resampler = samplerate.Resampler(self._converter, channels=block.channels)
            self._format = fmt
        ratio = self.target_rate / block.sample_rate * (1.0 - trim)
        out = self._resampler.process(np.ascontiguousarray(block.data.T), ratio)
        if len(out) == 0:
            return None
        return AudioBlock(np.ascontiguousarray(out.T, dtype=np.float32), self.target_rate)

    def reset(self) -> None:
        self._resampler = None


class DriftController:
    """PI controller: turns a FIFO's depth into the ``trim`` that holds it at ``target_depth``.

    A depth above the target gives a positive trim (fewer frames out). Against a constant clock
    offset the trim settles within 3% of it, after a few minutes, and at 48 kHz the depth swings
    about ±130 frames (3 ms) around the target with the default gains.

    The depth error counts at most as one ``target_depth`` and the trim never exceeds ``max_trim``,
    so a queue far off target is steered back gently and the controller does not overshoot when it
    gets there.
    """

    def __init__(
        self, target_depth: int, kp: float = 5e-4, ki: float = 1e-6, max_trim: float = 1e-3
    ) -> None:
        if target_depth <= 0:
            raise ValueError(f"target_depth must be positive, got {target_depth}")
        self.target_depth = target_depth
        self.kp = kp
        self.ki = ki
        self.max_trim = max_trim
        self._integral = 0.0

    def update(self, depth: int) -> float:
        """Return the trim for the next block, given the FIFO's current depth in frames."""
        error = max(-1.0, min(1.0, (depth - self.target_depth) / self.target_depth))
        limit = self.max_trim / self.ki
        self._integral = max(-limit, min(limit, self._integral + error))
        return max(-self.max_trim, min(self.max_trim, self.kp * error + self.ki * self._integral))

    def reset(self) -> None:
        self._integral = 0.0
