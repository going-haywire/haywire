"""Shutdown Event Node.

Triggered when the interpreter is shutting down, allowing for cleanup operations.
"""

from __future__ import annotations

from haywire.api import EXEC, FLOAT, INT, BaseNode, ExecutionContext, NodeType, NumberWidget, node


@node(
    label="Performance Probe",
    description="Helps test performance of execution system",
    menu="testing/performance",
    search_tags=["performance", "control", "flow", "event"],
    node_type=NodeType.CONTROL,
)
class PerformanceProbeNode(BaseNode):
    """Triggered when execution is switching control flow based on condition."""

    def init(self):
        # Control output

        self.add(EXEC.as_inlet("exec", label="Execute"))

        self.add(
            INT.as_config(
                "port_count",
                label="Port Count",
                widget=NumberWidget.config(properties={"min": 0, "max": 10, "step": 1}),
                default=0,
                on_change="my_change",
                operable=False,
            )
        )
        self.add(EXEC.as_outlet("trigger", label="Trigger"))

    def post_init(self):
        pass

    def my_change(self, *args, **kwargs) -> None:
        with self.rejig(exclude=["exec", "trigger", "port_count"]):
            for i in range(self.value("port_count")):
                self.add(
                    FLOAT.as_inlet(
                        "float_inlet_" + str(i),
                        label="Input " + str(i),
                        widget=NumberWidget.config(),
                        default=i,
                    )
                )
                self.add(FLOAT.as_outlet("float_outlet_" + str(i), label="Output " + str(i)))

    def worker(self, context: ExecutionContext, port_count: int) -> str | None:
        for i in range(port_count):
            val = self.value("float_inlet_" + str(i))
            self.out("float_outlet_" + str(i), val)

        return "trigger"
