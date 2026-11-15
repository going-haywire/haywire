from haywire.api import EXEC, FLOAT, BaseNode, ExecutionContext, NodeType, SystemEvent, SystemEventType, node


@node(
    label="Begin Player",
    description="Triggered once when execution starts",
    menu="core/event",
    search_tags=["start", "init", "begin", "event"],
    node_type=NodeType.EVENT,
)
class BeginPlayNode(BaseNode):
    """
    Triggered once when execution starts.

    Outputs:
        exec: Control flow
        timestamp: Time when execution began
    """

    def init(self):
        # Control output
        self.add(EXEC.as_outlet("exec", label="Execute"))

        # Data output
        self.add(FLOAT.as_outlet("timestamp", label="Start Time"))

    def post_init(self):
        self.event_subscription = SystemEvent(SystemEventType.BEGIN_PLAY)

    def worker(self, context: ExecutionContext) -> str | None:
        import time

        self.out("timestamp", time.time())
        # Continue execution
        return "exec"
