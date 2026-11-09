"""Playing AudioBlocks on a sound device."""

import threading
from typing import Any, Protocol

import numpy as np

from haybale_audio.dsp.buffer import PullBuffer
from haybale_audio.value import AudioBlock

#: Frames written to the device at a time.
CHUNK_FRAMES = 256
#: Seconds the feeding thread sleeps while it waits for audio the device buffer can still bridge.
WAIT_SECONDS = 0.002


class OutputStream(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...

    @property
    def buffer_frames(self) -> int:
        """Frames the device holds ahead of playback when its buffer is full."""
        ...

    @property
    def write_available(self) -> int:
        """Frames the device can take without blocking."""
        ...

    def write(self, data: np.ndarray) -> bool:
        """Block until the device has room for ``data`` (frames, channels); return ``True`` if it ran dry."""
        ...


class OutputBackend(Protocol):
    def device_info(self, device: str | int | None) -> tuple[int, int]:
        """Return the device's default sample rate and its output channel count."""
        ...

    def open(
        self, device: str | int | None, sample_rate: int, channels: int, latency: float | None = None
    ) -> OutputStream:
        """Open a stream; ``latency`` is the device buffer in seconds, ``None`` for the device's default."""
        ...


class SoundDeviceBackend:
    """Output through PortAudio; ``sounddevice`` loads on first use."""

    def device_info(self, device: str | int | None) -> tuple[int, int]:
        import sounddevice as sd

        info = sd.query_devices(_index(device), "output")
        return int(info["default_samplerate"]), int(info["max_output_channels"])

    def open(
        self, device: str | int | None, sample_rate: int, channels: int, latency: float | None = None
    ) -> OutputStream:
        import sounddevice as sd

        stream = sd.OutputStream(
            device=_index(device),
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            latency=latency if latency is not None else "high",
        )
        return _PortAudioOutput(stream, sample_rate)


class _PortAudioOutput:
    """An ``sounddevice`` output stream with the buffer size in frames."""

    def __init__(self, stream: Any, sample_rate: int) -> None:
        self._stream = stream
        self._sample_rate = sample_rate

    def start(self) -> None:
        self._stream.start()

    def stop(self) -> None:
        self._stream.stop()

    def close(self) -> None:
        self._stream.close()

    @property
    def buffer_frames(self) -> int:
        return round(self._stream.latency * self._sample_rate)

    @property
    def write_available(self) -> int:
        return int(self._stream.write_available)

    def write(self, data: np.ndarray) -> bool:
        return bool(self._stream.write(data))


def output_device_names() -> list[str]:
    """Return the names of the output devices, without repeats; empty if no sound system is available."""
    try:
        import sounddevice as sd

        names = [str(d["name"]) for d in sd.query_devices() if d["max_output_channels"] > 0]
    except Exception:
        return []
    return list(dict.fromkeys(names))


def _index(device: str | int | None) -> str | int | None:
    """Turn a device name into the index of the first output device of exactly that name."""
    if not isinstance(device, str):
        return device
    import sounddevice as sd

    for index, info in enumerate(sd.query_devices()):
        if info["name"] == device and info["max_output_channels"] > 0:
            return index
    return device  # PortAudio matches a part of a name


class DeviceOutput:
    """Plays the blocks passed to ``write`` on an output device.

    The first block opens the stream at the device's sample rate and fits it to the device's
    channels. A thread feeds the device by blocking writes, so the device's own buffer keeps playing
    while the rest of the program holds the interpreter; it covers a stall up to ``latency``.
    Playback starts once ``prefill_blocks`` blocks are queued and restarts after an underrun. Blocks
    are resampled to the device rate, with a drift controller holding the queue at the prefill depth
    so the producer's and the device's clocks may differ slightly.

    With ``threaded=False`` nothing feeds the device: the caller pulls audio with ``render``.
    """

    def __init__(
        self,
        device: str | int | None = None,
        prefill_blocks: int = 4,
        backend: OutputBackend | None = None,
        latency: float | None = None,
        threaded: bool = True,
    ) -> None:
        if prefill_blocks <= 0:
            raise ValueError(f"prefill_blocks must be positive, got {prefill_blocks}")
        self._device = device
        self._latency = latency
        self._threaded = threaded
        self._prefill_blocks = prefill_blocks
        self._backend: OutputBackend = backend or SoundDeviceBackend()
        self._stream: OutputStream | None = None
        self._buffer: PullBuffer | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.sample_rate = 0
        self.channels = 0
        self.late_writes = 0  # writes after which the device had run dry
        self.error: Exception | None = None  # what ended the feeding thread, if it failed

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

    def render(self, frames: int) -> np.ndarray:
        """Return the next (``frames``, channels) of audio for the device; silence while not playing."""
        data = self._buffer.read(frames) if self._buffer is not None else None
        if data is None:
            return np.zeros((frames, self.channels), dtype=np.float32)
        return np.ascontiguousarray(data.T)

    def close(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
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
        self._stream = self._backend.open(self._device, rate, self.channels, self._latency)
        self._stream.start()
        self._stop.clear()
        if self._threaded:
            self._thread = threading.Thread(
                target=self._feed, args=(self._stream,), name="audio-out", daemon=True
            )
            self._thread.start()

    def _feed(self, stream: OutputStream) -> None:
        try:
            size = stream.buffer_frames
            while not self._stop.is_set():
                queued = size - stream.write_available
                buffer = self._buffer
                if buffer is not None and not buffer.ready(CHUNK_FRAMES) and queued > 2 * CHUNK_FRAMES:
                    # The audio is late but the device still has some: wait rather than play silence.
                    self._stop.wait(WAIT_SECONDS)
                    continue
                if stream.write(self.render(CHUNK_FRAMES)):
                    self.late_writes += 1
        except Exception as exc:
            self.error = exc
