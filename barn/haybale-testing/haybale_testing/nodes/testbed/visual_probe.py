"""Test-only node with pins on a drawn-only wire."""

from __future__ import annotations

from haywire.api import FLOAT, BaseNode, ExecutionContext, NodeType, node


@node(
    label="Visual Probe",
    description="Test-only: a data node with pins on a drawn-only wire.",
    menu="testing/testbed",
    search_tags=["test", "visual", "wire"],
    node_type=NodeType.DATA,
)
class VisualProbeNode(BaseNode):
    """Data node with `TEST_VISUAL` pins `note_in` and `note_out`, a `TEST_VISUAL_COUNT` inlet `count_in`,
    and a float outlet `value`.
    """

    def init(self):
        from haybale_testing.types import TEST_VISUAL, TEST_VISUAL_COUNT

        self.add(TEST_VISUAL.as_inlet("note_in"))
        self.add(TEST_VISUAL_COUNT.as_inlet("count_in"))
        self.add(TEST_VISUAL.as_outlet("note_out"))
        self.add(FLOAT.as_outlet("value"))

    def worker(self, context: ExecutionContext) -> str | None:
        self.out("value", 1.0)
        return None
