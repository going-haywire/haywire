"""Audio Event — runs its flow for each audio block an audio emitter delivers."""

import logging

from haywire.barn.builtin.types import CHOICES, EXEC, FLOAT, INT
from haywire.core.execution import QueueMode
from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, Promotable, bag, setting

logger = logging.getLogger(__name__)

_QUEUE_MODES = {"Block (every block)": QueueMode.BLOCK, "Drop (newest only)": QueueMode.DROP}


class DispatchSettings(NodeSettings):
    """How incoming audio callbacks queue. Applies on the next start."""

    queue_mode = setting[CHOICES](
        "Block (every block)",
        label="Queue Mode",
        category="Dispatch",
        description=(
            "Block queues every block and back-pressures the emitter. Drop keeps only the "
            "newest block, so audio is lost whenever the flow runs behind."
        ),
        widget_config={"options": list(_QUEUE_MODES)},
        promotable=Promotable.CONFIG,
    )
    max_queue_size = setting[INT](
        100,
        min=1,
        max=1024,
        label="Max Queue Size",
        category="Dispatch",
        description="How many pending blocks to hold. 100 blocks of 256 samples at 48 kHz are about 0.5 s.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="Audio Event",
    description="Triggered for each audio block a connected audio emitter delivers",
    menu="audio/event",
    search_tags=["audio", "block", "event", "callback", "receive", "stream", "microphone"],
    node_type=NodeType.EVENT,
)
class AudioEventNode(BaseNode):
    """Runs its flow once per audio block from the emitter it is wired to.

    Connect `Listen` to the audio-callback inlet of an emitter (a device input, a stream
    receiver, a file player, a clock). The emitter sends
    `{"audio": AudioBlock, "timestamp": float, "block_number": int}`.

    Outputs:
        block_ready: Control flow when a block arrives
        audio: The block
        timestamp / block_number: Seconds since the emitter started, and the count
    """

    dispatch = bag(DispatchSettings)

    def init(self) -> None:
        from haybale_audio.types.audio import AUDIO
        from haybale_audio.types.callback import CALLBACK_AUDIO

        self.add(CALLBACK_AUDIO.as_outlet("listen_callback", label="Listen", default={"name": self.node_id}))
        self.add(EXEC.as_outlet("block_ready", label="Block Ready"))
        self.add(AUDIO.as_outlet("audio", label="Audio"))
        self.add(FLOAT.as_outlet("timestamp", label="Timestamp (s)"))
        self.add(INT.as_outlet("block_number", label="Block Number"))

    def post_init(self) -> None:
        from haybale_audio.types.callback import CALLBACK_AUDIO

        # A copy or a loaded graph restores the saved id; the listener publishes the id it listens on.
        self.out("listen_callback", CALLBACK_AUDIO(name=self.node_id))
        queue_mode = _QUEUE_MODES.get(str(self.dispatch.queue_mode), QueueMode.BLOCK)
        if queue_mode is QueueMode.DROP:
            logger.warning(
                "Audio Event %s uses Drop: blocks are lost whenever its flow runs behind", self.node_id
            )
        self.event_subscription = CallbackEvent(
            event_name=self.node_id,
            queue_mode=queue_mode,
            max_queue_size=int(self.dispatch.max_queue_size),
        )

    def worker(self, context: ExecutionContext) -> str | None:
        payload = context.trigger.payload if context.trigger else None
        if not isinstance(payload, dict) or payload.get("audio") is None:
            return None
        self.out("audio", payload["audio"])
        self.out("timestamp", payload.get("timestamp", 0.0))
        self.out("block_number", payload.get("block_number", 0))
        return "block_ready"
