"""Test-only node that relays a callback value as soon as it is written."""

from typing import Any

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node


@node(
    label="Callback Relay Probe",
    description="Test-only: copies a callback inlet's value to its outlet on write, with a suffix.",
    menu="testing/callbacks",
    search_tags=["test", "callback", "relay", "loop"],
    node_type=NodeType.CONTROL,
)
class CallbackRelayProbeNode(BaseNode):
    """Copies each value written to `in` onto `out` at once, with `suffix` appended.

    An empty `suffix` relays the value unchanged; absence is relayed as absence.
    `heard` records every value `in` reported.
    """

    suffix = ""

    def init(self):
        from haywire.barn.builtin.types import CALLBACK

        self.add(CALLBACK.as_inlet("in", on_change="_relay"))
        self.add(CALLBACK.as_outlet("out"))

    def post_init(self):
        self.heard: list[Any] = []

    def _relay(self, port, value) -> None:
        self.heard.append(value)
        self.out("out", value if value is None else f"{value}{self.suffix}")

    def worker(self, context: ExecutionContext) -> str | None:
        return None
