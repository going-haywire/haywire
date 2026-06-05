from abc import ABC
from typing import TYPE_CHECKING, List
from nicegui import ui

from haywire.core.errors import HaywireException
from haywire.core.types import DataPort, CompoundType, FlowType
from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.skin.base import BaseSkin
from haywire.ui import elements as hui
from haywire.ui.themes.icons import ICONS
from haywire.ui.utils import generate_pin_uuid

from ..settings.node_skin_settings import NodeSkinSettings

if TYPE_CHECKING:
    from haywire.ui.widget.factory_interface import IWidgetFactory


class NodeSkin(BaseSkin, ABC):
    """
    Base class for all NiceGui NodeSkin classes.

    NodeSkin instances are cached and reused by the SkinFactory. They hold a
    NodeUISettings instance for live access to layout and visibility settings,
    but carry no per-node render state.

    Layout values are driven by NodeUISettings and read on every render call:
        card_padding    — horizontal padding applied to the card (px).
        pin_gutter      — width of the pin column (px). Also sets the icon size.
        pin_protrusion  — how far the pin center sits outside the card's visible edge (px).
                          0 = flush with card border; positive = further out;
                          negative = pin pulled inward.
        content_gap     — offset between the gutter column edge and the label/widget (px).
        pin_row_height  — height of the pin cell, sets vertical centering target (px)
    """

    def __init__(self, widget_factory: "IWidgetFactory"):
        super().__init__(widget_factory)
        self._ui_settings = NodeSkinSettings()

    @property
    def CARD_H_PADDING(self) -> int:  # noqa: N802
        return self._ui_settings.card_padding

    @property
    def PIN_GUTTER(self) -> int:  # noqa: N802
        return self._ui_settings.pin_gutter

    @property
    def PIN_PROTRUSION(self) -> int:  # noqa: N802
        return self._ui_settings.pin_protrusion

    @property
    def CONTENT_GAP(self) -> int:  # noqa: N802
        return self._ui_settings.content_gap

    @property
    def PIN_ROW_HEIGHT(self) -> int:  # noqa: N802
        return self._ui_settings.pin_row_height

    def render_port(self, port: DataPort, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render a port according to its ort type"""
        if port.is_inlet():
            self._render_left(port, wrapper, widget_classes="widget-container zoom-pan-lod2")
        elif port.is_outlet():
            self._render_right(port, wrapper, widget_classes="widget-container zoom-pan-lod2")
        elif port.is_config():
            self._render_config(port, wrapper, widget_classes="widget-container zoom-pan-lod2")

    def _render_left(self, port: DataPort, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render a port with its pin on the LEFT: pin column | flex content column.

        The pin sits in column 1, centered by the cell; the content column
        stacks the label and optional widget. ``overflow: visible`` lets the pin
        straddle the card edge. Used for inlets.
        """
        g, gap, h = self.PIN_GUTTER, self.CONTENT_GAP, self.PIN_ROW_HEIGHT
        with ui.element("div").style(
            f"display: grid; grid-template-columns: {g}px 1fr; width: 100%; align-items: start; "
            "overflow: visible;"
        ):
            # Pin in grid column 1, centered in the PIN_GUTTER-wide cell.
            self._render_pin(
                port,
                wrapper,
                direction="left",
                cell_style=f"grid-column: 1; justify-self: center; align-self: center; min-height: {h}px;",
            )

            # Content column — label and optional widget stacked vertically.
            # `gap` toward the pin (left), `g` on the far side (right) so the
            # content inset matches regardless of pin side. `align-self: center`
            # matches the pin so the label/widget share the pin's vertical center.
            with (
                ui.element("div")
                .classes("compact-fields")
                .style(
                    f"grid-column: 2; align-self: center; display: flex; flex-direction: column; "
                    f"margin-left: {gap}px; margin-right: {g}px; min-width: 0;"
                )
            ):
                if self._ui_settings.show_labels:
                    ui.label(port.label).classes("text-xs zoom-pan-lod2")
                if port.widget_key is not None and port.should_show_widget():
                    self.render_widget(port, wrapper.node_id, classes=widget_classes)

    def _render_right(self, port, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render a port with its pin on the RIGHT: flex content column | pin column.

        Mirror of :meth:`_render_left` with the pin in column 2. Used for outlets.
        """
        g, gap, h = self.PIN_GUTTER, self.CONTENT_GAP, self.PIN_ROW_HEIGHT
        with ui.element("div").style(
            f"display: grid; grid-template-columns: 1fr {g}px; width: 100%; align-items: start; "
            "overflow: visible;"
        ):
            # Content column — label right-aligned and optional widget.
            # Margins mirror the inlet: `gap` toward the pin (right), `g` on the
            # far side (left) so the content inset matches regardless of pin side.
            # `align-self: center` matches the pin's vertical center.
            with (
                ui.element("div")
                .classes("compact-fields")
                .style(
                    f"grid-column: 1; align-self: center; display: flex; flex-direction: column; "
                    f"align-items: flex-end; margin-left: {g}px; margin-right: {gap}px; min-width: 0;"
                )
            ):
                if self._ui_settings.show_labels:
                    ui.label(port.label).classes("text-xs zoom-pan-lod2")
                if port.widget_key is not None and port.should_show_widget():
                    self.render_widget(port, wrapper.node_id, classes=widget_classes)

            # Pin in grid column 2, centered in the PIN_GUTTER-wide cell.
            self._render_pin(
                port,
                wrapper,
                direction="right",
                cell_style=f"grid-column: 2; justify-self: center; align-self: center; min-height: {h}px;",
            )

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
        ) as config_row:
            if self._ui_settings.show_labels:
                ui.label(port.label).classes("text-xs zoom-pan-lod2")
            if port.widget_key is not None and port.should_show_widget():
                self.render_widget(port, wrapper.node_id, classes=widget_classes)

        # Config ports render no pin, so they cannot carry a pin tooltip.
        # Attach the same label/description tooltip to the whole config row.
        if self._ui_settings.show_tooltips:
            self._add_pin_tooltip(config_row, port)

    def _render_pin(
        self, pin: DataPort, wrapper: NodeWrapper, direction: str = "left", cell_style: str = ""
    ):
        """Render a pin with connection system compatibility.

        ``cell_style`` is appended to the pin element's own style, letting the
        caller place the pin directly into a grid cell (grid-column / *-self
        centering).
        """
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
            f'data-pin-flow-type="{pin.flow_type.value}" '
            f'data-pin-dir="{pin_direction}" '
            f'data-pin-dir-x="{dir_x}" '
            f'data-pin-dir-y="{dir_y}"'
        )

        pin_size = f"{self.PIN_GUTTER}px"
        # offset = card padding + half gutter (pin's natural inset) + desired protrusion
        offset_px = self.CARD_H_PADDING + self.PIN_GUTTER // 2 + self.PIN_PROTRUSION
        pin_offset = f"position: relative; {direction}: -{offset_px}px; cursor: crosshair; {cell_style}"

        port_menu_props = 'data-hw-port-menu-focus-id="port.info"'

        pin_el: ui.element | None = None
        if pin.flow_type == FlowType.CONTROL:
            ctrl_color = pin.color
            if pin.is_inlet():
                ctrl_icon = pin.icon_in or ICONS.JOIN_LEFT
            else:
                ctrl_icon = pin.icon_out or ICONS.JOIN_RIGHT
            pin_el = (
                ui.icon(ctrl_icon, color=ctrl_color, size=pin_size)
                .classes("port input-port connection-pin zoom-pan-lod0")
                .style(pin_offset)
                .props(f'{common_props} data-pin-color="{ctrl_color}" {port_menu_props}')
            )

        elif pin.flow_type == FlowType.CALLBACK:
            callback_color = pin.color
            if pin.is_inlet():
                callback_icon = pin.icon_in or ICONS.SWIPE_LEFT_ALT
            else:
                callback_icon = pin.icon_out or ICONS.SWIPE_RIGHT_ALT
            pin_el = (
                ui.icon(callback_icon, color=callback_color, size=pin_size)
                .classes("port input-port connection-pin zoom-pan-lod0")
                .style(pin_offset)
                .props(f'{common_props} data-pin-color="{callback_color}" {port_menu_props}')
            )

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
                    if pin.type_cls and issubclass(pin.type_cls, CompoundType):
                        data_icon = pin._data.get_stored_type().class_identity.icon_in or ICONS.VIEW_DAY
                    else:
                        data_icon = pin._data.get_stored_type().class_identity.icon_in or ICONS.MY_LOCATION
            else:
                if pin.type_cls and issubclass(pin.type_cls, CompoundType):
                    data_icon = pin._data.get_stored_type().class_identity.icon_out_multi or ICONS.VIEW_DAY
                else:
                    data_icon = pin._data.get_stored_type().class_identity.icon_out_multi or ICONS.CIRCLE
            pin_el = (
                ui.icon(data_icon, color=pin_color, size=pin_size)
                .classes("port connection-pin zoom-pan-lod0")
                .style(pin_offset)
                .props(
                    f'{common_props} data-pin-data-type="{pin_data_type}" '
                    f'data-pin-color="{pin_color}" {port_menu_props}'
                )
            )

        if pin_el is not None and self._ui_settings.show_tooltips:
            self._add_pin_tooltip(pin_el, pin)

    def _add_pin_tooltip(self, pin_el: ui.element, pin: DataPort) -> None:
        """Attach a hover tooltip showing a port's label and description.

        Anchored to the pin element for inlets/outlets, or the config row for
        config ports (which have no pin). The description line is omitted when
        the port has no description.
        """
        with pin_el, ui.tooltip().classes("text-xs"):
            ui.label(pin.label).classes("font-bold")
            description = (pin.description or "").strip()
            if description:
                ui.label(description)

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
                "background: linear-gradient(135deg, transparent 50%, var(--hw-ghost-pin) 50%); "
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
                "background: var(--hw-ghost-pin); border: 1px dashed var(--hw-ghost-pin); "
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
                "background: var(--hw-ghost-pin); border: 1px dashed var(--hw-ghost-pin); "
                "cursor: default; right: -16px;"
            )
            .props(
                f'id="{outlet_uuid}" data-node-id="{node_id}" data-pin-id="root_out" '
                f'data-pin-flow-type="ghost" data-pin-dir="outlet" '
                f'data-pin-dir-x="1" data-pin-dir-y="0" data-pin-color="#888888"'
            )
        )

    def _render_errors_button(self, errors: List["HaywireException"], node_id: str):
        """Render a badge that signals runtime errors on the node.

        Right-click on the badge falls through to the regular node context
        menu (which contains the Node Errors panel via the dual-host
        registration). The badge no longer stamps a custom menu attribute.

        Args:
            errors: List of runtime errors to display
            node_id: Node ID used by canvas.vue to resolve the active node
        """
        error_count = len(errors)

        btn = ui.button(icon=hui.icon.warning, color="red")
        btn.classes("text-xl px-2 py-1")
        btn.props("dense flat")
        btn.style("position: absolute; top: -25px;")
        btn.props(f'data-node-id="{node_id}"')
        with btn:
            ui.badge(str(error_count), color="red").props("floating")
