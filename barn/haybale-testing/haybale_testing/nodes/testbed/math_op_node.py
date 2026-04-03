from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    registry_id="test_add_float",
    label="Test Add Float",
    description="Test arithmetic node — adds two float values",
    menu="testing/math",
    search_tags=["test", "math", "add", "float", "arithmetic"],
    node_type=NodeType.DATA,
)
class TestAddFloatNode(BaseNode):
    """Test-only data node that adds two float values."""

    def init(self):
        from haybale_core.types.specs import FLOAT

        self.add(FLOAT.as_inlet(id="value_a", label="Value A", default=0.0))
        self.add(FLOAT.as_inlet(id="value_b", label="Value B", default=0.0))
        self.add(FLOAT.as_outlet(id="result", label="Result"))

    def worker(
        self, context: ExecutionContext, value_a: float, value_b: float
    ) -> dict | None:
        self.out("result", value_a + value_b)
        return None
