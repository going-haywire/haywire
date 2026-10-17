from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import nicegui.ui as ui

from haywire.core.access import LevelMode
from haywire.core.types import DataPort, WidgetModel
from haywire.ui.widget.interface import IWidget

if TYPE_CHECKING:
    from haywire.core.graph.edit_route import EditRoute


class IWidgetFactory(ABC):
    """
    Interface for Widget Factory classes.
    """

    @abstractmethod
    def render_widget(
        self,
        registry_key: str,
        port: DataPort | WidgetModel,
        node_id: str,
        *,
        route: EditRoute | None = None,
        minimum: LevelMode = LevelMode.EDIT,
    ) -> tuple[IWidget | None, ui.element]:
        """Render a widget for the given inlet and return the widget instance.

        Note: The UI element is automatically added to the current NiceGUI context.

        Args:
            registry_key: The registry key of the widget to render
            port: The data port to render a widget for, or a model the caller built,
                which the widget binds to as given.
            node_id: ID of the node containing this inlet
            route: Where the widget's writes to a data port go; ``None`` refuses
                every write to a data port.
            minimum: The lowest level mode at which *route* lets a write through.
        Returns:
            IWidget instance or None if widget creation failed
        """
        pass
