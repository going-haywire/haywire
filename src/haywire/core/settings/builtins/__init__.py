# haywire/core/settings/builtins/__init__.py
"""
Built-in settings definitions.

Settings are organized into separate modules by category/aspect.
Each module exports a `register(registry)` function.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import GlobalSettingsRegistry
    from ..holder import SettingsHolder

# Import all builtin modules
from . import ui_node
from . import ui_edge
from . import ui_canvas
from . import ui_minimap
from . import execution
from . import debug
from . import editor
from . import node_instance

# Registry of all builtin modules (for global settings)
_BUILTIN_MODULES = [
    ui_node,
    ui_edge,
    ui_canvas,
    ui_minimap,
    execution,
    debug,
    editor,
]


def register_all(registry: 'GlobalSettingsRegistry') -> None:
    """
    Register all built-in global settings.
    
    Iterates through all builtin modules and calls their register() function.
    
    Args:
        registry: The global settings registry
    """
    for module in _BUILTIN_MODULES:
        module.register(registry)


def register_node_instance_settings(holder: 'SettingsHolder') -> None:
    """
    Register local-only settings for a node instance.
    
    Called during node initialization.
    
    Args:
        holder: The node's SettingsHolder instance
    """
    node_instance.register_node_instance_settings(holder)


def register_module(registry: 'GlobalSettingsRegistry', module_name: str) -> bool:
    """
    Register settings from a specific module.
    
    Args:
        registry: The global settings registry
        module_name: Name of the module (e.g., 'ui_node', 'execution')
        
    Returns:
        True if module was found and registered, False otherwise
    """
    for module in _BUILTIN_MODULES:
        if module.__name__.endswith(module_name):
            module.register(registry)
            return True
    return False


def list_modules() -> list[str]:
    """
    List all available builtin setting modules.
    
    Returns:
        List of module names
    """
    return [m.__name__.split('.')[-1] for m in _BUILTIN_MODULES]