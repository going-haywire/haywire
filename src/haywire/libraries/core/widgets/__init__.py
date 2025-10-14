"""
Core widget registration and exports
"""

from haywire.core.inventory.library import BaseLibrary
from haywire.core.inventory.registry.widget_reg import WidgetRegistry
from haywire.core.inventory.folder_scan_for_classes import folder_scan_for_classes
from haywire.core.ui.base_widget import is_widget

# Import all widget classes
from .error_widget import ErrorWidget
from .basic_widgets import (
    TextInputWidget, 
    NumberWidget, 
    CheckboxWidget, 
    SwitchWidget
)
from .display_widgets import (
    LabelWidget
)


def register_widgets(library: BaseLibrary):
    """Register all core widgets with the widget registry"""

    widgets = folder_scan_for_classes(
        library_path=__path__[0],
        library=library,
        class_filter=is_widget
    )

    reg: WidgetRegistry = library.get_registry(WidgetRegistry)
    if reg:
        # Register all discovered widgets (default_for and error flags will be handled automatically)
        for widget_class in widgets:
            reg._register(widget_class, library.identity)


__all__ = [
    'ErrorWidget', 
    'TextInputWidget',
    'NumberWidget',
    'CheckboxWidget',
    'SwitchWidget',
    'LabelWidget',
    'register_widgets'
]
