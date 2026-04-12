from haybale_core.widgets.basic_widgets import SelectWidget
from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    registry_id="custom_callback",
    label="Custom Callback",
    description="Listens for custom callbacks from other flows",
    menu="event/callback",
    search_tags=["callback", "listen", "event", "custom"],
    node_type=NodeType.EVENT,
)
class CustomCallbackNode(BaseNode):
    """
    Listens for custom callbacks from other flows.

    Config:
        callback_name: Name of the callback to listen for

    Outputs:
        triggered: Control flow when callback received
        payload: Data from callback
    """

    def init(self):
        from ...types.specs import GROUP, EXEC, CALLBACK, STRING, FLOAT
        from haybale_core.widgets.basic_widgets import TextWidget

        # Config for callback name
        with self.group(
            GROUP.as_config("mode_switch", default=False, label="Use Custom Name", on_change="redraw")
        ):
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
                widget=SelectWidget.config(properties={"options": ["single", "multi"]}),
            )
        )

        # Declare callback interest
        self.add(
            CALLBACK.as_outlet(
                "listen_callback", label="Listen", default=self.node_id, allow_multiple_links=True
            )
        )

        # Control output
        self.add(EXEC.as_outlet("triggered", label="Triggered"))

        # Data output
        self.add(FLOAT.as_outlet("payload", label="Payload"))

    def post_init(self):
        # Set initial subscription
        self._update_subscription(None, None)

    def redraw(self, *args, **kwargs) -> None:
        """Request a redraw of the node in the UI."""
        self.wrapper.redraw()
        self._update_subscription(None, None)

    def _update_subscription(self, port, new_value):
        """Update event subscription when callback name changes"""
        mode = self.value("mode_switch")
        if mode:
            callback_name = self.value("custom_callback_name")
            self.event_subscription = CallbackEvent(event_name=callback_name)
            # Trigger flow reassembly via wrapper
            self.wrapper.request_graph_reassembly()
        else:
            callback_name = self.value("listen_callback")
            self.event_subscription = CallbackEvent(event_name=callback_name)

    def worker(self, context: ExecutionContext) -> str | None:
        # Extract payload from trigger
        payload = context.trigger.payload

        self.out("payload", payload)
        return "triggered"
