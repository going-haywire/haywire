"""Empty fold probe — a fold with nothing inside has no direction to take."""

from haywire.api import STRING, BaseNode, ExecutionContext, NodeType, node


@node(
    label="Empty Fold",
    description="Tests that a fold holding no ports raises",
    search_tags=["testing", "fold"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class EmptyFoldNode(BaseNode):
    """Test-only."""

    def init(self):
        self.add(STRING.as_outlet("out"))
        with self.fold("Nothing"):
            pass

    def worker(self, context: ExecutionContext) -> str | None:
        return None
