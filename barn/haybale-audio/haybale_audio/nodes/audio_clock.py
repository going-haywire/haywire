"""Audio Clock — emits a silent block at a steady rate, to pace a mixer or any audio flow."""

from haywire.barn.builtin.types import EXEC, INT, STRING
from haywire.barn.builtin.widgets import SimpleLabelWidget
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, Promotable, bag, setting

from haybale_audio.emitter import BlockPump, deliver_to_subscribers, set_status
from haybale_audio.value import AudioBlock


class ClockSettings(NodeSettings):
    """The block rate the clock keeps. Applies on the next start."""

    sample_rate = setting[INT](
        48000,
        min=8000,
        max=192000,
        label="Sample Rate",
        category="Clock",
        description="Samples per second of the blocks.",
        promotable=Promotable.CONFIG,
    )
    block_size = setting[INT](
        256,
        min=16,
        max=8192,
        label="Block Size",
        category="Clock",
        description="Samples per block. 256 at 48 kHz is a block every 5.3 ms.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="Audio Clock",
    description="Emits a silent audio block at a steady rate",
    menu="audio/source",
    search_tags=["audio", "clock", "tick", "timer", "master", "pace", "emit"],
    node_type=NodeType.CONTROL,
)
class AudioClockNode(BaseNode):
    """Paces audio flows: one silent single-channel block per period, to every Audio Event listening.

    Wire the Audio Event that triggers a mixer to this node; the mixer then runs once per block.

    Inputs:
        start / stop: Begin or end the ticks
        callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

    Outputs:
        started / stopped: Control flow after the matching input
    """

    clock = bag(ClockSettings)

    def init(self) -> None:
        from haybale_core.types import PooledType
        from haybale_audio.types.callback import CALLBACK_AUDIO

        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(
            PooledType[CALLBACK_AUDIO].as_inlet(
                "callbacks", label="Subscribers", description="Connect to an Audio Event node."
            )
        )
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )
        self.add(EXEC.as_outlet("started", label="Started"))
        self.add(EXEC.as_outlet("stopped", label="Stopped"))

    def post_init(self) -> None:
        self.hb_pump: BlockPump | None = None

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_stop()

    def on_teardown(self) -> None:
        self.hb_stop()

    def worker(self, context: ExecutionContext) -> str | None:
        if context.control_pin == "start":
            return self.hb_start(context)
        if context.control_pin == "stop":
            self.hb_stop()
            set_status(self, "Stopped")
            return "stopped"
        return None

    def hb_start(self, context: ExecutionContext) -> str | None:
        if self.hb_pump is not None and self.hb_pump.running:
            return "started"
        if not (self.value("callbacks") or {}):
            set_status(self, "No subscriber")
            return None
        silence = AudioBlock.silence(1, int(self.clock.block_size), int(self.clock.sample_rate))
        self.hb_pump = BlockPump(
            produce=lambda: silence,
            deliver=lambda block, number, seconds: deliver_to_subscribers(
                context, self.value("callbacks"), block, number, seconds
            ),
            on_end=lambda error: set_status(self, f"Error: {error}" if error else "Stopped"),
        )
        self.hb_pump.start()
        set_status(self, f"Running {silence.duration * 1000:.1f} ms blocks")
        return "started"

    def hb_stop(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        pump = getattr(self, "hb_pump", None)
        if pump is not None:
            pump.stop()
            self.hb_pump = None
