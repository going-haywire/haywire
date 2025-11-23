from abc import ABC, abstractmethod
import logging
from typing import TYPE_CHECKING, Any, Dict
from nicegui import ui

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.dataclasses import NodeErrorInfo
from haywire.core.ui.renderer.base import IBaseRenderer, UINodeCard
from haywire.core.node.base import BaseNode
from haywire.core.node.base import BaseNode
from haywire.core.data.enums import FlowType
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.ports import PortInlet, PortOutlet, DataPort
from haywire.core.ui.widget.base import BaseWidget
from haywire.ui.renderer.widget_factory import NodeIDsBatchCallback
from ..errors.error_info import render_error_info

from ..themes.colors import Theme_UI_Color
from ..utils import generate_pin_uuid
from ..themes import ThemePalette
from .factory import RenderFactory


class NodeRenderer(IBaseRenderer, ABC):
    """
    Base class for all NiceGui NodeRenderer classes.

    NodeRenderer classes are stateless and define the look and structure of nodes.
    They are cached and reused by the NodeRenderFactory.
    """

    def __init__(self, render_factory: RenderFactory):
        """
        Initialize the renderer with a render factory.

        Args:
            render_factory: Factory for creating UINodeCard instances
        """
        self._render_factory: RenderFactory = render_factory
        self.main_card: ui.card | None = None


    def _render(self, wrapper: NodeWrapper) -> UINodeCard:
        self.main_card = None
        try:
            return self.render(wrapper)
        except Exception as error:
            # Clean up any partially created UI elements
            if self.main_card is not None:
                try:
                    # Remove all children and delete the main card
                    self.main_card.clear()
                    self.main_card.delete()
                except Exception as cleanup_error:
                    logging.error(f"Error during UI cleanup: {cleanup_error}")
            
            # Re-raise the original exception so the factory can handle it
            raise


    def _render_inlet(self, inlet: PortInlet, ui_elements: Dict[str, Any], widget_instances: Dict[str, BaseWidget], node: BaseNode):
        """Render an inlet with its port and optional widget."""
        with ui.row().classes('w-full items-center justify-start gap-1'):
            # only render pins for inlets that are actually involved in flows
            self._render_pin(inlet, direction='left', node=node)

            # Pin label
            ui.label(inlet.label).classes('text-xs zoom-pan-lod2')

        # Render inlet widget if it has a pin that is not pooled (is_pooled == False)
        if inlet.is_pooled == False:
            if inlet.widget:
                # Widget rendering adds UI element to current context automatically
                widget = self._render_factory.widget_factory.render_widget(inlet, node.node_id)
                if widget:
                    widget_instances[inlet.id] = widget

    
    def _render_outlet(self, outlet, node: BaseNode):
        """Render an outlet with its port."""
        with ui.row().classes('w-full items-center justify-end gap-1'):
            # Pin label
            ui.label(outlet.label).classes('text-xs')

            # only render pins for inlets that are actually involved in flows
            self._render_pin(outlet, direction='right', node=node)
    
    def _render_pin(self, pin: DataPort, direction: str = 'left', node: BaseNode = None):
        """Render a pin with connection system compatibility."""
        # Create unique pin ID and determine port type for connection system
        pin_direction = 'inlet' if pin.is_inlet() else 'outlet'
        pin_uuid = generate_pin_uuid(pin_direction, node.node_id, pin.id)
        
        # Calculate 2D direction vector components based on pin type
        if pin.is_inlet():
            # Inlets point left (negative X)
            dir_x, dir_y = "-1", "0"
        else:
            # Outlets point right (positive X)
            dir_x, dir_y = "1", "0"
        
        common_props = (
            f'id="{pin_uuid}" '
            f'data-node-id="{node.node_id}" '
            f'data-pin-id="{pin.id}" '
            f'data-pin-flow-type="{pin.flow_type}" '
            f'data-pin-dir="{pin_direction}" '
            f'data-pin-dir-x="{dir_x}" '
            f'data-pin-dir-y="{dir_y}"'
        )
        
        if pin.flow_type == FlowType.CTRL:
            # Get control flow color from theme
            ctrl_color = ThemePalette.flow_type(FlowType.CTRL)
            # Pin connector
            ui.icon('label', color=ctrl_color, size='xs').classes(
                'text-4xl port input-port connection-pin zoom-pan-lod0'
            ).style(
                f'position: absolute; {direction}: -20px; '
                f'cursor: crosshair;'
            ).props(
                f'{common_props} '
                f'data-pin-color="{ctrl_color}"'
            )
        elif pin.flow_type == FlowType.CALLBACK:
            # Get callback flow color from theme
            callback_color = ThemePalette.flow_type(FlowType.CALLBACK)
            # Pin connector
            ui.icon('replay_circle_filled', color=callback_color, size='xs').classes(
                'text-4xl port input-port connection-pin zoom-pan-lod0'
            ).style(
                f'position: absolute; {direction}: -20px; '
                f'cursor: crosshair;'
            ).props(
                f'{common_props} '
                f'data-pin-color="{callback_color}"'
            )
        elif pin.flow_type == FlowType.DATA:
            pin_color = ThemePalette.data_type(pin.type_cls, pin.color)
            port_border = ThemePalette.ui(Theme_UI_Color.PORT_BORDER, 'white')
            ui.element('div').classes(
                'port output-port connection-pin zoom-pan-lod0'
            ).style(
                f'position: absolute; {direction}: -20px; '
                f'width: 15px; height: 15px; '
                f'background: {pin_color}; '
                f'border: 2px solid {port_border}; '
                f'border-radius: 50%; '
                f'cursor: crosshair;'
            ).props(
                f'{common_props} '
                f'data-pin-data-type="{pin.data.type}" '
                f'data-pin-color="{pin_color}"'
            )

