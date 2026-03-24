"""
Event handler registration system for the enhanced graph canvas event system.

This module provides:
- Decorator for registering event handlers
- Type-safe handler registration
- Automatic handler discovery
"""

from typing import Callable, Type
from .event_definitions import BaseGraphEvent


def handles_event(*event_classes: Type[BaseGraphEvent]):
    """Decorator to register methods as handlers for specific event classes"""

    def decorator(func: Callable):
        func._handles_event_classes = event_classes
        return func

    return decorator
