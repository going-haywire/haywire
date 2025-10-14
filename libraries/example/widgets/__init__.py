"""
Test widgets for the test library
"""

from typing import Dict

from haywire.core.inventory.folder_scan_for_classes import folder_scan_for_classes
from haywire.core.inventory.library import BaseLibrary
from haywire.core.inventory.registry.widget_reg import WidgetRegistry
from haywire.core.ui.base_widget import is_widget

def register_widgets(library: BaseLibrary):
    """Register widgets with the widget registry"""

    widgets = folder_scan_for_classes(
        library_path=__path__[0],
        library=library,
        class_filter=is_widget
    )

    reg: WidgetRegistry = library.get_registry(WidgetRegistry)
    if reg:
        # Register all discovered widgets
        for widget_class in widgets:
            reg._register(widget_class, library.identity)

__all__ = [
    'register_widgets'
]
