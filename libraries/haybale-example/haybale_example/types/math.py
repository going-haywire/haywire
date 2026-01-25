# Custom data type for testing
from enum import Enum
from haywire.core.types.decorator import type
from haybale_core.types.specs import STRING

MATHOP: list[str] = [
    'add',
    'subtract',
    'multiply',
    'divide'
]

class MathOP(Enum):
    ADD = 'add'
    SUBTRACT = 'subtract'
    MULTIPLY = 'multiply'
    DIVIDE = 'divide'
    
    @classmethod
    def values(cls):
        return [e.value for e in cls]
    
    @classmethod
    def names(cls):
        return [e.name for e in cls]

@type(
    label='Simple Operations',
    description='Simple mathematical operations for one or two float values',
    widget_key='core:widget:SelectWidget',
    widget_config={'properties': {'options': MathOP.values()}},
    default=MathOP.ADD.value
)
class MathOPSelector(STRING):
    """
    A custom type representing simple mathematical operations.
    """
    pass
