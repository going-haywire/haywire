"""
Math operation node: applies a basic operation to two float values
"""

# Import the node system base class
from haywire.api import FLOAT, BaseNode, ExecutionContext, NodeType, NumberWidget, node

from haybale_example.types.math import MathOPs


@node(
    label="Math Operation",
    description="Applies the chosen operation (add, subtract, multiply, divide) to two float values.",
    search_tags=["math", "value", "single", "basic", "operation"],
    deprecation_warning="This node will be moved to the math library",
    menu="examples/math/basic",
    node_type=NodeType.DATA,
)
class MathOperationNode(BaseNode):
    """Applies the chosen operation to Value A and Value B; division by zero gives 0.0."""

    def init(self):
        from haybale_example.types.math import MATH_OPERATION

        # Add inlets with different widget types
        self.add(
            MATH_OPERATION.as_inlet(
                id="operator",
                label="Operator",
            )
        )

        self.add(FLOAT.as_inlet(id="value_a", label="Value A", widget=NumberWidget.config(), default=0.0))

        self.add(FLOAT.as_inlet(id="value_b", label="Value B", widget=NumberWidget.config(), default=0.0))

        self.add(FLOAT.as_outlet(id="result", label="Result"))

    # --8<-- [start:math_op_worker]
    def worker(self, context: ExecutionContext, value_a: float, value_b: float, operator: str) -> str | None:
        result = 0.0
        if operator == MathOPs.ADD.value:
            result = value_a + value_b
        elif operator == MathOPs.SUBTRACT.value:
            result = value_a - value_b
        elif operator == MathOPs.MULTIPLY.value:
            result = value_a * value_b
        elif operator == MathOPs.DIVIDE.value:
            if value_b != 0:
                result = value_a / value_b
            else:
                result = 0.0
        # result = 1 / 0
        self.out("result", result)
        return None

    # --8<-- [end:math_op_worker]
