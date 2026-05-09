import logging

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType

logger = logging.getLogger("haybale.print")


@node(label="Print Terminal Message", menu="testing/utils", node_type=NodeType.CONTROL)
class PrintTerminalMessageNode(BaseNode):
    """Simple control node that prints a message"""

    def init(self):
        from haybale_core.types import EXEC, STRING

        # Control flow
        self.add(EXEC.as_inlet("exec"))
        self.add(EXEC.as_outlet("done"))

        # Data input
        self.add(STRING.as_inlet("message", default="Hello, World!"))

    def worker(self, context: ExecutionContext) -> str | None:
        message = self.value("message")
        logger.info(message)
        return "done"
