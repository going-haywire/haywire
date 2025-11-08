from enum import Enum


class DataType(Enum):
    """Defines the fundamental data types a node can handle."""
    INT = 'int'
    FLOAT = 'float'
    STRING = 'str'
    BOOL = 'bool'
    BYTES = 'bytes'
    DICT = 'dict'
    LIST = 'list'
    OBJECT = 'object'
    CUSTOM = 'custom'  # For library-defined custom types


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
