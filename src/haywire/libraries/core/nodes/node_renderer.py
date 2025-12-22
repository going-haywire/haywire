from abc import ABC
from nicegui import ui

from haywire.core.data.enums import FlowType
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.ports import PortInlet, DataPort

from haywire.ui.renderer.base import BaseRenderer
from haywire.ui.themes.colors import Theme_UI_Color
from haywire.ui.utils import generate_pin_uuid
from haywire.ui.themes import ThemePalette

class NodeRenderer(BaseRenderer, ABC):
    """
    Base class for all NiceGui NodeRenderer classes.

    NodeRenderer classes are stateless and define the look and structure of nodes.
    They are cached and reused by the NodeRenderFactory.
    """


    def _render_inlet(self, inlet: PortInlet, wrapper: NodeWrapper):
        """Render an inlet with its port and optional widget."""
        with ui.row().classes('w-full items-center justify-start gap-1'):
            # only render pins for inlets that are actually involved in flows
            self._render_pin(inlet, wrapper, direction='left')

            # Pin label
            ui.label(inlet.label).classes('text-xs zoom-pan-lod2')

        # Render inlet widget if it has a pin that is not pooled (is_pooled == False)
        if not inlet.allow_multiple_connections:
            if inlet.widget:
                # Widget rendering adds UI element to current context automatically
                self.render_widget(inlet, wrapper.node_id)

    
    def _render_outlet(self, outlet, wrapper: NodeWrapper):
        """Render an outlet with its port."""
        with ui.row().classes('w-full items-center justify-end gap-1'):
            # Pin label
            ui.label(outlet.label).classes('text-xs')

            # only render pins for inlets that are actually involved in flows
            self._render_pin(outlet, wrapper, direction='right')
    
    def _render_pin(self, pin: DataPort,  wrapper: NodeWrapper, direction: str = 'left'):
        """Render a pin with connection system compatibility."""
        # Create unique pin ID and determine port type for connection system
        pin_direction = 'inlet' if pin.is_inlet() else 'outlet'
        pin_uuid = generate_pin_uuid(pin_direction, wrapper.node_id, pin.id)
        
        # Calculate 2D direction vector components based on pin type
        if pin.is_inlet():
            # Inlets point left (negative X)
            dir_x, dir_y = "-1", "0"
        else:
            # Outlets point right (positive X)
            dir_x, dir_y = "1", "0"
        
        common_props = (
            f'id="{pin_uuid}" '
            f'data-node-id="{wrapper.node_id}" '
            f'data-pin-id="{pin.id}" '
            f'data-pin-flow-type="{pin.flow_type}" '
            f'data-pin-dir="{pin_direction}" '
            f'data-pin-dir-x="{dir_x}" '
            f'data-pin-dir-y="{dir_y}"'
        )
        
        if pin.flow_type == FlowType.CONTROL:
            # Get control flow color from theme
            ctrl_color = ThemePalette.flow_type(FlowType.CONTROL)
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
            pin_data_type = pin.data.type_cls.class_identity.registry_key
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
                f'data-pin-data-type="{pin_data_type}" '
                f'data-pin-color="{pin_color}"'
            )

