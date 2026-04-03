from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    registry_id="test_custom_callback",
    label="Test Custom Callback",
    description="Test version of CustomCallback — listens for named callbacks",
    menu="testing/callbacks",
    search_tags=["test", "callback", "listen", "event", "custom"],
    node_type=NodeType.EVENT,
)
class TestCustomCallbackNode(BaseNode):
    """Test-only event node that listens for custom callbacks."""

    def init(self):
        from haybale_core.types.specs import GROUP, EXEC, CALLBACK, STRING, FLOAT
        from haybale_core.widgets.basic_widgets import TextWidget, SelectWidget

        with self.group(
            GROUP.as_config("mode_switch", default=False, label="Use Custom Name", on_change="redraw")
        ):
            self.add(
                STRING.as_config(
                    "custom_callback_name",
                    default="my_callback",
                    label="Callback Name",
                    widget=TextWidget.config(),
                )
            )

        self.add(
            STRING.as_config(
                "thread_mode",
                default="single",
                label="Thread Mode",
                widget=SelectWidget.config(properties={"options": ["single", "multi"]}),
            )
        )

        self.add(
            CALLBACK.as_outlet(
                "listen_callback", label="Listen", default=self.node_id, allow_multiple_links=True
            )
        )

        self.add(EXEC.as_outlet("triggered", label="Triggered"))
        self.add(FLOAT.as_outlet("payload", label="Payload"))

    def post_init(self):
        self._update_subscription(None, None)

    def redraw(self, *args, **kwargs) -> None:
        self.wrapper.redraw()
        self._update_subscription(None, None)

    def _update_subscription(self, port, new_value):
        mode = self.value("mode_switch")
        if mode:
            callback_name = self.value("custom_callback_name")
            self.event_subscription = CallbackEvent(event_name=callback_name)
            self.wrapper.request_graph_reassembly()
        else:
            callback_name = self.value("listen_callback")
            self.event_subscription = CallbackEvent(event_name=callback_name)

    def worker(self, context: ExecutionContext) -> str | None:
        payload = context.trigger.payload
        self.out("payload", payload)
        return "triggered"
