from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Tick",
    description="Triggered periodically by a connected TickEmitNode",
    menu="event/runtime",
    search_tags=["frame", "update", "loop", "event", "tick"],
    node_type=NodeType.EVENT,
)
class TickEventNode(BaseNode):
    """
    Listens for tick callbacks from a connected TickEmitNode.

    Connect the callback outlet to a TickEmitNode's callback inlet
    to receive periodic tick events.

    Outputs:
        exec: Control flow
        delta_time: Time since last tick (seconds)
    """

    def init(self):
        from haybale_core.types import EXEC, FLOAT, CALLBACK

        # Callback outlet — broadcasts this node's listener ID
        self.add(
            CALLBACK.as_outlet(
                "listen_callback", label="Listen", default=self.node_id, allow_multiple_links=True
            )
        )

        # Control output
        self.add(EXEC.as_outlet("exec", label="Execute"))

        # Data output
        self.add(FLOAT.as_outlet("delta_time", label="Delta Time"))

    def post_init(self):
        # Subscribe to callbacks using this node's ID
        self.event_subscription = CallbackEvent(event_name=self.node_id)

    def worker(self, context: ExecutionContext) -> str | None:
        payload = context.trigger.payload if context.trigger else None
        delta = payload.get("delta_time", 0.016) if payload else 0.016
        self.out("delta_time", delta)
        return "exec"
