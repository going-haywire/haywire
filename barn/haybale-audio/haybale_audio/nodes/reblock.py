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

    Use cases:

    - Give a node the block size it wants. A microphone may deliver 1024 samples at a time, a
      speech model may want 512 and an OMT send wants 256 or more. Put a Reblock in front of the node
      that cares and set `Block Size` to what it needs.
    - Re-cut after a Resample. A Resample changes the size of its blocks with the rate (441
      samples at 44.1 kHz become about 480 at 48 kHz). A Reblock behind it restores a fixed size.
    - Change the pace of a flow. 256 samples at 48 kHz is 187 events per second; 1024 is 47. A
      flow that does more work per block can run on the larger ones.

    ```text
    File Player → Audio Event → Resample (16000) → Audio Event → Reblock (512) → Audio Event → …
    ```

    A Reblock adds delay: samples wait until a whole block has collected, up to one block of the size
    it delivers. An Audio Mixer and a Device Out take any block size, so neither needs one in front.

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
