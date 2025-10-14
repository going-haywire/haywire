"""
Core widget registration and exports
"""

from haywire.core.inventory.library import BaseLibrary
from haywire.core.inventory.registry.widget_reg import WidgetRegistry

def register_widgets(library: BaseLibrary):
    """Register all widgets within this folder with the widget registry"""

    library.add_folder_to_registry(__path__[0], WidgetRegistry)

__all__ = [
    'register_widgets'
]
