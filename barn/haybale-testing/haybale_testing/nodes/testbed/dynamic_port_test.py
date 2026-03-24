"""
Dynamic port test node for validation pipeline testing.

Uses push/pop via on_change callback to dynamically add/remove
ports based on a config value. Designed for testing edge survival
across node reconfigurations and hot reloads.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Dynamic Port TestNode",
    search_tags=["testing", "dynamic", "push", "pop", "reconfigure"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class DynamicPortTestNode(BaseNode):
    """
    Node with dynamically configurable ports for testing
    the validation pipeline (push/pop, hot reload, edge survival).

    Static ports (always present):
    - bool_inlet, bool_outlet

    Dynamic ports (controlled by port_count config):
    - dynamic_inlet_0..N  (TEST_INT)
    - dynamic_outlet_0..N (TEST_INT)
    """

    def init(self):
        from haybale_testing.types.test_types import TEST_BOOL, TEST_INT

        # Static ports that survive reconfiguration
        self.add(TEST_BOOL.as_inlet(id="bool_inlet", label="Bool Inlet"))
        self.add(TEST_BOOL.as_outlet(id="bool_outlet", label="Bool Outlet"))

        # Config port controlling dynamic port count
        self.add(
            TEST_INT.as_inlet(id="port_count", label="Port Count", default=2, on_change="hb_reconfigure")
        )

        # Build dynamic ports based on initial count
        self._build_dynamic_ports(2)

    def hb_reconfigure(self, port=None, *args):
        """Called by on_change when port_count changes."""
        count = self.value("port_count")
        if not isinstance(count, int) or count < 0:
            count = 0

        with self.rejig(include=r"^dynamic_"):
            self._build_dynamic_ports(count)

    def _build_dynamic_ports(self, count: int):
        """Add dynamic inlet/outlet pairs."""
        from haybale_testing.types.test_types import TEST_INT

        for i in range(count):
            self.add(TEST_INT.as_inlet(id=f"dynamic_inlet_{i}", label=f"Dynamic Inlet {i}"))
            self.add(TEST_INT.as_outlet(id=f"dynamic_outlet_{i}", label=f"Dynamic Outlet {i}"))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
