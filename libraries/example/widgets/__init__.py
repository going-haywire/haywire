"""
Test widgets for the test library
"""

from typing import Dict

from haywire.core.registry.auto_discover import auto_discover_classes, is_widget
from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.registry import WidgetRegistry

def register_widgets(widget_registry: WidgetRegistry, library_metadata: LibraryMetadata):
    """Register test widgets with the widget registry"""

    widgets = auto_discover_classes(
        library_path=__path__[0],
        class_filter=is_widget
    )

    # Register all discovered widgets
    for widget_class in widgets:
        widget_registry.register_widget(widget_class, library_metadata)

__all__ = [
    'register_widgets'
]
