from abc import ABC
from nicegui import ui

from haywire.core.data.enums import FlowType
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.base import CompoundType, PrimitiveType
from haywire.core.types.ports import PortInlet, DataPort

from haywire.ui.renderer.base import BaseRenderer
from haywire.ui.themes.icons import ICONS
from haywire.ui.themes.keys import ThemeKey
from haywire.ui.utils import generate_pin_uuid
from haywire.ui.themes import ThemePalette

class NodeRenderer(BaseRenderer, ABC):
    """
    Base class for all NiceGui NodeRenderer classes.

    NodeRenderer classes are stateless and define the look and structure of nodes.
    They are cached and reused by the NodeRenderFactory.
    """

    def _render_inlet(self, inlet: PortInlet, wrapper: NodeWrapper, widget_classes: str = ''):
        """Render an inlet with its port and optional widget."""
        with ui.row().classes('w-full items-center justify-start gap-0'):
            # only render pins for inlets that are actually involved in flows
            self._render_pin(inlet, wrapper, direction='left')

            # Pin label
            ui.label(inlet.label).classes('text-xs zoom-pan-lod2')

        # Render inlet widget if it has a pin that does not allow multiple connections
        if not inlet.allow_multiple_connections:
            if inlet.widget:
                # Widget rendering adds UI element to current context automatically
                self.render_widget(inlet, wrapper.node_id, classes=widget_classes)

    
    def _render_outlet(self, outlet, wrapper: NodeWrapper, widget_classes: str = ''):
        """Render an outlet with its port."""
        with ui.row().classes('w-full items-center justify-end gap-0'):
            # Pin label
            ui.label(outlet.label).classes('text-xs')

            # only render pins for outlets that are actually involved in flows
            self._render_pin(outlet, wrapper, direction='right')
    
    def _render_pin(self, pin: DataPort, wrapper: NodeWrapper, direction: str = 'left'):
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
            ctrl_color = pin.color
            # Pin connector
            if pin.is_inlet():
                ctrl_icon = ThemePalette.get(
                    ThemeKey.UI_PORT_ICON_IN_CTRL,
                    pin.icon_in,
                    ICONS.JOIN_LEFT
                )
            else:
                ctrl_icon = ThemePalette.get(
                    ThemeKey.UI_PORT_ICON_OUT_CTRL,
                    pin.icon_out,
                    ICONS.JOIN_RIGHT
                )
            ui.icon(ctrl_icon, color=ctrl_color, size='xs').classes(
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
            callback_color = pin.color
            if pin.is_inlet():
                callback_icon = ThemePalette.get(
                    ThemeKey.UI_PORT_ICON_IN_CALLBACK,
                    pin.icon_in,
                    ICONS.SWIPE_LEFT_ALT
                )
            else:
                callback_icon = ThemePalette.get(
                    ThemeKey.UI_PORT_ICON_OUT_CALLBACK,
                    pin.icon_out,
                    ICONS.SWIPE_RIGHT_ALT
                )
            # Pin connector
            ui.icon(callback_icon, color=callback_color, size='20px').classes(
                'text-4xl port input-port connection-pin zoom-pan-lod0'
            ).style(
                f'position: absolute; {direction}: -20px; '
                f'cursor: crosshair;'
            ).props(
                f'{common_props} '
                f'data-pin-color="{callback_color}"'
            )
        elif pin.flow_type == FlowType.DATA:
            pin_color = pin.data.get_stored_type().class_identity.color
            pin_data_type = pin.data.get_stored_type().class_identity.registry_key
            # Get pin color: try data type specific, use pin.color as preference
            if pin.is_inlet():
                if pin.allow_multiple_connections:
                    if issubclass(pin.data.get_stored_type(), CompoundType):
                        data_icon = ThemePalette.get(
                            ThemeKey.UI_PORT_ICON_IN_MULTI_COMPOUND,
                            pin.data.get_stored_type().class_identity.icon_in_multi,
                            fallback=ICONS.WEB_STORIES
                        )
                    else:
                        data_icon = ThemePalette.get(
                            ThemeKey.UI_PORT_ICON_IN_MULTI_SINGLE,
                            pin.data.get_stored_type().class_identity.icon_in_multi,
                            fallback=ICONS.FIBER_SMART_RECORD
                        )
                else:
                    if issubclass(pin.type_cls, CompoundType):
                        data_icon = ThemePalette.get(
                            ThemeKey.UI_PORT_ICON_IN_COMPOUND,
                            pin.data.get_stored_type().class_identity.icon_in,
                            fallback=ICONS.VIEW_DAY
                        )
                    else:
                        data_icon = ThemePalette.get(
                            ThemeKey.UI_PORT_ICON_IN_SINGLE,
                            pin.data.get_stored_type().class_identity.icon_in,
                            fallback=ICONS.MY_LOCATION
                        )
            else:
                if issubclass(pin.type_cls, CompoundType):
                    data_icon = ThemePalette.get(
                        ThemeKey.UI_PORT_ICON_OUT_MULTI_COMPOUND,
                        pin.data.get_stored_type().class_identity.icon_out_multi,
                        fallback=ICONS.VIEW_DAY
                    )
                else:
                    data_icon = ThemePalette.get(
                        ThemeKey.UI_PORT_ICON_OUT_MULTI_SINGLE,
                        pin.data.get_stored_type().class_identity.icon_out_multi,
                        fallback=ICONS.CIRCLE
                    )
            with ui.icon(data_icon, color=pin_color, size='15px').classes(
                    'text-4xl port connection-pin zoom-pan-lod0'
                ).style(
                    f'position: absolute; {direction}: -20px; '
                    f'cursor: crosshair;'
                ).props(
                    f'{common_props} '
                    f'data-pin-data-type="{pin_data_type}" '
                    f'data-pin-color="{pin_color}"'
                ):
                ui.tooltip(f'{pin.description} | {pin.data.get_value()}').classes('bg-green')

    def _add_resize_handle(self, main_card: ui.card, wrapper: NodeWrapper):
        """Add a draggable resize handle to the bottom-right corner."""
        
        # Resize handle element
        with ui.element('div').classes('resize-handle').style(
            'position: absolute; '
            'bottom: 0; '
            'right: 0; '
            'width: 16px; '
            'height: 16px; '
            'cursor: nwse-resize; '
            'background: linear-gradient(135deg, transparent 50%, rgba(128,128,128,0.3) 50%); '
            'z-index: 1000;'
        ) as handle:
            
            # Add JavaScript for drag functionality
            handle.on('mousedown', js_handler='''
                (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const card = e.target.closest('.node-card');
                    const startX = e.clientX;
                    const startWidth = parseInt(getComputedStyle(card).width);
                    
                    const onMouseMove = (e) => {
                        const newWidth = startWidth + (e.clientX - startX);
                        if (newWidth >= 256) { // min-w-64 = 256px
                            card.style.width = newWidth + 'px';
                            card.style.maxWidth = 'none';
                        }
                    };
                    
                    const onMouseUp = () => {
                        document.removeEventListener('mousemove', onMouseMove);
                        document.removeEventListener('mouseup', onMouseUp);
                    };
                    
                    document.addEventListener('mousemove', onMouseMove);
                    document.addEventListener('mouseup', onMouseUp);
                }
            ''')