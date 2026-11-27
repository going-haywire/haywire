from __future__ import annotations

from haywire.api import (
    CALLBACK,
    EXEC,
    FLOAT,
    INT,
    BaseNode,
    CallbackEvent,
    DeliverySettings,
    ExecutionContext,
    NodeType,
    NumberWidget,
    bag,
    node,
)


@node(
    label="Merged Callback Event",
    description="Listens for a specified number of callbacks from other flows",
    menu="examples/event/callback",
    search_tags=["callback", "listen", "event", "custom"],
    node_type=NodeType.EVENT,
)
class MergedCallbackEventNode(BaseNode):
    """
    Listens for a specified number of callbacks from other flows.

    Config:
        callback_name: Name of the callback to listen for

    Outputs:
        triggered: Control flow when callback received
        payload: Data from callback

    Delivery: `Every` runs for every callback; `Pooled` shares them with the emitter's other
    pooled listeners, the next free one taking each callback.
    """

    delivery = bag(DeliverySettings)

    def init(self):
        # Config for callback name

        self.add(
            INT.as_config(
                "custom_callback_count",
                default=1,
                label="Callback Count",
                widget=NumberWidget.config(properties={"min": 1, "step": 1}),
                on_change="hb_rebuild",
            )
        )

        self.hb_reconfigure(number_of_callbacks=1)

    def post_init(self):
        # Set initial subscription
        self.cache.store = {}
        self._subscribe()
        self.delivery._subscribe_field("mode", self._on_delivery)

    def _on_delivery(self, _value: object, _old: object) -> None:
        self._subscribe()

    def _subscribe(self) -> None:
        # Delivery takes effect when the graph next starts.
        self.event_subscription = CallbackEvent(event_name=self.node_id, delivery=self.delivery.delivery)

    def hb_rebuild(self, *args, **kwargs) -> None:
        """Request a redraw of the node in the UI."""
        number_of_callbacks = self.value("custom_callback_count")
        if number_of_callbacks and number_of_callbacks > 0:
            self.hb_reconfigure(number_of_callbacks=number_of_callbacks)
            self.wrapper.redraw()

    def hb_reconfigure(self, number_of_callbacks: int = 1):
        """Reconfigure the node based on current settings."""

        self.cache.store = {}

        with self.rejig(exclude=["custom_callback_count"]):
            for i in range(number_of_callbacks):
                # Declare callback interest
                self.add(
                    CALLBACK.as_outlet(
                        f"listen_callback_{i + 1}",
                        label="Listener " + str(i + 1),
                        default=self.node_id + str(i + 1),
                    )
                )

            if number_of_callbacks > 0:
                # Control output
                self.add(EXEC.as_outlet("triggered", label="Triggered"))

            for i in range(number_of_callbacks):
                # Data output
                self.add(FLOAT.as_outlet(f"payload_{i + 1}", label="Payload " + str(i + 1)))

    def worker(self, context: ExecutionContext) -> str | None:
        # Extract payload from trigger
        if context.trigger:
            self.cache.store[context.trigger.source_key] = context.trigger.payload

        return "triggered"
