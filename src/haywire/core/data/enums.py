from enum import Enum

class FlowType(Enum):
    """Defines the type of flow for inlets and outlets."""
    CTRL = 'control'
    DATA = 'data'
    CALLBACK = 'callback'
    NONE = 'none'

