from enum import Enum

class ContainerType(Enum):
    """Defines the container type for inlets and outlets."""
    SINGLE = 'single'
    LIST = 'list'
    DICT = 'dict'
    SET = 'set'
    TUPLE = 'tuple'

class FlowType(Enum):
    """Defines the type of flow for inlets and outlets."""
    CONTROL = 'control'
    DATA = 'data'
    CALLBACK = 'callback'
    NONE = 'none'

