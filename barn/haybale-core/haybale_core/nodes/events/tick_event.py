from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Tick",
    description="Triggered by a connected emitter (Tick Emit, Run Button)",
    menu="core/event",
    search_tags=["frame", "update", "loop", "event", "tick"],
    node_type=NodeType.EVENT,
)
class TickEventNode(BaseNode):
    """
    Runs its flow each time a connected emitter triggers it.

    Connect the `Listen` outlet to the `Trigger` inlet of a Tick Emit (periodic
    ticks) or a Run Button (one trigger per press).

    Outputs:
        exec: Control flow
        delta_time: Time since the emitter's previous trigger (seconds)
    """

    def init(self):
        from haywire.barn.builtin.types import FLOAT
        from haywire.barn.builtin.types import CALLBACK, EXEC

        # Callback outlet — broadcasts this node's listener ID
        self.add(CALLBACK.as_outlet("listen_callback", label="Listen"))

        # Control output
        self.add(EXEC.as_outlet("exec", label="Execute"))

        # Data output
        self.add(FLOAT.as_outlet("delta_time", label="Delta Time"))

    def post_init(self):
        # A copy or a loaded graph restores the saved id; the listener publishes the id it listens on.
        self.ports["listen_callback"].set_value(self.node_id)
        # Subscribe to callbacks using this node's ID
        self.event_subscription = CallbackEvent(event_name=self.node_id)

    def worker(self, context: ExecutionContext) -> str | None:
        payload = context.trigger.payload if context.trigger else None
        delta = payload.get("delta_time", 0.016) if payload else 0.016
        self.out("delta_time", delta)
        return "exec"
