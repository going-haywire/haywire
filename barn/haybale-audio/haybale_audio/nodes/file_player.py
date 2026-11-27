"""File Player — plays an audio file as audio blocks, in real time."""

from __future__ import annotations

from haybale_audio.emitter import BlockPump, deliver_to_subscribers, set_status
from haybale_audio.io.files import FileBlockReader
from haywire.api import (
    BOOL,
    EXEC,
    FILE_PATH,
    INT,
    STRING,
    BaseNode,
    ExecutionContext,
    LabelWidget,
    NodeSettings,
    NodeType,
    PathWidget,
    Promotable,
    VolumePath,
    bag,
    node,
    resolve_volume_path,
    setting,
)

_EXTENSIONS = [".wav", ".flac", ".ogg", ".aiff", ".mp3"]


class PlayerSettings(NodeSettings):
    """How the file is read. Applies on the next start."""

    block_size = setting[INT](
        256,
        min=16,
        max=8192,
        label="Block Size",
        category="Playback",
        description="Samples per block. The file's own sample rate and channels are kept.",
        promotable=Promotable.CONFIG,
    )
    loop = setting[BOOL](
        False,
        label="Loop",
        category="Playback",
        description="Start again at the end of the file instead of stopping.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="File Player",
    description="Plays an audio file as audio blocks, in real time",
    menu="audio/source",
    search_tags=["audio", "file", "play", "wav", "flac", "ogg", "read", "emit"],
    node_type=NodeType.CONTROL,
)
class FilePlayerNode(BaseNode):
    """Reads an audio file from a volume and delivers it to every Audio Event listening.

    Delivery is paced at the file's sample rate. The file's own sample rate and channel count are
    kept: a node that needs another format converts it (Reblock/Resample).

    Inputs:
        start / stop: Begin or end playback
        path: Audio file to play
        callbacks: Pooled AUDIO_CALLBACK subscriptions from Audio Event nodes

    Outputs:
        started / stopped: Control flow after the matching input
    """

    playback = bag(PlayerSettings)

    def init(self) -> None:
        from haybale_audio.types.callback import AUDIO_CALLBACK
        from haybale_core.types import POOLED

        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(
            FILE_PATH.as_inlet(
                "path",
                label="Path",
                widget=PathWidget.config(properties={"mode": "open", "extensions": _EXTENSIONS}),
                description="Audio file to play",
            )
        )
        self.add(
            POOLED[AUDIO_CALLBACK].as_inlet(
                "callbacks", label="Subscribers", description="Connect to an Audio Event node."
            )
        )
        self.add(STRING.as_config("status", default="Idle", label="Status", widget=LabelWidget.config()))
        self.add(EXEC.as_outlet("started", label="Started"))
        self.add(EXEC.as_outlet("stopped", label="Stopped"))

    def post_init(self) -> None:
        self.hb_pump: BlockPump | None = None
        self.hb_reader: FileBlockReader | None = None

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_stop()

    def on_teardown(self) -> None:
        self.hb_stop()

    def worker(self, context: ExecutionContext, path: VolumePath | None = None) -> str | None:
        if context.control_pin == "start":
            return self.hb_start(context, path)
        if context.control_pin == "stop":
            self.hb_stop()
            set_status(self, "Stopped")
            return "stopped"
        return None

    def hb_start(self, context: ExecutionContext, path: VolumePath | None) -> str | None:
        if self.hb_pump is not None and self.hb_pump.running:
            return "started"
        if path is None:
            raise ValueError("no audio file given")
        if not (self.value("callbacks") or {}):
            set_status(self, "No subscriber")
            return None
        reader = FileBlockReader(
            resolve_volume_path(path), int(self.playback.block_size), bool(self.playback.loop)
        )
        self.hb_reader = reader
        self.hb_pump = BlockPump(
            produce=reader.read_block,
            deliver=lambda block, number, seconds: deliver_to_subscribers(
                context, self.value("callbacks"), block, number, seconds
            ),
            on_end=self.hb_on_end,
        )
        self.hb_pump.start()
        set_status(self, f"Playing {reader.channels} ch at {reader.sample_rate} Hz")
        return "started"

    def hb_on_end(self, error: Exception | None) -> None:
        set_status(self, f"Error: {error}" if error else "Finished")

    def hb_stop(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        pump = getattr(self, "hb_pump", None)
        if pump is not None:
            pump.stop()
            self.hb_pump = None
        reader = getattr(self, "hb_reader", None)
        if reader is not None:
            reader.close()
            self.hb_reader = None
