"""Image Event — runs its flow for each image an image emitter delivers."""

from haywire.barn.builtin.types import CHOICES, EXEC, FLOAT, INT
from haywire.core.execution import QueueMode
from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, Promotable, bag, setting

_QUEUE_MODES = {"Drop (realtime)": QueueMode.DROP, "Block (every frame)": QueueMode.BLOCK}


class DispatchSettings(NodeSettings):
    """How incoming image callbacks queue. Applies on the next start."""

    queue_mode = setting[CHOICES](
        "Drop (realtime)",
        label="Queue Mode",
        category="Dispatch",
        description=(
            "Drop keeps only the newest image (live preview). Block queues every image "
            "and back-pressures the emitter."
        ),
        widget_config={"options": list(_QUEUE_MODES)},
        promotable=Promotable.CONFIG,
    )
    max_queue_size = setting[INT](
        1,
        min=1,
        max=256,
        label="Max Queue Size",
        category="Dispatch",
        description="How many pending images to hold. Drop mode needs 1 to guarantee newest-wins.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="Image Event",
    description="Triggered for each image a connected image emitter delivers",
    menu="image/event",
    search_tags=["image", "frame", "event", "callback", "receive", "stream", "camera"],
    node_type=NodeType.EVENT,
)
class ImageEventNode(BaseNode):
    """Runs its flow once per image from the emitter it is wired to.

    Connect `Listen` to the image-callback inlet of an emitter (a stream receiver, a camera).
    The emitter sends `{"image": ImageValue, "timestamp": float, "frame_number": int}`.

    Outputs:
        frame_ready: Control flow when an image arrives
        image: The image
        timestamp / frame_number: Seconds since the emitter started, and the count
    """

    dispatch = bag(DispatchSettings)

    def init(self) -> None:
        from haybale_image.types.callback import CALLBACK_IMAGE
        from haybale_image.types.image import IMAGE

        self.add(CALLBACK_IMAGE.as_outlet("listen_callback", label="Listen"))
        self.add(EXEC.as_outlet("frame_ready", label="Frame Ready"))
        self.add(IMAGE.as_outlet("image", label="Image"))
        self.add(FLOAT.as_outlet("timestamp", label="Timestamp (s)"))
        self.add(INT.as_outlet("frame_number", label="Frame Number"))

    def post_init(self) -> None:
        from haybale_image.types.callback import CALLBACK_IMAGE

        # A copy or a loaded graph restores the saved id; the listener publishes the id it listens on.
        self.out("listen_callback", CALLBACK_IMAGE(name=self.node_id))
        self.event_subscription = CallbackEvent(
            event_name=self.node_id,
            queue_mode=_QUEUE_MODES.get(str(self.dispatch.queue_mode), QueueMode.DROP),
            max_queue_size=int(self.dispatch.max_queue_size),
        )

    def worker(self, context: ExecutionContext) -> str | None:
        payload = context.trigger.payload if context.trigger else None
        if not isinstance(payload, dict) or payload.get("image") is None:
            return None
        self.out("image", payload["image"])
        self.out("timestamp", payload.get("timestamp", 0.0))
        self.out("frame_number", payload.get("frame_number", 0))
        return "frame_ready"
