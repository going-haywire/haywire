from abc import ABC, abstractmethod
import logging
from typing import TYPE_CHECKING, Any, Dict
from nicegui import ui

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.dataclasses import NodeErrorInfo
from haywire.core.ui.renderer.base import IBaseRenderer
from haywire.core.node.base import BaseNode
from haywire.core.node.base import BaseNode
from haywire.core.data.enums import FlowType
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.ports import PortInlet, PortOutlet, DataPort
from haywire.core.ui.widget.base import BaseWidget
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
                widget = self._render_widget(inlet, node.node_id)
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

    def _render_widget(self, inlet: PortInlet, node_id: str) -> BaseWidget | None:
        """Render a widget for the given inlet and return the widget instance.
        
        Note: The UI element is automatically added to the current NiceGUI context.
        
        Args:
            inlet: The inlet port to render a widget for
            node_id: ID of the node containing this inlet
            
        Returns:
            BaseWidget instance or None if widget creation failed
        """        
        widget_instance: BaseWidget | None = None

        try:
            widget_instance = self._get_widget(inlet)
            ui_element = widget_instance.render()
            
            # Apply styling to the UI element if possible
            if hasattr(ui_element, 'classes') and callable(ui_element.classes):
                ui_element.classes('widget-container zoom-pan-lod2')
                
        except Exception as error:
            logging.error(f"Failed to render widget '{inlet.widget}' for inlet '{inlet.id}' in node '{node_id}': {error}", exc_info=True)
            if not isinstance(error, HaywireException):
                error = HaywireException.from_exception(
                    exception=error,
                    category="Widget Render Error",
                    operation="widget_lookup",
                    message=f"Failed to render widget '{inlet.widget}' for inlet '{inlet.id}' in node '{node_id}'"
                ).enrich(
                    registry_key=inlet.widget
                ).log()
            
            error_widget_registry_key = 'unknown'

            try:
                # get the error widget class from the registry
                widget_cls = self.widget_registry._get_error_widget()

                if widget_cls:
                    error_widget_registry_key = widget_cls.class_identity.registry_key
                widget_instance = widget_cls(inlet, error)

                ui_element = widget_instance.render()

            except Exception as e:
                # Fallback to error display if widget creation fails completely
                logging.error(f"Failed to create error widget '{error_widget_registry_key}' for inlet '{inlet.id}' in node '{node_id}': {e}", exc_info=True)

                creationerror = NodeErrorInfo(
                    error='Fatal Error',
                    error_message=str(e)
                )
                creationerror.add_note(f"Check log for details")
                creationerror.add_note(f"Element: {inlet.id}")
                creationerror.add_note(f"Requested widget: {getattr(inlet, 'widget', 'None')}")

                render_error_info(creationerror)
                
                widget_instance = None
    
        return widget_instance

    def _get_widget(self, element: DataPort) -> BaseWidget:
        """
        Get a widget instance for the given element using the widget registry.
        Args:
            element: The DataPort (inlet or outlet) to get the widget for
        Returns:
            BaseWidget: The instantiated widget for the element
        """
 
        key = element.widget

        lc_event = self._render_factory.widget_registry.get_widget_event(key)

        widget_cls = lc_event.affected_class

        widget_instance = None

        if widget_cls is not None:
            try:
                widget_instance = widget_cls(element, lc_event.error)
            except Exception as e:
                # Create detailed error with context about the node instantiation
                error = HaywireException.from_exception(
                    exception=e,
                    category="Widget Instantiation Error",
                    operation="widget_lookup",
                    message=f"Failed to instantiate widget '{key}'"
                ).enrich(
                    registry_key=key,
                    module_name=lc_event.module_name,
                    library_identity=lc_event.library_identity
                )

                raise error

        return widget_instance
