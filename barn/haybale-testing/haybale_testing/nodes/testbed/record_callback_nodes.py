from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Test Record Event",
    description="Test event node whose subscription is a dataclass callback value",
    menu="testing/callbacks",
    search_tags=["test", "callback", "event", "record"],
    node_type=NodeType.EVENT,
)
class TestRecordEventNode(BaseNode):
    """Test-only event node publishing a `TEST_RECORD_CALLBACK` subscription named after itself."""

    def init(self):
        from haybale_core.types import EXEC
        from haybale_testing.types import TEST_RECORD_CALLBACK

        self.add(
            TEST_RECORD_CALLBACK.as_outlet(
                "subscription",
                label="Listen",
                default={"name": self.node_id, "weight": 1},
                allow_multiple_links=True,
            )
        )
        self.add(EXEC.as_outlet("triggered", label="Triggered"))

    def post_init(self):
        self.event_subscription = CallbackEvent(event_name=self.node_id)

    def worker(self, context: ExecutionContext) -> str | None:
        return "triggered"


@node(
    label="Test Record Emit",
    description="Test control node emitting to every dataclass subscription in its pool",
    menu="testing/callbacks",
    search_tags=["test", "callback", "emit", "record"],
    node_type=NodeType.CONTROL,
)
class TestRecordEmitNode(BaseNode):
    """Test-only emitter collecting `TEST_RECORD_CALLBACK` subscriptions in a pooled inlet."""

    def init(self):
        from haybale_core.types import EXEC, PooledType
        from haybale_testing.types import TEST_RECORD_CALLBACK

        self.add(EXEC.as_inlet("execute", label="Execute"))
        self.add(PooledType[TEST_RECORD_CALLBACK].as_inlet("subscriptions", label="Trigger"))
        self.add(EXEC.as_outlet("exec", label="Then"))

    def worker(self, context: ExecutionContext) -> str | None:
        for record in self.value("subscriptions").values():
            context.emit_callback(event_name=record.name, payload={"weight": record.weight})
        return "exec"
