from enum import Enum

class FlowType(Enum):
    """Defines the type of flow for inlets and outlets."""
    CONTROL = 'control'
    DATA = 'data'
    CALLBACK = 'callback'
    NONE = 'none'

