from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    registry_id="test_begin_play",
    label="Test Begin Play",
    description="Test version of BeginPlay — triggered once when execution starts",
    menu="testing/events",
    search_tags=["test", "start", "init", "begin", "event"],
    node_type=NodeType.EVENT,
)
class TestBeginPlayNode(BaseNode):
    """Test-only event node triggered when execution starts."""

    def init(self):
        from haybale_core.types.specs import EXEC, FLOAT

        self.add(EXEC.as_outlet("exec", label="Execute"))
        self.add(FLOAT.as_outlet("timestamp", label="Start Time"))

    def post_init(self):
        self.event_subscription = SystemEvent(SystemEventType.BEGIN_PLAY)

    def worker(self, context: ExecutionContext) -> str | None:
        import time

        self.out("timestamp", time.time())
        return "exec"
