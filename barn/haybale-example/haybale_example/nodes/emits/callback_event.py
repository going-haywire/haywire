from __future__ import annotations

from haywire.api import (
    CALLBACK,
    EXEC,
    FLOAT,
    STRING,
    BaseNode,
    CallbackEvent,
    DeliverySettings,
    ExecutionContext,
    MenuWidget,
    NodeType,
    TextWidget,
    bag,
    node,
)


@node(
    label="Callback Event",
    description="Listens for custom callbacks from other flows",
    menu="examples/event/callback",
    search_tags=["callback", "listen", "event", "custom"],
    node_type=NodeType.EVENT,
)
class CallbackEventNode(BaseNode):
    """Listens for custom callbacks from other flows.

    Config:
        callback_name: Name of the callback to listen for
        delivery: `Every` runs for every callback; `Pooled` shares them with the emitter's other
            pooled listeners, the next free one taking each callback

    Outputs:
        triggered: Control flow when callback received
        payload: Data from callback
    """

    delivery = bag(DeliverySettings)

    def init(self):
        # Config for callback name
        with self.fold("Custom Name", default=False, on_change="redraw"):
            # Config for callback name
            self.add(
                STRING.as_config(
                    "custom_callback_name",
                    default="my_callback",
                    label="Callback Name",
                    widget=TextWidget.config(),
                )
            )

            # Config for callback name
        self.add(
            STRING.as_config(
                "thread_mode",
                default="single",
                label="Thread Mode",
                widget=MenuWidget.config(properties={"options": ["single", "multi"]}),
            )
        )

        # Declare callback interest
        self.add(CALLBACK.as_outlet("listen_callback", label="Listen"))

        # Control output
        self.add(EXEC.as_outlet("triggered", label="Triggered"))

        # Data output
        self.add(FLOAT.as_outlet("payload", label="Payload"))

    def post_init(self):
        # A copy or a loaded graph restores the saved id; the listener publishes the id it listens on.
        self.ports["listen_callback"].set_value(self.node_id)
        # Set initial subscription
        self._update_subscription(None, None)
        self.delivery._subscribe_field("mode", self._on_delivery)

    def _on_delivery(self, _value: object, _old: object) -> None:
        self._update_subscription(None, None)

    def redraw(self, *args, **kwargs) -> None:
        """Request a redraw of the node in the UI."""
        self.wrapper.redraw()
        self._update_subscription(None, None)

    def _update_subscription(self, port, new_value):
        """Update event subscription when callback name changes"""
        mode = self.value("custom_name")
        if mode:
            callback_name = self.value("custom_callback_name")
            self.event_subscription = CallbackEvent(
                event_name=callback_name, delivery=self.delivery.delivery
            )
            # Trigger flow reassembly via wrapper
            self.wrapper.request_graph_reassembly()
        else:
            callback_name = self.value("listen_callback")
            self.event_subscription = CallbackEvent(
                event_name=callback_name, delivery=self.delivery.delivery
            )

    def worker(self, context: ExecutionContext) -> str | None:
        # Extract payload from trigger
        payload = context.trigger.payload if context.trigger else None

        self.out("payload", payload)
        return "triggered"
