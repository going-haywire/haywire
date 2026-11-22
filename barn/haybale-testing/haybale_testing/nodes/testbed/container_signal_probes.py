"""Test-only nodes carrying containers of control and callback elements."""

from __future__ import annotations

from haywire.api import CALLBACK, EXEC, BaseNode, ExecutionContext, NodeType, node


@node(
    label="Array Exec Probe",
    description="Test-only: an array-of-EXEC outlet and inlet on a control node.",
    menu="testing/testbed",
    search_tags=["test", "array", "exec", "container"],
    node_type=NodeType.CONTROL,
)
class ArrayExecProbeNode(BaseNode):
    """Control node with an `ARRAY[EXEC]` outlet and inlet.

    Set `emit` to a list and the worker writes it to `exec_list_out` and fires
    that outlet. The worker stores what arrived on `exec_list_in` in `received`.
    """

    emit = None
    received = None

    def init(self):
        from haybale_core.types import ARRAY

        self.add(EXEC.as_inlet("exec_in"))
        self.add(ARRAY[EXEC].as_inlet("exec_list_in"))
        self.add(ARRAY[EXEC].as_outlet("exec_list_out"))

    def worker(self, context: ExecutionContext) -> str | None:
        self.received = self.value("exec_list_in")
        if self.emit is None:
            return None
        self.out("exec_list_out", self.emit)
        return "exec_list_out"


@node(
    label="Array Callback Probe",
    description="Test-only: an array-of-CALLBACK outlet and inlet.",
    menu="testing/testbed",
    search_tags=["test", "array", "callback", "container"],
    node_type=NodeType.CONTROL,
)
class ArrayCallbackProbeNode(BaseNode):
    """Node with an `ARRAY[CALLBACK]` outlet and inlet; `heard` records each list the inlet receives."""

    def init(self):
        from haybale_core.types import ARRAY

        self.add(ARRAY[CALLBACK].as_outlet("names_out"))
        self.add(ARRAY[CALLBACK].as_inlet("names_in", on_change="_on_names"))

    def post_init(self):
        self.heard = []

    def _on_names(self, port, value) -> None:
        self.heard.append(value)

    def worker(self, context: ExecutionContext) -> str | None:
        return None
