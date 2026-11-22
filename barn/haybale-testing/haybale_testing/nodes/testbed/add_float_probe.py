from __future__ import annotations

from haywire.api import FLOAT, BaseNode, ExecutionContext, NodeType, node


@node(
    label="Add Float Probe",
    description="Test arithmetic node — adds two float values",
    menu="testing/math",
    search_tags=["test", "math", "add", "float", "arithmetic"],
    node_type=NodeType.DATA,
)
class AddFloatProbeNode(BaseNode):
    """Test-only data node that adds two float values."""

    def init(self):
        self.add(FLOAT.as_inlet(id="value_a", label="Value A", default=0.0))
        self.add(FLOAT.as_inlet(id="value_b", label="Value B", default=0.0))
        self.add(FLOAT.as_outlet(id="result", label="Result"))

    def worker(self, context: ExecutionContext, value_a: float, value_b: float) -> str | None:
        self.out("result", value_a + value_b)
        return None
