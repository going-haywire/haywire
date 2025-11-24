from abc import ABC, abstractmethod
from ast import Dict
from dataclasses import dataclass
import logging

import nicegui.ui as ui

from haywire.core.types.ports import DataPort
from haywire.core.ui.widget.base import BaseWidget
from haywire.ui.renderer.factory_interface import IRenderFactory
from haywire.ui.ui_nodecard import UINodeCard

from ...node.node_wrapper import NodeWrapper
from ...registry.identity import BaseIdentity
from .interface import IBaseRenderer

@dataclass
class RendererIdentity(BaseIdentity):
    """Core identifying attributes of a renderer"""
    is_default: bool = False
    is_error: bool = False

 
class BaseRenderer(IBaseRenderer, ABC):
    """
    Abstract base class for all NodeRenderer classes.

    NodeRenderer classes define the look and structure of nodes.
    They are cached and reused by the NodeRenderFactory.
    """

    def __init__(self, render_factory: IRenderFactory):
        """
        Initialize the renderer with a render factory.

        Args:
            render_factory: Factory for creating UINodeCard instances
        """
        self._render_factory: IRenderFactory = render_factory
        self._nodeids_widget_instances: Dict[str, Dict[str, BaseWidget]] = {}


    def _render(self, wrapper: NodeWrapper) -> UINodeCard:
        try:
            main_card: ui.card = ui.card()
            # Initialize node_id storage for widget instances
            self._nodeids_widget_instances[wrapper.node_id] = {}

            self.render(main_card,wrapper)

            node_card = UINodeCard(main_card, self._nodeids_widget_instances[wrapper.node_id])

            # Clear widget instances for next render
            self._nodeids_widget_instances[wrapper.node_id] = {}

            return node_card
        
        except Exception as error:
            # Clean up any partially created UI elements
            if main_card is not None:
                try:
                    # Remove all children and delete the main card
                    main_card.clear()
                    main_card.delete()
                except Exception as cleanup_error:
                    logging.error(f"Error during UI cleanup: {cleanup_error}")
            
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

    def render_widget(self, inlet: DataPort, node_id: str) -> BaseWidget | None:
        """
        Render a widget for the given inlet and node ID.
        
        Args:
            inlet: The data port inlet to render the widget for
            node_id: The unique identifier of the node 
        Returns:
            The rendered widget instance, or None if no widget was rendered
        """
        widget_instance: BaseWidget | None = self._render_factory.render_widget(inlet, node_id)

        if widget_instance:
            self._nodeids_widget_instances.setdefault(node_id, {inlet.id, widget_instance})

        return widget_instance





