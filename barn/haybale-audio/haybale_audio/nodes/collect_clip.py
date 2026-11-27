"""Collect Clip — gathers the audio blocks of a flow into one clip, until Stop."""

from __future__ import annotations

from haybale_audio.dsp.clip import ClipBuffer
from haybale_audio.emitter import set_status
from haybale_audio.value import AudioBlock
from haywire.api import EXEC, FLOAT, STRING, BaseNode, ExecutionContext, LabelWidget, NodeType, node


@node(
    label="Collect Clip",
    description="Gathers the audio blocks of a flow into one clip, sent on Stop",
    menu="audio/clip",
    search_tags=["audio", "clip", "collect", "gather", "buffer", "speech", "record", "segment"],
    node_type=NodeType.CONTROL,
)
class CollectClipNode(BaseNode):
    """Appends each block to a clip in memory; `Stop` sends the clip and starts a new one.

    The first block fixes the clip's channel count and sample rate; a later block that differs
    is an error. Blocks past `Max Seconds` are dropped, and the status says so.

    ```text
    Device In → Audio Event → Collect Clip (Add)
    Run Button → Tick Event → Collect Clip (Stop) → Done → Clip Player (Start), Clip → Clip
    ```

    Inputs:
        add: Append the block on `audio` (wire it to an Audio Event's Block Ready)
        stop: Send the clip on `clip` and continue on `done`; an empty clip sends nothing
        audio: The block to append
        max_seconds: Longest clip kept

    Outputs:
        next: Control flow after a block is appended
        done: Control flow after `stop`, once `clip` holds the clip
        clip: The gathered audio, one block
        seconds: Length of the clip so far
    """

    def init(self) -> None:
        # reload: barn types are looked up fresh after a hot reload.
        from haybale_audio.types.audio import AUDIO
        from haybale_audio.types.audio_clip import AUDIO_CLIP
        from haybale_audio.types.audio_exec import AUDIO_EXEC

        self.add(AUDIO_EXEC.as_inlet("add", label="Add"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(AUDIO.as_inlet("audio", label="Audio", description="Block to append"))
        self.add(
            FLOAT.as_config(
                "max_seconds",
                default=300.0,
                label="Max Seconds",
                description="Longest clip kept; later blocks are dropped",
            )
        )
        self.add(STRING.as_config("status", default="Idle", label="Status", widget=LabelWidget.config()))
        self.add(AUDIO_EXEC.as_outlet("next", label="Next"))
        self.add(EXEC.as_outlet("done", label="Done", description="Runs after Stop, once Clip is set"))
        self.add(AUDIO_CLIP.as_outlet("clip", label="Clip", description="The gathered audio"))
        self.add(FLOAT.as_outlet("seconds", label="Seconds", description="Length of the clip so far"))

    def post_init(self) -> None:
        self.hb_buffer = ClipBuffer(300.0)

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_reset()

    def on_teardown(self) -> None:
        self.hb_reset()

    def hb_reset(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        buffer = getattr(self, "hb_buffer", None)
        if buffer is not None:
            buffer.take()

    def worker(
        self, context: ExecutionContext, audio: AudioBlock | None = None, max_seconds: float = 300.0
    ) -> str | None:
        buffer = self.hb_buffer
        if context.control_pin == "stop":
            clip = buffer.take()
            if clip is None:
                set_status(self, "Empty")
                return None
            self.out("clip", clip)
            self.out("seconds", clip.duration)
            set_status(self, f"Sent {clip.duration:.1f} s")
            return "done"
        if audio is None:
            raise ValueError("add needs an audio block")
        buffer.max_seconds = float(max_seconds)
        if buffer.add(audio):
            seconds = buffer.seconds
            self.out("seconds", seconds)
            set_status(self, f"Collecting {seconds:.1f} s")
        else:
            set_status(self, f"Full at {buffer.seconds:.1f} s — {buffer.dropped} blocks dropped")
        return "next"
