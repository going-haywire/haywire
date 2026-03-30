from abc import ABC, abstractmethod
from ast import Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

import nicegui.ui as ui

from haywire.core.library.identity import LibraryIdentity
from haywire.core.types import DataPort
from haywire.ui.ui_nodecard import UINodeCard
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.registry.identity import BaseIdentity

from ..widget.base import BaseWidget
from ..widget.factory_interface import IWidgetFactory
from .interface import IBaseSkin


@dataclass
class SkinIdentity(BaseIdentity):
    """Core identifying attributes of a skin"""

    _is_default: bool = False
    _default_priority: int = 0
    _is_error: bool = False
    _error_priority: int = 0


class BaseSkin(IBaseSkin, ABC):
    """
    Abstract base class for all NodeSkin classes.

    NodeSkin classes define the look and structure of nodes.
    They are cached and reused by the SkinFactory.
    """

    class_identity: SkinIdentity
    class_library: LibraryIdentity

    def __init__(self, widget_factory: IWidgetFactory):
        """
        Initialize the skin with a widget factory.

        Args:
            widget_factory: Factory for creating widget instances
        """
        self._widget_factory: IWidgetFactory = widget_factory
        self._nodeids_widget_instances: Dict[str, Dict[str, BaseWidget]] = {}

    def _render(self, wrapper: NodeWrapper) -> UINodeCard:
        ui_nodeCard: UINodeCard = UINodeCard()
        try:
            # Initialize node_id storage for widget instances
            self._nodeids_widget_instances[wrapper.node_id] = {}

            self.render(ui_nodeCard.get_card(), wrapper)

            ui_nodeCard.set_widget_instances(self._nodeids_widget_instances[wrapper.node_id])

            # Clear widget instances for next render
            self._nodeids_widget_instances[wrapper.node_id] = {}

            return ui_nodeCard

        except Exception:
            # Clean up any partially created UI elements
            if ui_nodeCard is not None:
                try:
                    # Remove all children and delete the main card
                    ui_card = ui_nodeCard.get_card()
                    ui_card.clear()
                    ui_card.delete()
                except Exception as cleanup_error:
                    logger.error(f"Error during UI cleanup: {cleanup_error}")

            # Re-raise the original exception so the factory can handle it
            raise

    @abstractmethod
    def render(self, main_card: ui.card, wrapper: NodeWrapper) -> UINodeCard:
        """
        Render a node into the main_card.

        Usage:
        ```
        # Set up main card appearance
        main_card.classes().style()

        with main_card:
            # Add UI elements here
        ```
        Args:
            main_card: The NiceGUI ui.card() element to render the node into
            wrapper: The NodeWrapper containing the HaywireNode to render

        """
        pass

    def render_widget(self, port: DataPort, node_id: str, classes: str = "") -> ui.element | None:
        """
        Render a widget for the given inlet and node ID.

        Args:
            port: The data port inlet to render the widget for
            node_id: The unique identifier of the node
            classes: Additional CSS classes to apply to the widget ui_element container
        Returns:
            The rendered widget ui_element container, or None if no widget was rendered
        """
        widget_instance, ui_element = self._widget_factory.render_widget(
            registry_key=port.widget_key, port=port, node_id=node_id
        )

        # Apply styling to the UI element if possible
        if ui_element and hasattr(ui_element, "classes") and callable(ui_element.classes):
            ui_element.classes(classes)

        if widget_instance:
            self._nodeids_widget_instances.setdefault(node_id, {port.id, widget_instance})

        return ui_element
