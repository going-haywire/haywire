"""Reading and writing audio files as AudioBlocks."""

from pathlib import Path

import numpy as np
import soundfile as sf

from haybale_audio.value import AudioBlock


class FileBlockReader:
    """Reads an audio file block by block, at the file's own sample rate and channel count."""

    def __init__(self, path: Path, block_size: int, loop: bool = False) -> None:
        self._file = sf.SoundFile(str(path))
        self._block_size = block_size
        self._loop = loop
        self.sample_rate: int = self._file.samplerate
        self.channels: int = self._file.channels

    def read_block(self) -> AudioBlock | None:
        """Return the next block, or ``None`` at the end of the file (unless looping).

        The last block of a pass is shorter than ``block_size`` when the length does not divide.
        """
        data = self._file.read(self._block_size, dtype="float32", always_2d=True)
        if data.shape[0] == 0 and self._loop:
            self._file.seek(0)
            data = self._file.read(self._block_size, dtype="float32", always_2d=True)
        if data.shape[0] == 0:
            return None
        return AudioBlock(np.ascontiguousarray(data.T), self.sample_rate)

    def close(self) -> None:
        self._file.close()


class BlockWriter:
    """Writes AudioBlocks to a file; the first block fixes its channel count and sample rate."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._file: sf.SoundFile | None = None
        self.frames_written = 0

    def write(self, block: AudioBlock) -> None:
        """Append ``block``.

        Raises:
            ValueError: The extension is not a known audio format, or ``block`` differs in channel
                count or sample rate from the first block.
        """
        if self._file is None:
            self._file = self._open(block)
        elif (block.channels, block.sample_rate) != (self._file.channels, self._file.samplerate):
            raise ValueError(
                f"recording is {self._file.channels} ch at {self._file.samplerate} Hz, "
                f"block is {block.channels} ch at {block.sample_rate} Hz"
            )
        self._file.write(block.data.T)
        self.frames_written += block.frames

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def _open(self, block: AudioBlock) -> sf.SoundFile:
        extension = self._path.suffix.lstrip(".").upper()
        if extension not in sf.available_formats():
            raise ValueError(f"unknown audio format '.{extension.lower()}'; use one of: {_formats()}")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # WAV keeps float32 samples as they are; the other formats use their default encoding.
        subtype = "FLOAT" if extension == "WAV" else None
        return sf.SoundFile(
            str(self._path), "w", samplerate=block.sample_rate, channels=block.channels, subtype=subtype
        )


def _formats() -> str:
    return ", ".join(f".{name.lower()}" for name in ("WAV", "FLAC", "OGG"))
