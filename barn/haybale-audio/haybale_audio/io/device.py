"""Playing AudioBlocks on a sound device."""

from collections.abc import Callable
from typing import Any, Protocol

import numpy as np

from haybale_audio.dsp.buffer import PullBuffer
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
        self._buffer: PullBuffer | None = None
        self.sample_rate = 0
        self.channels = 0

    @property
    def running(self) -> bool:
        return self._stream is not None

    @property
    def depth(self) -> int:
        """Frames queued for the device."""
        return self._buffer.depth if self._buffer is not None else 0

    @property
    def overruns(self) -> int:
        """Frames dropped because the queue was full."""
        return self._buffer.overruns if self._buffer is not None else 0

    @property
    def underruns(self) -> int:
        """Times playback restarted after the queue ran dry."""
        return self._buffer.restarts if self._buffer is not None else 0

    def write(self, block: AudioBlock) -> None:
        """Queue ``block`` for playback, opening the device on the first call."""
        if self._buffer is None:
            self._open(block)
        assert self._buffer is not None
        self._buffer.write(block)

    def close(self) -> None:
        stream, self._stream = self._stream, None
        self._buffer = None
        if stream is not None:
            stream.stop()
            stream.close()

    def _open(self, block: AudioBlock) -> None:
        rate, max_channels = self._backend.device_info(self._device)
        self.sample_rate = rate
        # A mono block plays on both speakers of a stereo device.
        self.channels = max(1, min(max(block.channels, 2), max_channels))
        frames = max(1, round(block.frames * rate / block.sample_rate))
        self._buffer = PullBuffer(rate, self.channels, frames, self._prefill_blocks)
        self._stream = self._backend.open(self._device, rate, self.channels, self._callback)
        self._stream.start()

    def _callback(self, outdata: np.ndarray, frames: int, time: Any, status: Any) -> None:
        buffer = self._buffer
        data = buffer.read(frames) if buffer is not None else None
        if data is None:
            outdata.fill(0)
        else:
            outdata[:] = data.T
