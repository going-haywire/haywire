"""
Basic core node implementations
"""

# Import the node system base class
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode

from haybale_example.types.math import MathOP

@node(
    label='Math Operation',
    search_tags=['math', 'value', 'single', 'basic', 'operation'],
    menu='math/basic'
)
class MathOP(BaseNode):
    """Node that outputs a constant value"""
    
    def initialize(self):
        from haybale_example.types.math import MathOPSelector, MATHOP
        from haybale_core.types.specs import (
            FLOAT,
        )
        from haybale_core.widgets.basic_widgets import (
            NumberWidget,
        )

        # Configure behavior
        self.behavior.is_data_node = True
        self.behavior.is_control_node = False

        # Add inlets with different widget types
        self.add(MathOPSelector.as_inlet(
                id='operator',
                label='Operator',
            ))
        
        self.add(FLOAT.as_inlet(
                id='value_a',
                label='Value A',
                widget=NumberWidget.config(),
                default=0.0
            ))
        
        self.add(FLOAT.as_inlet(
                id='value_b',
                label='Value B',
                widget=NumberWidget.config(),
                default=0.0
            ))

        self.add(FLOAT.as_outlet(
                id='result',
                label='Result'
            ))

    def worker(self, context: ExecutionContext, value_a: float, value_b: float, operator: str) -> dict | None:
        if operator == MathOP.ADD.value:
            result = value_a + value_b
            return None, ('result', result)
        elif operator == MathOP.SUBTRACT.value:
            result = value_a - value_b
            return None, ('result', result)
        elif operator == MathOP.MULTIPLY.value:
            result = value_a * value_b
            return None, ('result', result)
        elif operator == MathOP.DIVIDE.value:
            if value_b != 0:
                result = value_a / value_b
                return None, ('result', result)
            else:
                return None, ('result', 0.0)
        return None
    