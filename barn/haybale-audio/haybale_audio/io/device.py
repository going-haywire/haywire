"""Playing AudioBlocks on a sound device."""

from collections.abc import Callable
from typing import Any, Protocol

import numpy as np

from haybale_audio.dsp.channels import fit
from haybale_audio.dsp.fifo import FrameFifo
from haybale_audio.dsp.resample import DriftController, StreamResampler
from haybale_audio.value import AudioBlock

#: Called on the device's thread with ``(outdata, frames, time, status)``; ``outdata`` is (frames, channels).
StreamCallback = Callable[[np.ndarray, int, Any, Any], None]


class OutputStream(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...


class OutputBackend(Protocol):
    def device_info(self, device: str | int | None) -> tuple[int, int]:
        """Return the device's default sample rate and its output channel count."""
        ...

    def open(
        self, device: str | int | None, sample_rate: int, channels: int, callback: StreamCallback
    ) -> OutputStream: ...


class SoundDeviceBackend:
    """Output through PortAudio; ``sounddevice`` loads on first use."""

    def device_info(self, device: str | int | None) -> tuple[int, int]:
        import sounddevice as sd

        info = sd.query_devices(device, "output")
        return int(info["default_samplerate"]), int(info["max_output_channels"])

    def open(
        self, device: str | int | None, sample_rate: int, channels: int, callback: StreamCallback
    ) -> OutputStream:
        import sounddevice as sd

        return sd.OutputStream(
            device=device, samplerate=sample_rate, channels=channels, dtype="float32", callback=callback
        )


class DeviceOutput:
    """Plays the blocks passed to ``write`` on an output device.

    The first block opens the stream at the device's sample rate and fits it to the device's
    channels. Playback starts once ``prefill_blocks`` blocks are queued and restarts after an
    underrun. Blocks are resampled to the device rate, with a drift controller holding the queue
    at the prefill depth so the producer's and the device's clocks may differ slightly.
    """

    def __init__(
        self,
        device: str | int | None = None,
        prefill_blocks: int = 4,
        backend: OutputBackend | None = None,
    ) -> None:
        if prefill_blocks <= 0:
            raise ValueError(f"prefill_blocks must be positive, got {prefill_blocks}")
        self._device = device
        self._prefill_blocks = prefill_blocks
        self._backend: OutputBackend = backend or SoundDeviceBackend()
        self._stream: OutputStream | None = None
        self._fifo: FrameFifo | None = None
        self._resampler: StreamResampler | None = None
        self._drift: DriftController | None = None
        self._channels = 0
        self._target = 0
        self._playing = False
        self.sample_rate = 0
        self.underruns = 0  # restarts after the queue ran dry

    @property
    def running(self) -> bool:
        return self._stream is not None

    @property
    def depth(self) -> int:
        """Frames queued for the device."""
        return self._fifo.depth if self._fifo is not None else 0

    @property
    def overruns(self) -> int:
        """Frames dropped because the queue was full."""
        return self._fifo.overruns if self._fifo is not None else 0

    @property
    def channels(self) -> int:
        return self._channels

    def write(self, block: AudioBlock) -> None:
        """Queue ``block`` for playback, opening the device on the first call."""
        if self._stream is None:
            self._open(block)
        assert self._fifo is not None and self._resampler is not None and self._drift is not None
        trim = self._drift.update(self._fifo.depth) if self._playing else 0.0
        converted = self._resampler.process(block, trim)
        if converted is not None:
            self._fifo.push(fit(converted.data, self._channels))

    def close(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        self._playing = False

    def _open(self, block: AudioBlock) -> None:
        rate, max_channels = self._backend.device_info(self._device)
        self.sample_rate = rate
        # A mono block plays on both speakers of a stereo device.
        self._channels = max(1, min(max(block.channels, 2), max_channels))
        self._target = max(1, round(block.frames * rate / block.sample_rate)) * self._prefill_blocks
        self._fifo = FrameFifo(self._channels, self._target * 4)
        self._resampler = StreamResampler(rate)
        self._drift = DriftController(self._target)
        self._playing = False
        self._stream = self._backend.open(self._device, rate, self._channels, self._callback)
        self._stream.start()

    def _callback(self, outdata: np.ndarray, frames: int, time: Any, status: Any) -> None:
        fifo = self._fifo
        if fifo is None:
            outdata.fill(0)
            return
        if not self._playing:
            if fifo.depth < self._target:
                outdata.fill(0)
                return
            self._playing = True
        before = fifo.underruns
        outdata[:] = fifo.pop(frames).T
        if fifo.underruns != before:
            self.underruns += 1
            self._playing = False
