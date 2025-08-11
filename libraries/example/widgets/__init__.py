"""
Test widgets for the test library
"""

from typing import Dict

from haywire.core.inventory.folder_scan import folder_scan_for_classes
from haywire.core.inventory.base import LibraryMetadata
from haywire.core.inventory.registry.widget import WidgetRegistry
from haywire.core.ui.base import is_widget

def register_widgets(widget_registry: WidgetRegistry, library_metadata: LibraryMetadata):
    """Register test widgets with the widget registry"""

    widgets = folder_scan_for_classes(
        library_path=__path__[0],
        class_filter=is_widget
    )

    # Register all discovered widgets
    for widget_class in widgets:
        widget_registry.register_widget(widget_class, library_metadata)

__all__ = [
    'register_widgets'
]
