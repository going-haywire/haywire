"""Clip Event — runs its flow for each audio clip a clip emitter delivers."""

from __future__ import annotations

from haywire.api import (
    CHOICES,
    EXEC,
    FLOAT,
    INT,
    BaseNode,
    CallbackEvent,
    DeliverySettings,
    ExecutionContext,
    NodeSettings,
    NodeType,
    Promotable,
    QueueMode,
    bag,
    node,
    setting,
)

_QUEUE_MODES = {"Block (every clip)": QueueMode.BLOCK, "Drop (newest only)": QueueMode.DROP}


class ClipDispatchSettings(NodeSettings):
    """How incoming clips queue while the flow runs. Applies on the next start."""

    queue_mode = setting[CHOICES](
        "Block (every clip)",
        label="Queue Mode",
        category="Dispatch",
        description=(
            "Block queues every clip and holds the emitter back when the queue is full. Drop keeps "
            "only the newest clip, so clips are lost whenever the flow runs behind."
        ),
        widget_config={"options": list(_QUEUE_MODES)},
        promotable=Promotable.CONFIG,
    )
    max_queue_size = setting[INT](
        16,
        min=1,
        max=1024,
        label="Max Queue Size",
        category="Dispatch",
        description="How many clips wait while the flow runs.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="Clip Event",
    description="Triggered for each audio clip a connected clip emitter delivers",
    menu="audio/event",
    search_tags=["audio", "clip", "event", "callback", "receive", "speech", "segment", "pool"],
    node_type=NodeType.EVENT,
)
class ClipEventNode(BaseNode):
    """Runs its flow once per clip from the emitter it is wired to.

    Connect `Listen` to the clip-callback inlet of a clip emitter, such as Clip Segmenter's
    `Subscribers`. The emitter sends `{"clip": AudioBlock, "timestamp": float, "clip_number": int}`.

    `Clip Ready` is plain control flow: the flow may take as long as it needs, such as a speech
    model transcribing the clip, and the emitter's audio flow goes on meanwhile.

    Delivery: `Every` runs the flow for every clip. `Pooled` shares the clips with the emitter's
    other pooled listeners: the next free one takes each clip, so two pooled flows with a slow
    model each work on a clip at once. Queue Mode and Max Queue Size then have no effect; the
    emitter's Backlog holds the clips that wait. Two pooled flows run at once only when they share
    no control node: flows that share one run one after the other.

    Outputs:
        clip_ready: Control flow when a clip arrives
        clip: The clip
        timestamp: Where the clip starts, in seconds since the emitter's first block
        clip_number: The count of clips the emitter has sent
    """

    dispatch = bag(ClipDispatchSettings)
    delivery = bag(DeliverySettings)

    def init(self) -> None:
        # reload: barn types are looked up fresh after a hot reload.
        from haybale_audio.types.audio_clip import AUDIO_CLIP
        from haybale_audio.types.clip_callback import CLIP_CALLBACK

        self.add(CLIP_CALLBACK.as_outlet("listen_callback", label="Listen"))
        self.add(EXEC.as_outlet("clip_ready", label="Clip Ready"))
        self.add(AUDIO_CLIP.as_outlet("clip", label="Clip"))
        self.add(FLOAT.as_outlet("timestamp", label="Timestamp (s)"))
        self.add(INT.as_outlet("clip_number", label="Clip Number"))

    def post_init(self) -> None:
        from haybale_audio.types.clip_callback import CLIP_CALLBACK

        # A copy or a loaded graph restores the saved id; the listener publishes the id it listens on.
        self.out("listen_callback", CLIP_CALLBACK(name=self.node_id))
        self._subscribe()
        self.dispatch._subscribe_field("queue_mode", self._on_setting)
        self.dispatch._subscribe_field("max_queue_size", self._on_setting)
        self.delivery._subscribe_field("mode", self._on_setting)

    def _on_setting(self, _value: object, _old: object) -> None:
        self._subscribe()

    def _subscribe(self) -> None:
        # The subscription takes effect when the graph next starts.
        self.event_subscription = CallbackEvent(
            event_name=self.node_id,
            queue_mode=_QUEUE_MODES.get(str(self.dispatch.queue_mode), QueueMode.BLOCK),
            max_queue_size=int(self.dispatch.max_queue_size),
            delivery=self.delivery.delivery,
        )

    def worker(self, context: ExecutionContext) -> str | None:
        payload = context.trigger.payload if context.trigger else None
        if not isinstance(payload, dict) or payload.get("clip") is None:
            return None
        self.out("clip", payload["clip"])
        self.out("timestamp", payload.get("timestamp", 0.0))
        self.out("clip_number", payload.get("clip_number", 0))
        return "clip_ready"
