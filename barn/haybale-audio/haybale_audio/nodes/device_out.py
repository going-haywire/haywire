"""Device Out — plays the audio blocks of a flow on a sound device."""

import time

from haywire.barn.builtin.types import EXEC, INT, STRING
from haywire.barn.builtin.widgets import SimpleLabelWidget
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, Promotable, bag, setting

from haybale_audio.emitter import set_status
from haybale_audio.io.device import DeviceOutput
from haybale_audio.value import AudioBlock

#: Seconds between status updates; one per block would flood the UI.
STATUS_INTERVAL = 0.5


class DeviceOutSettings(NodeSettings):
    """Where and how the sound is played. Applies on the next start."""

    device = setting[STRING](
        "",
        label="Device",
        category="Output",
        description="Name (or part of it) or number of the output device. Empty uses the system default.",
        promotable=Promotable.CONFIG,
    )
    prefill = setting[INT](
        4,
        min=1,
        max=64,
        label="Prefill",
        category="Output",
        description="Blocks queued before playback starts. More blocks survive longer stalls but add delay.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="Device Out",
    description="Plays audio blocks on a sound device",
    menu="audio/io",
    search_tags=["audio", "play", "speaker", "output", "device", "sound"],
    node_type=NodeType.CONTROL,
)
class DeviceOutNode(BaseNode):
    """Plays each block on an output device. The first block opens the device at its own sample rate;
    blocks are converted to it, and a mono block plays on both speakers of a stereo device.

    Playback starts once the prefill is queued and restarts after a stall. A producer clock that
    differs slightly from the device clock is absorbed by adjusting the conversion ratio.

    Inputs:
        write: Queue the block on `audio` (wire it to an Audio Event's Block Ready)
        stop: Close the device; the next `write` opens it again
        audio: The block to play

    Outputs:
        next: Control flow after a block is queued
        depth: Frames queued for the device
    """

    output = bag(DeviceOutSettings)

    def init(self) -> None:
        from haybale_audio.types.audio import AUDIO

        self.add(EXEC.as_inlet("write", label="Write"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(AUDIO.as_inlet("audio", label="Audio", description="Block to play"))
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )
        self.add(EXEC.as_outlet("next", label="Next"))
        self.add(INT.as_outlet("depth", label="Depth"))

    def post_init(self) -> None:
        self.hb_output: DeviceOutput | None = None
        self.hb_status_at = 0.0

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_close()

    def on_teardown(self) -> None:
        self.hb_close()

    def worker(self, context: ExecutionContext, audio: AudioBlock | None = None) -> str | None:
        if context.control_pin == "stop":
            self.hb_close()
            set_status(self, "Stopped")
            return None
        if audio is None:
            raise ValueError("write needs an audio block")
        if self.hb_output is None:
            self.hb_output = DeviceOutput(_device(str(self.output.device)), int(self.output.prefill))
        self.hb_output.write(audio)
        self.out("depth", self.hb_output.depth)
        now = time.monotonic()
        if now - self.hb_status_at >= STATUS_INTERVAL:
            self.hb_status_at = now
            out = self.hb_output
            set_status(
                self,
                f"Playing {out.channels} ch at {out.sample_rate} Hz, "
                f"stalls {out.underruns}, dropped {out.overruns}",
            )
        return "next"

    def hb_close(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        output = getattr(self, "hb_output", None)
        if output is not None:
            output.close()
            self.hb_output = None


def _device(text: str) -> str | int | None:
    text = text.strip()
    if not text:
        return None
    return int(text) if text.isdigit() else text
