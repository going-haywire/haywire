"""Node fixtures for chip selects and long labels on node cards (browser test support).

Each node hosts the one widget under test plus, on the chip node, a plain single select
for comparison: a node's size floor is a whole-card property, so each case gets its own
node. Backs ``tests/ui/harness/test_chip_select_widget.py``.
"""

from __future__ import annotations

from haywire.api import STRING, BaseNode, ExecutionContext, LabelWidget, MenuWidget, NodeType, node

#: A status line far wider than any node the tests size by hand.
LONG_STATUS = (
    "Listening 1 ch at 48000 Hz, blocks 256, latency 56.9 ms, lost 0, overflow 0, "
    "device Built-in Microphone, host API Core Audio, format float32"
)


@node(
    label="Chip Field Probe",
    description="Hosts a chip select whose root is the select, beside a plain select",
    search_tags=["chips", "select", "widget", "testing"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class ChipFieldProbeNode(BaseNode):
    """A chip field (all twelve choices chosen) and a plain single select."""

    def init(self):
        self.add(
            STRING.as_config(
                "chips",
                label="Chips",
                default="",
                widget_key="haybale-testing:widget:ChipSelectRootWidget",
            )
        )
        self.add(
            STRING.as_config(
                "plain",
                label="Plain",
                default="a",
                widget=MenuWidget.config(properties={"options": ["a", "b"]}),
            )
        )
        self.add(STRING.as_outlet("passthrough", label="Passthrough"))

    def worker(self, context: ExecutionContext) -> str | None:
        return None


@node(
    label="Long Label Probe",
    description="Hosts a status label far longer than the node is wide",
    search_tags=["label", "status", "widget", "testing"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class LongLabelProbeNode(BaseNode):
    """A status shown with `LabelWidget`, as the audio nodes show theirs."""

    def init(self):
        self.add(
            STRING.as_config("status", label="Status", default=LONG_STATUS, widget=LabelWidget.config())
        )
        self.add(STRING.as_outlet("passthrough", label="Passthrough"))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
