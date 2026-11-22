from __future__ import annotations

from haywire.api import (
    BOOL,
    CALLBACK,
    EXEC,
    FLOAT,
    STRING,
    BaseNode,
    ExecutionContext,
    NodeType,
    TextWidget,
    ToggleWidget,
    node,
)


@node(
    label="Callback Emit Probe",
    description="Test version of EmitCallback — emits a callback to trigger event nodes",
    menu="testing/callbacks",
    search_tags=["test", "callback", "emit", "trigger", "event"],
    node_type=NodeType.CONTROL,
)
class CallbackEmitProbeNode(BaseNode):
    """Test-only control node that emits a named callback."""

    def init(self):
        from haybale_core.types import POOLED

        self.add(EXEC.as_inlet("execute", label="Execute"))

        with self.fold("Custom Name", default=False, on_change="redraw"):
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
                widget=ToggleWidget.config(),
            )
        )

        self.add(FLOAT.as_inlet("payload", use_mode="optional", label="Payload"))

        self.add(POOLED[CALLBACK].as_inlet("edge_callback", label="Trigger", on_change="printout"))

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
        custom_name: bool,
        sequential_mode: bool,
        edge_callbacks: dict,
        custom_callback_name: str,
        payload: float,
    ) -> str | None:
        payload_dict = {"value": payload}
        if custom_name:
            context.emit_callback(event_name=custom_callback_name, payload=payload_dict)
        else:
            if sequential_mode:
                edge_callback = list(edge_callbacks.values())[self.callback_index]
                self.callback_index = (self.callback_index + 1) % len(edge_callbacks)
                context.emit_callback(event_name=edge_callback, payload=payload_dict)
            else:
                for edge_callback in edge_callbacks.values():
                    context.emit_callback(event_name=edge_callback, payload=payload_dict)

        return "exec"
