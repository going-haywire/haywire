"""Reblock — re-cuts audio blocks to a fixed size."""

from haywire.barn.builtin.types import EXEC, INT, STRING
from haywire.barn.builtin.widgets import SimpleLabelWidget
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, Promotable, bag, setting

from haybale_audio.dsp.reblock import Reblocker
from haybale_audio.emitter import deliver_to_subscribers, set_status
from haybale_audio.value import AudioBlock


class ReblockSettings(NodeSettings):
    """The size of the blocks it delivers. Applies on the next start."""

    block_size = setting[INT](
        256,
        min=16,
        max=8192,
        label="Block Size",
        category="Reblock",
        description="Samples per delivered block.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="Reblock",
    description="Re-cuts audio blocks to a fixed size and delivers them to Audio Event nodes",
    menu="audio/convert",
    search_tags=["audio", "reblock", "block", "size", "buffer", "chunk"],
    node_type=NodeType.CONTROL,
)
class ReblockNode(BaseNode):
    """Collects the blocks that reach `Write` and delivers blocks of exactly `Block Size` samples to
    every Audio Event listening, in order. One input block can give several output blocks or none.

    The delivered blocks start a new flow: the Audio Event that receives them is the queue between
    the two rates. A change of channel count or sample rate in the input drops the samples still held.

    Inputs:
        write: Add the block on `audio`
        audio: The block to add
        callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

    Outputs:
        next: Control flow after the block is taken in
    """

    reblock = bag(ReblockSettings)

    def init(self) -> None:
        from haybale_core.types import PooledType
        from haybale_audio.types.audio import AUDIO
        from haybale_audio.types.callback import CALLBACK_AUDIO

        self.add(EXEC.as_inlet("write", label="Write"))
        self.add(AUDIO.as_inlet("audio", label="Audio", description="Block to add"))
        self.add(
            PooledType[CALLBACK_AUDIO].as_inlet(
                "callbacks", label="Subscribers", description="Connect to an Audio Event node."
            )
        )
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )
        self.add(EXEC.as_outlet("next", label="Next"))

    def post_init(self) -> None:
        self.hb_reblocker: Reblocker | None = None
        self.hb_delivered = 0

    def on_startup(self, context: ExecutionContext) -> None:
        self.hb_reblocker = Reblocker(int(self.reblock.block_size))
        self.hb_delivered = 0

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_reblocker = None

    def worker(self, context: ExecutionContext, audio: AudioBlock | None = None) -> str | None:
        if audio is None:
            raise ValueError("no audio block to reblock")
        if self.hb_reblocker is None:
            self.hb_reblocker = Reblocker(int(self.reblock.block_size))
        subscribers = self.value("callbacks")
        for block in self.hb_reblocker.push(audio):
            deliver_to_subscribers(
                context, subscribers, block, self.hb_delivered, self.hb_delivered * block.duration
            )
            self.hb_delivered += 1
        set_status(self, f"{self.hb_delivered} blocks of {self.reblock.block_size}")
        return "next"
