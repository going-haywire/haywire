import logging

from haywire.api import EXEC, STRING, BaseNode, ExecutionContext, NodeType, TextWidget, node

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
