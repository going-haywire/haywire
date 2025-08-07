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


class DataCategory(Enum):
    """Defines the category or structure of the data."""
    SCALAR = 'scalar'
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
