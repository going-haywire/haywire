from abc import ABC
from typing import TYPE_CHECKING, List
from nicegui import ui

from haywire.core.types import DataPort, CompoundType, FlowType
from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.widget.factory import error_render_detail
from haywire.ui.skin.base import BaseSkin
from haywire.ui.themes.icons import ICONS
from haywire.ui.utils import generate_pin_uuid

if TYPE_CHECKING:
    from haywire.core.errors import HaywireException


class NodeSkin(BaseSkin, ABC):
    """
    Base class for all NiceGui NodeSkin classes.

    NodeSkin classes are stateless and define the look and structure of nodes.
    They are cached and reused by the SkinFactory.

    Layout constants (override in subclasses to tune spacing):
        CARD_H_PADDING  — explicit horizontal padding applied to the card (px).
                          This value is consumed by default_skin's render() and is also
                          baked into the pin offset formula so that PIN_PROTRUSION = 0
                          always means "pin center exactly at the card's visible border".
        PIN_GUTTER      — width of the pin column (px). Also sets the icon size.
        PIN_PROTRUSION  — how far the pin center sits outside the card's visible edge (px).
                          0 = flush with card border; positive = further out;
                          negative = pin pulled inward.
        CONTENT_GAP     — offset between the gutter column edge and the label/widget (px).
                          Positive = gap, zero = flush with column edge, negative = label
                          overlaps into the gutter (useful since the pin only occupies the
                          outer half of the gutter, leaving PIN_GUTTER/2 px of empty space
                          before the label even at zero).
        PIN_ROW_HEIGHT  — height of the pin cell, sets vertical centering target (px)
    """

    CARD_H_PADDING: int = 16
    PIN_GUTTER: int = 20
    PIN_PROTRUSION: int = 0
    CONTENT_GAP: int = -15
    PIN_ROW_HEIGHT: int = 24

    def render_port(self, port: DataPort, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render a port according to its ort type"""
        if port.is_inlet():
            self._render_inlet(port, wrapper, widget_classes="widget-container zoom-pan-lod2")
        elif port.is_outlet():
            self._render_outlet(port, wrapper, widget_classes="widget-container zoom-pan-lod2")
        elif port.is_config():
            self._render_config(port, wrapper, widget_classes="widget-container zoom-pan-lod2")

    def _render_inlet(self, port: DataPort, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render an inlet port as a two-column grid: fixed PIN_GUTTER pin column | flex content."""
        g, gap, h = self.PIN_GUTTER, self.CONTENT_GAP, self.PIN_ROW_HEIGHT
        with ui.element("div").style(
            f"display: grid; grid-template-columns: {g}px 1fr; width: 100%; align-items: start;"
        ):
            # Pin gutter — fixed-width column, overflow visible so pin straddles card edge
            with ui.element("div").style(
                f"width: {g}px; height: {h}px; display: flex; align-items: center; "
                "justify-content: center; overflow: visible; flex-shrink: 0;"
            ):
                self._render_pin(port, wrapper, direction="left")

            # Content column — label and optional widget stacked vertically
            # margin (not padding) so negative CONTENT_GAP can pull label toward the pin
            with (
                ui.element("div")
                .classes("compact-fields")
                .style(
                    f"display: flex; flex-direction: column; "
                    f"margin-left: {gap}px; margin-right: {g}px; min-width: 0;"
                )
            ):
                ui.label(port.label).classes("text-xs zoom-pan-lod2")
                if not port.allow_multiple_links and port.widget_key:
                    self.render_widget(port, wrapper.node_id, classes=widget_classes)

    def _render_outlet(self, port, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render an outlet port as a two-column grid: flex content | fixed PIN_GUTTER pin column."""
        g, gap, h = self.PIN_GUTTER, self.CONTENT_GAP, self.PIN_ROW_HEIGHT
        with ui.element("div").style(
            f"display: grid; grid-template-columns: 1fr {g}px; width: 100%; align-items: start;"
        ):
            # Content column — label right-aligned and optional widget
            # margin (not padding) so negative CONTENT_GAP can pull label toward the pin
            with (
                ui.element("div")
                .classes("compact-fields")
                .style(
                    f"display: flex; flex-direction: column; align-items: flex-end; "
                    f"margin-right: {gap}px; min-width: 0;"
                )
            ):
                ui.label(port.label).classes("text-xs")
                if not port.allow_multiple_links and port.widget_key:
                    self.render_widget(port, wrapper.node_id, classes=widget_classes)

            # Pin gutter — fixed-width column on the right
            with ui.element("div").style(
                f"width: {g}px; height: {h}px; display: flex; align-items: center; "
                "justify-content: center; overflow: visible; flex-shrink: 0;"
            ):
                self._render_pin(port, wrapper, direction="right")

    def _render_config(self, port, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render a config port — no pin, indented symmetrically to align with inlet/outlet labels."""
        indent = max(0, self.PIN_GUTTER + self.CONTENT_GAP)
        with (
            ui.element("div")
            .classes("compact-fields")
            .style(
                f"display: flex; flex-direction: column; width: 100%; "
                f"padding-left: {indent}px; padding-right: {indent}px;"
            )
        ):
            ui.label(port.label).classes("text-xs")
            if not port.allow_multiple_links and port.widget_key:
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

        pin_size = f"{self.PIN_GUTTER}px"
        # offset = card padding + half gutter (pin's natural inset) + desired protrusion
        offset_px = self.CARD_H_PADDING + self.PIN_GUTTER // 2 + self.PIN_PROTRUSION
        pin_offset = f"position: relative; {direction}: -{offset_px}px; cursor: crosshair;"

        if pin.flow_type == FlowType.CONTROL:
            ctrl_color = pin.color
            if pin.is_inlet():
                ctrl_icon = pin.icon_in or ICONS.JOIN_LEFT
            else:
                ctrl_icon = pin.icon_out or ICONS.JOIN_RIGHT
            with (
                ui.icon(ctrl_icon, color=ctrl_color, size=pin_size)
                .classes("port input-port connection-pin zoom-pan-lod0")
                .style(pin_offset)
                .props(f'{common_props} data-pin-color="{ctrl_color}"')
            ):
                with ui.tooltip().classes(ctrl_color):
                    self._tooltip_for_port(pin)

        elif pin.flow_type == FlowType.CALLBACK:
            callback_color = pin.color
            if pin.is_inlet():
                callback_icon = pin.icon_in or ICONS.SWIPE_LEFT_ALT
            else:
                callback_icon = pin.icon_out or ICONS.SWIPE_RIGHT_ALT
            with (
                ui.icon(callback_icon, color=callback_color, size=pin_size)
                .classes("port input-port connection-pin zoom-pan-lod0")
                .style(pin_offset)
                .props(f'{common_props} data-pin-color="{callback_color}"')
            ):
                with ui.tooltip().classes(callback_color):
                    self._tooltip_for_port(pin)

        elif pin.flow_type == FlowType.DATA:
            pin_color = pin.color
            pin_data_type = pin._data.get_stored_type().class_identity.registry_key
            if pin.is_inlet():
                if pin.allow_multiple_links:
                    if issubclass(pin._data.get_stored_type(), CompoundType):
                        data_icon = (
                            pin._data.get_stored_type().class_identity.icon_in_multi or ICONS.WEB_STORIES
                        )
                    else:
                        data_icon = (
                            pin._data.get_stored_type().class_identity.icon_in_multi
                            or ICONS.FIBER_SMART_RECORD
                        )
                else:
                    if issubclass(pin.type_cls, CompoundType):
                        data_icon = pin._data.get_stored_type().class_identity.icon_in or ICONS.VIEW_DAY
                    else:
                        data_icon = pin._data.get_stored_type().class_identity.icon_in or ICONS.MY_LOCATION
            else:
                if issubclass(pin.type_cls, CompoundType):
                    data_icon = pin._data.get_stored_type().class_identity.icon_out_multi or ICONS.VIEW_DAY
                else:
                    data_icon = pin._data.get_stored_type().class_identity.icon_out_multi or ICONS.CIRCLE
            with (
                ui.icon(data_icon, color=pin_color, size=pin_size)
                .classes("port connection-pin zoom-pan-lod0")
                .style(pin_offset)
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
        inlet_uuid = generate_pin_uuid(node_id, "root_in")
        (
            ui.element("div")
            .classes("connection-pin zoom-pan-lod0")
            .style(
                "width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; "
                "background: rgba(128,128,128,0.15); border: 1px dashed rgba(128,128,128,0.4); "
                "cursor: default; left: -16px;"
            )
            .props(
                f'id="{inlet_uuid}" data-node-id="{node_id}" data-pin-id="root_in" '
                f'data-pin-flow-type="ghost" data-pin-dir="inlet" '
                f'data-pin-dir-x="-1" data-pin-dir-y="0" data-pin-color="#888888"'
            )
        )

        # Outlet ghost pin — right side (order: 999 pushes it after all other flex items)
        outlet_uuid = generate_pin_uuid(node_id, "root_out")
        (
            ui.element("div")
            .classes("connection-pin zoom-pan-lod0")
            .style(
                "order: 999; width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; "
                "background: rgba(128,128,128,0.15); border: 1px dashed rgba(128,128,128,0.4); "
                "cursor: default; right: -16px;"
            )
            .props(
                f'id="{outlet_uuid}" data-node-id="{node_id}" data-pin-id="root_out" '
                f'data-pin-flow-type="ghost" data-pin-dir="outlet" '
                f'data-pin-dir-x="1" data-pin-dir-y="0" data-pin-color="#888888"'
            )
        )

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
