from __future__ import annotations

from haywire.api import (
    CALLBACK,
    EXEC,
    FLOAT,
    BaseNode,
    CallbackEvent,
    DeliverySettings,
    ExecutionContext,
    NodeType,
    bag,
    node,
)


@node(
    label="Tick Event",
    description="Triggered by a connected emitter (Tick Emit, Run Button)",
    menu="core/event",
    search_tags=["frame", "update", "loop", "event", "tick"],
    node_type=NodeType.EVENT,
)
class TickEventNode(BaseNode):
    """
    Runs its flow each time a connected emitter triggers it.

    Connect the `Listen` outlet to the `Trigger` inlet of a Tick Emit (periodic
    ticks) or a Run Button (one trigger per press).

    Delivery: `Every` runs the flow for every trigger. `Pooled` shares the triggers
    with the emitter's other pooled listeners: the next free one runs each trigger,
    and the emitter's Backlog holds them while all are busy.

    Outputs:
        exec: Control flow
        delta_time: Time since the emitter's previous trigger (seconds)
    """

    delivery = bag(DeliverySettings)

    def init(self):
        # Callback outlet — broadcasts this node's listener ID
        self.add(CALLBACK.as_outlet("listen_callback", label="Listen"))

        # Control output
        self.add(EXEC.as_outlet("exec", label="Execute"))

        # Data output
        self.add(FLOAT.as_outlet("delta_time", label="Delta Time"))

    def post_init(self):
        # A copy or a loaded graph restores the saved id; the listener publishes the id it listens on.
        self.ports["listen_callback"].set_value(self.node_id)
        self._subscribe()
        self.delivery._subscribe_field("mode", self._on_delivery)

    def _on_delivery(self, _value: object, _old: object) -> None:
        self._subscribe()

    def _subscribe(self) -> None:
        # Listens under this node's id; Delivery takes effect when the graph next starts.
        self.event_subscription = CallbackEvent(event_name=self.node_id, delivery=self.delivery.delivery)

    def worker(self, context: ExecutionContext) -> str | None:
        payload = context.trigger.payload if context.trigger else None
        delta = payload.get("delta_time", 0.016) if payload else 0.016
        self.out("delta_time", delta)
        return "exec"
