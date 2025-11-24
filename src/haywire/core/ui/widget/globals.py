# haywire/core/ui/widget/globals.py
"""
Global widget registry for type validation.

This module provides a simple module-level dictionary that maps widget registry keys
to widget classes. This allows type validation during port creation without requiring
DI container access.
"""

from typing import Dict, Type, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseWidget
    from ...types.interface import IType

# Global widget class lookup
WIDGET_REGISTRY: Dict[str, Type['BaseWidget']] = {}


def register_widget_globally(registry_key: str, widget_cls: Type['BaseWidget']) -> None:
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


def get_widget_class(registry_key: str) -> Optional[Type['BaseWidget']]:
    """
    Get widget class by registry key.
    
    Args:
        registry_key: Widget registry key
        
    Returns:
        Widget class or None if not found
    """
    return WIDGET_REGISTRY.get(registry_key)


def validate_widget_type_compatibility(
    widget_registry_key: str,
    type_cls: Type['IType']
) -> tuple[bool, Optional[str]]:
    """
    Validate if a widget is compatible with a given type.
    
    Args:
        widget_registry_key: Widget registry key
        type_cls: The type class to validate against
        
    Returns:
        Tuple of (is_compatible, error_message)
    """
    widget_class = get_widget_class(widget_registry_key)
    
    if widget_class is None:
        return True, None
    # If widget class not found, skip validation. This will be caught later during widget instantiation.
    #    return False, f"Widget '{widget_registry_key}' not found in global registry"
    


    # If widget has no type constraints, it accepts all types
    if len(widget_class.class_identity.compatible_types) == 0:
        return True, None
    
    # Check if type_cls is compatible
    compatible_types: Set[Type[IType]] = widget_class.class_identity.compatible_types
    
    for compatible_type in compatible_types:
        try:
            if issubclass(type_cls, compatible_type):
                return True, None
        except TypeError:
            # Handle case where type_cls or compatible_type isn't a class
            continue
    
    # Not compatible
    compatible_names = [t.__name__ for t in compatible_types]
    error_msg = (
        f"Widget '{widget_registry_key}' is not compatible with type '{type_cls.__name__}'. "
        f"Compatible types: {compatible_names}"
    )
    return False, error_msg


def list_all_widgets() -> Dict[str, Type['BaseWidget']]:
    """
    Get all registered widgets.
    
    Returns:
        Dictionary of registry_key -> widget_class
    """
    return dict(WIDGET_REGISTRY)