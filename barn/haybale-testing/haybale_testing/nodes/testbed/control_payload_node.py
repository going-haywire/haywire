from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


# --8<-- [start:control_payload_test_node]
@node(
    label="Control Payload TestNode",
    description=(
        "Test-only control node for exercising EXEC-edge payloads. Records the "
        "payload that arrived on its exec inlet, then advances — optionally "
        "writing its own payload, optionally forwarding the entered one "
        "implicitly (transparent conduit)."
    ),
    menu="testing/testbed",
    search_tags=["test", "control", "exec", "payload", "conduit"],
    node_type=NodeType.CONTROL,
)
class ControlPayloadTestNode(BaseNode):
    """Control node that participates in EXEC-payload flows.

    Behaviour is driven by two plain attributes the test sets after the node
    is created (kept off the port surface to keep the testbed node trivial):

    - ``emit_payload``: if not ``None``, the worker calls ``out("exec_out", …)``
      with this value, exercising the *explicit* payload path.
    - otherwise the worker writes nothing to ``exec_out`` and returns it anyway,
      exercising the *transparent-conduit* path where the VM forwards the
      payload that arrived on ``exec_in`` without the developer doing so.

    Either way the worker stashes the payload seen on ``exec_in`` into
    ``received`` so the test can assert what propagated down the chain.
    """

    # Test-controlled knobs (set by the test after create_node_wrapper):
    emit_payload = None
    # Populated by the worker each pulse with the value seen on ``exec_in``:
    received = None

    def init(self):
        from haybale_core.types import EXEC

        self.add(EXEC.as_inlet("exec_in"))
        self.add(EXEC.as_outlet("exec_out"))

    def worker(self, context: ExecutionContext) -> str | None:
        self.received = self.value("exec_in")
        if self.emit_payload is not None:
            self.out("exec_out", self.emit_payload)
        # Always advance. When emit_payload is None the outlet is left unwritten,
        # so the VM's transparent-conduit fallback forwards the entered payload.
        return "exec_out"


# --8<-- [end:control_payload_test_node]
