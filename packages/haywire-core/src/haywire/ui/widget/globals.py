# haywire/core/ui/widget/globals.py
"""
Global widget registry for type validation.

This module provides a simple module-level dictionary that maps widget registry keys
to widget classes. This allows type validation during port creation without requiring
DI container access.
"""

from typing import Dict, Type, Optional, TYPE_CHECKING


if TYPE_CHECKING:
    from .interface import IWidget

# Global widget class lookup
WIDGET_REGISTRY: Dict[str, Type["IWidget"]] = {}


def register_widget_globally(registry_key: str, widget_cls: Type["IWidget"]) -> None:
    """
    Register a widget class globally for validation purposes.

    Args:
        registry_key: Widget registry key (e.g., 'core:widget:number.widget')
        widget_cls: Widget class to register
    """
    WIDGET_REGISTRY[registry_key] = widget_cls


def unregister_widget_globally(registry_key: str) -> None:
    """
    Unregister a widget class from global registry.

    Args:
        registry_key: Widget registry key to unregister
    """
    if registry_key in WIDGET_REGISTRY:
        del WIDGET_REGISTRY[registry_key]


def get_widget_class(registry_key: str) -> Optional[Type["IWidget"]]:
    """
    Get widget class by registry key.

    Args:
        registry_key: Widget registry key

    Returns:
        Widget class or None if not found
    """
    return WIDGET_REGISTRY.get(registry_key)


def list_all_widgets() -> Dict[str, Type["IWidget"]]:
    """
    Get all registered widgets.

    Returns:
        Dictionary of registry_key -> widget_class
    """
    return dict(WIDGET_REGISTRY)
