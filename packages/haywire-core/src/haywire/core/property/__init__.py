# haywire/core/property/__init__.py
"""
Property system — observable descriptors with shared metadata contract.

    FieldDescriptor    — base: metadata + __set_name__ + class-level __get__
    prop               — reactive instance property (for Bag subclasses)
    Bag                — observable property container (subscribe, to_dict, reset)
"""

from .base import FieldDescriptor
from .descriptor import prop
from .bag import Bag

__all__ = [
    'FieldDescriptor',
    'prop',
    'Bag',
]
