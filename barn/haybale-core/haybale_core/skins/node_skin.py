from abc import ABC
from typing import TYPE_CHECKING, List
from nicegui import ui

from haywire.core.types import DataPort, CompoundType, FlowType
from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.widget.factory import error_render_detail
from haywire.ui.skin.base import BaseSkin
from haywire.ui.themes.icons import ICONS
from haywire.ui.themes.keys import ThemeKey
from haywire.ui.utils import generate_pin_uuid
from haywire.ui.themes import ThemePalette

if TYPE_CHECKING:
    from haywire.core.errors import HaywireException


class NodeSkin(BaseSkin, ABC):
    """
    Base class for all NiceGui NodeSkin classes.

    NodeSkin classes are stateless and define the look and structure of nodes.
    They are cached and reused by the SkinFactory.
    """

    def render_port(self, port: DataPort, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render a port according to its ort type"""
        if port.is_inlet():
            self._render_inlet(port, wrapper, widget_classes='widget-container zoom-pan-lod2')
        elif port.is_outlet():
            self._render_outlet(port, wrapper, widget_classes='widget-container zoom-pan-lod2')
        elif port.is_config():
            self._render_config(port, wrapper, widget_classes='widget-container zoom-pan-lod2')

    def _render_inlet(self, port: DataPort, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render an inlet with its pin and widget."""
        with ui.row().classes("w-full items-center justify-start gap-0"):
            # only render pins for inlets that are actually involved in flows
            self._render_pin(port, wrapper, direction="left")

            # Pin label
            ui.label(port.label).classes("text-xs zoom-pan-lod2")

        # Render inlet widget if it has a pin that does not allow multiple connections
        if not port.allow_multiple_links:
            if port.widget_key:
                # Widget rendering adds UI element to current context automatically
                self.render_widget(port, wrapper.node_id, classes=widget_classes)

    def _render_outlet(self, port, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render an outlet with its pin and widget."""
        with ui.row().classes("w-full items-center justify-end gap-0"):
            # Pin label
            ui.label(port.label).classes("text-xs")

            # only render pins for outlets that are actually involved in flows
            self._render_pin(port, wrapper, direction="right")

        # Render outlet widget if it has a pin that does not allow multiple links
        if not port.allow_multiple_links:
            if port.widget_key:
                # Widget rendering adds UI element to current context automatically
                self.render_widget(port, wrapper.node_id, classes=widget_classes)

    def _render_config(self, port, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render an config with its widget."""
        with ui.row().classes("w-full items-center justify-start gap-0"):
            # Pin label
            ui.label(port.label).classes("text-xs")

        # Render config widget if it has a pin that does not allow multiple links
        if not port.allow_multiple_links:
            if port.widget_key:
                # Widget rendering adds UI element to current context automatically
                self.render_widget(port, wrapper.node_id, classes=widget_classes)

    def _render_pin(self, pin: DataPort, wrapper: NodeWrapper, direction: str = "left"):
        """Render a pin with connection system compatibility."""
        # Create unique pin ID and determine port type for connection system
        pin_direction = "inlet" if pin.is_inlet() else "outlet"
        pin_uuid = generate_pin_uuid(wrapper.node_id, pin.id)

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
                ctrl_icon = ThemePalette.get(ThemeKey.UI_PORT_ICON_IN_CTRL, pin.icon_in, ICONS.JOIN_LEFT)
            else:
                ctrl_icon = ThemePalette.get(ThemeKey.UI_PORT_ICON_OUT_CTRL, pin.icon_out, ICONS.JOIN_RIGHT)
            with (
                ui.icon(ctrl_icon, color=ctrl_color, size="xs")
                .classes("text-4xl port input-port connection-pin zoom-pan-lod0")
                .style(f"position: absolute; {direction}: -20px; cursor: crosshair;")
                .props(f'{common_props} data-pin-color="{ctrl_color}"')
            ):
                with ui.tooltip().classes(ctrl_color):
                    self._tooltip_for_port(pin)

        elif pin.flow_type == FlowType.CALLBACK:
            # Get callback flow color from theme
            callback_color = pin.color
            if pin.is_inlet():
                callback_icon = ThemePalette.get(
                    ThemeKey.UI_PORT_ICON_IN_CALLBACK, pin.icon_in, ICONS.SWIPE_LEFT_ALT
                )
            else:
                callback_icon = ThemePalette.get(
                    ThemeKey.UI_PORT_ICON_OUT_CALLBACK, pin.icon_out, ICONS.SWIPE_RIGHT_ALT
                )
            # Pin connector
            with (
                ui.icon(callback_icon, color=callback_color, size="20px")
                .classes("text-4xl port input-port connection-pin zoom-pan-lod0")
                .style(f"position: absolute; {direction}: -20px; cursor: crosshair;")
                .props(f'{common_props} data-pin-color="{callback_color}"')
            ):
                with ui.tooltip().classes(callback_color):
                    self._tooltip_for_port(pin)

        elif pin.flow_type == FlowType.DATA:
            pin_color = pin.color
            pin_data_type = pin._data.get_stored_type().class_identity.registry_key
            # Get pin color: try data type specific, use pin.color as preference
            if pin.is_inlet():
                if pin.allow_multiple_links:
                    if issubclass(pin._data.get_stored_type(), CompoundType):
                        data_icon = ThemePalette.get(
                            ThemeKey.UI_PORT_ICON_IN_MULTI_COMPOUND,
                            pin._data.get_stored_type().class_identity.icon_in_multi,
                            fallback=ICONS.WEB_STORIES,
                        )
                    else:
                        data_icon = ThemePalette.get(
                            ThemeKey.UI_PORT_ICON_IN_MULTI_SINGLE,
                            pin._data.get_stored_type().class_identity.icon_in_multi,
                            fallback=ICONS.FIBER_SMART_RECORD,
                        )
                else:
                    if issubclass(pin.type_cls, CompoundType):
                        data_icon = ThemePalette.get(
                            ThemeKey.UI_PORT_ICON_IN_COMPOUND,
                            pin._data.get_stored_type().class_identity.icon_in,
                            fallback=ICONS.VIEW_DAY,
                        )
                    else:
                        data_icon = ThemePalette.get(
                            ThemeKey.UI_PORT_ICON_IN_SINGLE,
                            pin._data.get_stored_type().class_identity.icon_in,
                            fallback=ICONS.MY_LOCATION,
                        )
            else:
                if issubclass(pin.type_cls, CompoundType):
                    data_icon = ThemePalette.get(
                        ThemeKey.UI_PORT_ICON_OUT_MULTI_COMPOUND,
                        pin._data.get_stored_type().class_identity.icon_out_multi,
                        fallback=ICONS.VIEW_DAY,
                    )
                else:
                    data_icon = ThemePalette.get(
                        ThemeKey.UI_PORT_ICON_OUT_MULTI_SINGLE,
                        pin._data.get_stored_type().class_identity.icon_out_multi,
                        fallback=ICONS.CIRCLE,
                    )
            with (
                ui.icon(data_icon, color=pin_color, size="15px")
                .classes("text-4xl port connection-pin zoom-pan-lod0")
                .style(f"position: absolute; {direction}: -20px; cursor: crosshair;")
                .props(f'{common_props} data-pin-data-type="{pin_data_type}" data-pin-color="{pin_color}"')
            ):
                with ui.tooltip().classes(pin_color):
                    self._tooltip_for_port(pin)

    def _tooltip_for_port(self, port: DataPort):
        ui.label(f"Desc: {port.description}")
        ui.label(f"Flow: {port.flow_type.value}")
        ui.label(f"Type: {port._data.get_stored_type().class_identity.registry_key}")

    def _add_resize_handle(self, main_card: ui.card, wrapper: NodeWrapper):
        """Add a draggable resize handle to the bottom-right corner."""

        # Resize handle element
        with (
            ui.element("div")
            .classes("resize-handle")
            .style(
                "position: absolute; "
                "bottom: 0; "
                "right: 0; "
                "width: 16px; "
                "height: 16px; "
                "cursor: nwse-resize; "
                "background: linear-gradient(135deg, transparent 50%, rgba(128,128,128,0.3) 50%); "
                "z-index: 1000;"
            ) as handle
        ):
            # Add JavaScript for drag functionality
            handle.on(
                "mousedown",
                js_handler="""
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
            """,
            )

    def _render_root_ghost_pins(self, wrapper: NodeWrapper):
        """
        Render inline ghost pins into the current flex-row context (the header row).

        Both are regular flex items — no absolute positioning.
        The inlet appears first (order 0, left side of the row).
        The outlet uses `order: 999` so flexbox places it last (right side),
        after the node title and any conditional hidden-port pins.

        Using inline flex items means getBoundingClientRect() always returns
        correct screen coordinates for the JavaScript edge-drawing code,
        regardless of which element acts as the CSS positioning context.
        """
        node_id = wrapper.node_id

        # Inlet ghost pin — left side (natural order in flex row)
        inlet_uuid = generate_pin_uuid(node_id, 'root_in')
        (ui.element('div')
            .classes('connection-pin zoom-pan-lod0')
            .style(
                'width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; '
                'background: rgba(128,128,128,0.15); border: 1px dashed rgba(128,128,128,0.4); '
                'cursor: default; left: -16px;'
            )
            .props(
                f'id="{inlet_uuid}" data-node-id="{node_id}" data-pin-id="root_in" '
                f'data-pin-flow-type="ghost" data-pin-dir="inlet" '
                f'data-pin-dir-x="-1" data-pin-dir-y="0" data-pin-color="#888888"'
            ))

        # Outlet ghost pin — right side (order: 999 pushes it after all other flex items)
        outlet_uuid = generate_pin_uuid(node_id, 'root_out')
        (ui.element('div')
            .classes('connection-pin zoom-pan-lod0')
            .style(
                'order: 999; width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; '
                'background: rgba(128,128,128,0.15); border: 1px dashed rgba(128,128,128,0.4); '
                'cursor: default; right: -16px;'
            )
            .props(
                f'id="{outlet_uuid}" data-node-id="{node_id}" data-pin-id="root_out" '
                f'data-pin-flow-type="ghost" data-pin-dir="outlet" '
                f'data-pin-dir-x="1" data-pin-dir-y="0" data-pin-color="#888888"'
            ))

    def _render_errors_button(self, errors: List["HaywireException"]):
        """
        Render a button that shows runtime errors count and opens a popup with details.

        Args:
            errors: List of runtime errors to display
        """
        error_count = len(errors)

        with ui.button(icon="warning", color="red") as btn:
            btn.classes("text-xl px-2 py-1")
            btn.props("dense flat")
            btn.style("position: absolute; top: -25px;")
            ui.badge(str(error_count), color="red").props("floating")

            with ui.menu().props('anchor="bottom left" self="top left"'):
                with ui.card().classes("p-2 max-w-md max-h-96 overflow-auto"):
                    for idx, error in enumerate(errors):
                        with ui.expansion(f"{idx + 1}. {error.operation or 'Error'}", icon="error").classes(
                            "w-full text-red-600"
                        ):
                            ui.label(error.message).classes("text-sm text-red-600 mb-2")
                            error_render_detail(error)
