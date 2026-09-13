from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Fold",
    description="Tests fold rendering",
    menu="testing/rendering",
    search_tags=["test", "fold", "render"],
    node_type=NodeType.CONTROL,
)
class TestFoldNode(BaseNode):
    """Test-only"""

    def init(self):
        from haywire.barn.builtin.types import STRING, FLOAT, BOOL
        from haybale_core.types import EXEC
        from haywire.barn.builtin.widgets import SwitchWidget, TextWidget

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

        with self.fold("Custom Pin", default=False, on_change="redraw"):
            self.add(
                STRING.as_inlet(
                    "in_group_inlet",
                    default="my_name",
                    label="Name",
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
    ) -> str | None:
        return None
