"""
Basic core node implementations
"""

# Import the node system base class
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType

from haybale_example.types.math import MathOPs


# --8<-- [start:math_op_class]
@node(
    label="Math Operation",
    search_tags=["math", "value", "single", "basic", "operation"],
    menu="examples/math/basic",
    node_type=NodeType.DATA,
)
class MathOP(BaseNode):
    """Node that outputs a constant value"""

    def init(self):
        from haybale_example.types.math import MathOPSelector
        from haybale_core.types import (
            FLOAT,
        )
        from haybale_core.widgets.basic_widgets import (
            NumberWidget,
        )

        # Add inlets with different widget types
        self.add(
            MathOPSelector.as_inlet(
                id="operator",
                label="Operator",
            )
        )

        self.add(FLOAT.as_inlet(id="value_a", label="Value A", widget=NumberWidget.config(), default=0.0))

        self.add(FLOAT.as_inlet(id="value_b", label="Value B", widget=NumberWidget.config(), default=0.0))

        self.add(FLOAT.as_outlet(id="result", label="Result"))

    # --8<-- [start:math_op_worker]
    def worker(
        self, context: ExecutionContext, value_a: float, value_b: float, operator: str
    ) -> dict | None:
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


# --8<-- [end:math_op_class]
