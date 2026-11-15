"""Mixed-direction fold probe — must raise at declaration time."""

from haywire.api import FLOAT, STRING, BaseNode, ExecutionContext, NodeType, node


@node(
    label="Mixed Fold",
    description="Tests that a fold spanning two directions raises",
    search_tags=["testing", "fold"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class MixedFoldNode(BaseNode):
    """Test-only."""

    def init(self):
        self.add(STRING.as_outlet("out"))
        with self.fold("Mixed"):
            self.add(FLOAT.as_inlet("an_inlet"))
            self.add(FLOAT.as_outlet("an_outlet"))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
