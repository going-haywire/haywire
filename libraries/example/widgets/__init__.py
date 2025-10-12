"""
Test widgets for the test library
"""

from typing import Dict

from haywire.core.inventory.folder_scan import folder_scan_for_classes
from haywire.core.inventory.registry.widget_reg import WidgetRegistry
from haywire.core.ui.base_widget import is_widget

def register_widgets(library):
    """Register widgets with the widget registry"""

    widgets = folder_scan_for_classes(
        library_path=__path__[0],
        metadata=library.metadata,
        class_filter=is_widget
    )

    reg = library.get_registry(WidgetRegistry)
    if reg:
        # Register all discovered widgets
        for widget_class in widgets:
            reg.register_widget(widget_class, library.metadata)

__all__ = [
    'register_widgets'
]
