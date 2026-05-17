"""
Event handler registration system for the enhanced graph canvas event system.

This module provides:
- Decorator for registering event handlers
- Type-safe handler registration
- Automatic handler discovery
- build_event_handler_map: scan multiple handler sources into a dispatch map
"""

from typing import Callable, Dict, List, Type
from haywire.ui.components.graph.event_definitions import BaseGraphEvent


def handles_event(*event_classes: Type[BaseGraphEvent]):
    """Decorator to register methods as handlers for specific event classes"""

    def decorator(func: Callable):
        setattr(func, "_handles_event_classes", event_classes)
        return func

    return decorator


def build_event_handler_map(sources: List[object]) -> Dict[str, Callable]:
    """
    Build an event-type → handler mapping by scanning a list of handler sources.

    For each source object, scans all methods for the ``_handles_event_classes``
    attribute set by the ``@handles_event`` decorator.  When two sources register
    the same event type the later source wins.

    Args:
        sources: Objects whose methods should be scanned for ``@handles_event``.

    Returns:
        Dict mapping event_type strings to bound handler methods.
    """
    handlers: Dict[str, Callable] = {}
    for source in sources:
        for method_name in dir(source):
            method = getattr(source, method_name)
            if hasattr(method, "_handles_event_classes"):
                for event_class in method._handles_event_classes:
                    handlers[event_class.event_type] = method
    return handlers
