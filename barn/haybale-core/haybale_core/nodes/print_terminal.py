import logging

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType

logger = logging.getLogger("haybale.print")


@node(label="Print Terminal Message", menu="testing/utils", node_type=NodeType.CONTROL)
class PrintTerminalMessageNode(BaseNode):
    """Simple control node that prints a message"""

    def init(self):
        from haybale_core.types import EXEC, STRING
        from haybale_core.widgets import TextWidget

        # Control flow
        self.add(EXEC.as_inlet("exec"))
        self.add(EXEC.as_outlet("done"))

        # Data input
        self.add(
            STRING.as_inlet(
                "prepend", label="Prepend", default="My Message to you:", widget=TextWidget.config()
            )
        )

        # Data input
        self.add(STRING.as_inlet("message", default="Hello, World!"))

    def worker(self, context: ExecutionContext, prepend: str) -> str | None:
        message = self.value("message")
        logger.info(prepend + message)
        return "done"
