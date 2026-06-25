from abc import ABC
from typing import TYPE_CHECKING, List
from nicegui import ui

from haywire.core.errors import HaywireException
from haywire.core.types import DataPort
from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.pin_render import render_pin, add_pin_tooltip
from haywire.ui import elements as hui
from haywire.ui.utils import generate_pin_uuid

from ..settings.node_skin_settings import NodeSkinSettings

if TYPE_CHECKING:
    from haywire.ui.widget.factory_interface import IWidgetFactory
    from haywire.core.node.node_warning import NodeWarning


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
            add_pin_tooltip(config_row, port)

    def _render_pin(
        self, pin: DataPort, wrapper: NodeWrapper, direction: str = "left", cell_style: str = ""
    ):
        """Render a pin with connection system compatibility.

        Thin wrapper over the framework ``render_pin`` helper, supplying this
        skin's geometry settings. ``cell_style`` is forwarded to place the pin
        into a grid cell. Wires the right-click port menu and attaches a hover
        tooltip when enabled in settings.
        """
        pin_el = render_pin(
            pin,
            wrapper.node_id,
            direction=direction,
            cell_style=cell_style,
            pin_gutter=self.PIN_GUTTER,
            card_padding=self.CARD_H_PADDING,
            pin_protrusion=self.PIN_PROTRUSION,
        )
        if pin_el is not None:
            # Wire the right-click port context menu (host concern — render_pin
            # stays agnostic of which focus the menu opens).
            pin_el.props('data-hw-port-menu-focus-id="port.info"')
            if self._ui_settings.show_tooltips:
                add_pin_tooltip(pin_el, pin)

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

    def _render_diagnostics_button(
        self,
        errors: List["HaywireException"],
        warnings: List["NodeWarning"],
        node_id: str,
        deprecation_str: str = "",
    ) -> None:
        """Render a single badge unifying errors and advisory warnings.

        One icon, one floating count (errors + warnings + deprecation), colored
        by the highest severity present: red when the node has any runtime error,
        otherwise amber for advisory-only notices.

        Left-click opens one popup listing errors first (fatal), then advisory
        warnings and any deprecation notice. Right-click still falls through to
        the node context menu (via `data-node-id`), which carries the Node Errors
        panel through dual-host registration.

        Args:
            errors: Runtime errors (fatal — make the node invalid).
            warnings: Advisory NodeWarning records (non-fatal).
            node_id: Node ID used by canvas.vue to resolve the active node.
            deprecation_str: Optional deprecation notice from node identity.
        """
        has_errors = bool(errors)
        # One count covering every diagnostic surfaced in the popup.
        total = len(errors) + len(warnings) + (1 if deprecation_str else 0)

        # Highest severity drives the color: red if any fatal error, else amber.
        color = "red" if has_errors else "amber"

        btn = ui.button(icon=hui.icon.warning, color=color).props("flat dense round")
        btn.classes("text-xl px-2 py-1")
        btn.style("position: absolute; top: -25px;")
        btn.props(f'data-node-id="{node_id}"')
        with btn:
            ui.badge(str(total), color=color).props("floating")

            # ui.menu renders on Layer 2 (--hw-bg-elevated) per the design system.
            # Body copy stays quiet (body/dim tokens) — severity lives on the badge
            # icon, not the prose. Messages wrap, so override `truncate`.
            with ui.menu(), ui.column().classes("p-2 gap-1").style("max-width: 22rem"):
                if errors:
                    hui.section_label("Errors")
                    for e in errors:
                        ui.label(e.message).classes("text-sm hw-text-body whitespace-normal")
                if deprecation_str:
                    hui.section_label("Deprecated")
                    ui.label(deprecation_str).classes("text-sm hw-text-body whitespace-normal")
                if warnings:
                    hui.section_label("Compatibility warnings")
                    for w in warnings:
                        ui.label(w.message).classes("text-sm hw-text-body whitespace-normal")
                    ui.label(
                        "Tip: 'Reset Node' re-derives this node from current code "
                        "(note: this discards any dynamically-added ports)."
                    ).classes("text-xs hw-text-dim whitespace-normal")
