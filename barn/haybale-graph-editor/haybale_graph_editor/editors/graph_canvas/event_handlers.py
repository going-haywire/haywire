"""
Event handler registration system for the enhanced graph canvas event system.

This module provides:
- Decorator for registering event handlers
- Type-safe handler registration
- Automatic handler discovery
- build_event_handler_map: scan multiple handler sources into a dispatch map
"""

from typing import Callable, Dict, List, Type

from haywire.core.access import LevelMode
from haywire.ui.components.graph.event_definitions import BaseGraphEvent


def handles_event(*event_classes: Type[BaseGraphEvent], access: LevelMode = LevelMode.EDIT):
    """Decorator to register methods as handlers for specific event classes.

    Args:
        access: The lowest level mode a session needs on the canvas for the
            handler to run. See ``handler_access``.

    Example::

        @handles_event(UserRemoveEvent)  # needs edit
        def process_element_removal(self, event): ...

        @handles_event(SelectionChangedEvent, access=LevelMode.VIEW)  # runs in every mode
        def process_selection_change(self, event): ...
    """

    def decorator(func: Callable):
        # setattr, not attribute assignment: stamping a marker onto a Callable
        # is invisible to the type system, so the direct form fails mypy with
        # "Callable[..., Any] has no attribute _handles_event_classes".
        setattr(func, "_handles_event_classes", event_classes)  # noqa: B010
        setattr(func, "_handles_event_access", access)  # noqa: B010
        return func

    return decorator


def handler_access(handler: Callable) -> LevelMode:
    """Return the level mode ``handler`` needs, as declared by ``@handles_event``; ``EDIT`` if undeclared."""
    return getattr(handler, "_handles_event_access", LevelMode.EDIT)


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
