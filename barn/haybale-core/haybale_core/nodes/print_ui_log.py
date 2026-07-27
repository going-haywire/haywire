from haywire.core.node import node, BaseNode, NodeType
from haywire.ui.console_bridge import console_print


@node(
    label="Print",
    registry_id="PrintLogNode",  # PINNED — see below. Do not remove.
    menu="core/utils",
    description="Print to the haywire UI console",
    node_type=NodeType.CONTROL,
)
class PrintNode(BaseNode):
    """Prints a message to the haywire ui console.

    `registry_id` stays pinned to the old "PrintLogNode" class name so existing
    saved graphs keep resolving across the rename.
    """

    def init(self):
        from haywire.barn.builtin.types import STRING
        from haybale_core.types import EXEC

        # Control flow
        self.add(EXEC.as_inlet("exec"))
        self.add(EXEC.as_outlet("done"))

        # Data input
        self.add(STRING.as_inlet("message", default="Hello, World!"))

    def worker(self, context):
        message = self.value("message")
        console_print(message)  # Thread-safe, appears in UI
        return "done"
