"""Recorder — writes the audio blocks of a flow to a file."""

from haywire.barn.builtin.types import EXEC, FILE_PATH, INT, STRING
from haywire.barn.builtin.widgets import PathWidget, SimpleLabelWidget
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.volumes import VolumePath, resolve

from haybale_audio.emitter import set_status
from haybale_audio.io.files import BlockWriter
from haybale_audio.value import AudioBlock

_EXTENSIONS = [".wav", ".flac", ".ogg"]


@node(
    label="Recorder",
    description="Writes audio blocks to a file",
    menu="audio/io",
    search_tags=["audio", "record", "write", "save", "file", "wav", "flac", "ogg"],
    node_type=NodeType.CONTROL,
)
class RecorderNode(BaseNode):
    """Appends each block to a file. The first block opens it and fixes its channel count and sample
    rate; a later block that differs is an error. WAV files are written as 32-bit float.

    Inputs:
        write: Append the block on `audio` (wire it to an Audio Event's Block Ready)
        stop: Close the file; the next `write` starts a new recording
        audio: The block to append
        path: File to write; its extension picks the format

    Outputs:
        next: Control flow after a block is written
        frames: Frames written to the current file
    """

    def init(self) -> None:
        from haybale_audio.types.audio import AUDIO

        self.add(EXEC.as_inlet("write", label="Write"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(AUDIO.as_inlet("audio", label="Audio", description="Block to append"))
        self.add(
            FILE_PATH.as_inlet(
                "path",
                label="Path",
                widget=PathWidget.config(properties={"mode": "save", "extensions": _EXTENSIONS}),
                description="File to write; its extension picks the format",
            )
        )
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )
        self.add(EXEC.as_outlet("next", label="Next"))
        self.add(INT.as_outlet("frames", label="Frames"))

    def post_init(self) -> None:
        self.hb_writer: BlockWriter | None = None

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_close()

    def on_teardown(self) -> None:
        self.hb_close()

    def worker(
        self, context: ExecutionContext, audio: AudioBlock | None = None, path: VolumePath | None = None
    ) -> str | None:
        if context.control_pin == "stop":
            self.hb_close()
            set_status(self, "Stopped")
            return None
        if audio is None or path is None:
            raise ValueError("write needs both an audio block and a path")
        if self.hb_writer is None:
            self.hb_writer = BlockWriter(resolve(path))
        self.hb_writer.write(audio)
        self.out("frames", self.hb_writer.frames_written)
        set_status(self, f"Recording {self.hb_writer.frames_written / audio.sample_rate:.1f} s")
        return "next"

    def hb_close(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        writer = getattr(self, "hb_writer", None)
        if writer is not None:
            writer.close()
            self.hb_writer = None
