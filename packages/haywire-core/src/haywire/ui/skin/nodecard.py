from typing import Callable, Dict, Optional
from nicegui import ui

from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui.errors.error_info import error_render_detail
from haywire.ui.widget.interface import IWidget


class UINodeCard:
    """
    Container for a rendered node's UI elements and widget instances.

    Holds the NiceGUI card element and mappings to all widget instances
    for easy access and management.
    """

    def __init__(self):
        """
        Initialize UINodeCard with UI elements and widget instances.

        Args:
            ui_card: The main NiceGUI card element
            ui_elements: Mapping of element IDs to UI elements
            widget_instances: Mapping of element IDs to widget instances
        """
        self.ui_card: ui.card = ui.card()
        self.widget_instances = {}
        self._cleanups: list[Callable[[], None]] = []

    def get_card(self):
        """Get the main NiceGUI card element."""
        return self.ui_card

    def set_widget_instances(self, widget_instances: Dict[str, IWidget]):
        """Set the widget instances mapping."""
        self.widget_instances = widget_instances

    def get_widget_instance(self, element_id: str) -> Optional["IWidget"]:
        """Get a widget instance by element ID."""
        return self.widget_instances.get(element_id)

    def append(self, error: HaywireException):
        """Append an error message to the UI card."""
        if error is not None:
            with self.ui_card:
                error_render_detail(error)

    def add_cleanup(self, callback: Callable[[], None]) -> None:
        """Run *callback* when this card is cleaned up, after its widgets, once."""
        self._cleanups.append(callback)

    def cleanup(self):
        """Clean up all widget instances, then run the added cleanups once each."""
        for _element_id, widget in self.widget_instances.items():
            if widget:
                widget.cleanup()
        cleanups, self._cleanups = self._cleanups, []
        for callback in cleanups:
            callback()
