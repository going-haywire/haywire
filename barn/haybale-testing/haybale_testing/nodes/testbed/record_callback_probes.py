from __future__ import annotations

from haywire.api import (
    EXEC,
    BaseNode,
    CallbackEvent,
    DeliverySettings,
    ExecutionContext,
    NodeType,
    bag,
    node,
)


@node(
    label="Record Event Probe",
    description="Test event node whose subscription is a dataclass callback value",
    menu="testing/callbacks",
    search_tags=["test", "callback", "event", "record"],
    node_type=NodeType.EVENT,
)
class RecordEventProbeNode(BaseNode):
    """Test-only event node publishing a `TEST_RECORD_CALLBACK` subscription named after itself."""

    delivery = bag(DeliverySettings)

    def init(self):
        from haybale_testing.types import TEST_RECORD_CALLBACK

        self.add(
            TEST_RECORD_CALLBACK.as_outlet(
                "subscription",
                label="Listen",
                default={"name": self.node_id, "weight": 1},
            )
        )
        self.add(EXEC.as_outlet("triggered", label="Triggered"))

    def post_init(self):
        self._subscribe()
        self.delivery._subscribe_field("mode", self._on_delivery)

    def _on_delivery(self, _value: object, _old: object) -> None:
        self._subscribe()

    def _subscribe(self) -> None:
        self.event_subscription = CallbackEvent(event_name=self.node_id, delivery=self.delivery.delivery)

    def worker(self, context: ExecutionContext) -> str | None:
        return "triggered"


@node(
    label="Record Emit Probe",
    description="Test control node emitting to every dataclass subscription in its pool",
    menu="testing/callbacks",
    search_tags=["test", "callback", "emit", "record"],
    node_type=NodeType.CONTROL,
)
class RecordEmitProbeNode(BaseNode):
    """Test-only emitter collecting `TEST_RECORD_CALLBACK` subscriptions in a pooled inlet."""

    def init(self):
        from haybale_core.types import POOLED
        from haybale_testing.types import TEST_RECORD_CALLBACK

        self.add(EXEC.as_inlet("execute", label="Execute"))
        self.add(POOLED[TEST_RECORD_CALLBACK].as_inlet("subscriptions", label="Trigger"))
        self.add(EXEC.as_outlet("exec", label="Then"))

    def worker(self, context: ExecutionContext) -> str | None:
        for record in self.value("subscriptions").values():
            context.emit_callback(event_name=record.name, payload={"weight": record.weight})
        return "exec"
