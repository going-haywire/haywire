from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Test Emit Callback",
    description="Test version of EmitCallback — emits a callback to trigger event nodes",
    menu="testing/callbacks",
    search_tags=["test", "callback", "emit", "trigger", "event"],
    node_type=NodeType.CONTROL,
)
class TestEmitCallbackNode(BaseNode):
    """Test-only control node that emits a named callback."""

    def init(self):
        from haybale_core.types.specs import EXEC, STRING, FLOAT, CALLBACK, GROUP, BOOL
        from haybale_core.types.pooled_type import PooledType
        from haybale_core.widgets.basic_widgets import SwitchWidget, TextWidget

        self.add(EXEC.as_inlet("execute", label="Execute"))

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
            BOOL.as_inlet(
                "sequential_mode",
                label="Sequential",
                description="Sequential Mode - if multiple callbacks, emit in sequence",
                default=False,
                widget=SwitchWidget.config(),
            )
        )

        self.add(FLOAT.as_inlet("payload", use_mode="optional", label="Payload"))

        self.add(PooledType[CALLBACK].as_inlet("edge_callback", label="Trigger", on_change="printout"))

        self.add(EXEC.as_outlet("exec", label="Then"))

    def post_init(self):
        self.callback_index = 0

    def redraw(self, *args, **kwargs) -> None:
        self.wrapper.redraw()

    def printout(self, port, new_value):
        self.callback_index = 0

    def worker(
        self,
        context: ExecutionContext,
        mode_switch: bool,
        sequential_mode: bool,
        edge_callbacks: dict,
        custom_callback_name: str,
        payload: float,
    ) -> dict | None:
        if mode_switch:
            context.emit_callback(event_name=custom_callback_name, payload=payload)
        else:
            if sequential_mode:
                edge_callback = list(edge_callbacks.values())[self.callback_index]
                self.callback_index = (self.callback_index + 1) % len(edge_callbacks)
                context.emit_callback(event_name=edge_callback, payload=payload)
            else:
                for edge_callback in edge_callbacks.values():
                    context.emit_callback(event_name=edge_callback, payload=payload)

        return "exec"
