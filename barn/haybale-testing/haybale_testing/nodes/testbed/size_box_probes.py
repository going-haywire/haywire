"""Node fixtures for the declared-size-box feature (browser test support).

One node per widget flavour, deliberately not one node with three ports: a
node's size floor is a whole-card property, so widgets sharing a node would
floor it together and the declaration under test would not be isolated.
"""

from __future__ import annotations

from haywire.api import STRING, BaseNode, ExecutionContext, NodeType, node


class _SizeBoxProbeNode(BaseNode):
    """Hosts one oversized-content widget, named by ``WIDGET_KEY``."""

    WIDGET_KEY: str = ""

    def init(self):
        self.add(
            STRING.as_config(
                "preview",
                label="Preview",
                default="",
                widget_key=self.WIDGET_KEY,
            )
        )
        # Data nodes must carry at least one data outlet (structural validation).
        self.add(STRING.as_outlet("passthrough", label="Passthrough"))

    def worker(self, context: ExecutionContext) -> str | None:
        return None


@node(
    label="Size Box Content Probe",
    description="Hosts an oversized widget with no declared box",
    search_tags=["size", "resize", "widget", "testing"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class SizeBoxContentProbeNode(_SizeBoxProbeNode):
    WIDGET_KEY = "haybale-testing:widget:OversizedContentWidget"


@node(
    label="Size Box Aspect Probe",
    description="Hosts an oversized widget declaring min_width only",
    search_tags=["size", "resize", "widget", "testing"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class SizeBoxAspectProbeNode(_SizeBoxProbeNode):
    WIDGET_KEY = "haybale-testing:widget:AspectBoxWidget"


@node(
    label="Size Box Fixed Probe",
    description="Hosts an oversized widget declaring both axes",
    search_tags=["size", "resize", "widget", "testing"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class SizeBoxFixedProbeNode(_SizeBoxProbeNode):
    WIDGET_KEY = "haybale-testing:widget:FixedBoxWidget"
