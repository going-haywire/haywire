import logging

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType

# Lives under the `haywire` namespace (not a standalone "haybale.*" tree) so its
# effective level is set deterministically by LoggingConfigurator._apply_root —
# it no longer depends on logging.basicConfig() happening to run before anything
# else attaches a handler to the true root logger.
logger = logging.getLogger("haywire.nodes.logger")

_SEVERITIES = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@node(
    label="Logger",
    registry_id="PrintTerminalMessageNode",  # PINNED — see below. Do not remove.
    menu="core/utils",
    node_type=NodeType.CONTROL,
)
class LoggerNode(BaseNode):
    """Logs a message through Python's logging system at a configurable severity.

    `registry_id` stays pinned to the old "PrintTerminalMessageNode" class name so
    existing saved graphs (e.g. graphs/loop.haywire, graphs/loop2.haywire) keep
    resolving across the rename.
    """

    def init(self):
        from haywire.barn.builtin.types import STRING
        from haybale_core.types import EXEC
        from haywire.barn.builtin.widgets import TextWidget, SelectWidget

        # Control flow
        self.add(EXEC.as_inlet("exec"))
        self.add(EXEC.as_outlet("done"))

        self.add(
            STRING.as_config(
                "severity",
                label="Severity",
                description="Log level this message is emitted at.",
                widget=SelectWidget.config(properties={"options": _SEVERITIES}),
                default="INFO",
            )
        )

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
        level = getattr(logging, self.value("severity"), logging.INFO)
        logger.log(level, prepend + message)
        return "done"
