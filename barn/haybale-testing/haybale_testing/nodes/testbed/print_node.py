import logging

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType

logger = logging.getLogger("haybale.testing.print")


@node(
    label="Test Print",
    description="Test version of Logger — logs a message and continues flow",
    menu="testing/utils",
    search_tags=["test", "print", "log", "message", "terminal"],
    node_type=NodeType.CONTROL,
)
class TestPrintNode(BaseNode):
    """Test-only control node that logs a message.

    Mirrors the port shape of ``haybale_core``'s ``LoggerNode``
    (``exec`` inlet, ``done`` outlet, ``prepend`` + ``message`` STRING inlets)
    so framework execution tests can use a testbed-owned sink instead of
    reaching into another library.
    """

    def init(self):
        from haywire.barn.builtin.types import STRING
        from haybale_core.types import EXEC
        from haywire.barn.builtin.widgets import TextWidget

        # Control flow
        self.add(EXEC.as_inlet("exec"))
        self.add(EXEC.as_outlet("done"))

        # Data inputs
        self.add(
            STRING.as_inlet(
                "prepend", label="Prepend", default="My Message to you:", widget=TextWidget.config()
            )
        )
        self.add(STRING.as_inlet("message", default="Hello, World!"))

    def worker(self, context: ExecutionContext, prepend: str) -> str | None:
        message = self.value("message")
        logger.info(prepend + message)
        return "done"
