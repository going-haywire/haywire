from enum import Enum

class DataContainerType(Enum):
    """Defines the container or structure of the data."""
    SINGLE = 'single'
    TUPLE = 'tuple'
    LIST = 'list'
    SET = 'set'
    DICT = 'dict'


class FlowType(Enum):
    """Defines the type of flow for inlets and outlets."""
    CTRL = 'control'
    DATA = 'data'
    CALLBACK = 'callback'
    NONE = 'none'

class SocketType(Enum):
    """Defines the socket type. It is either an inlet or an outlet."""
    INLET = 'inlet'
    OUTLET = 'outlet'
