"""The modal behind a port row's pen — edit what a port is called and starts at.

Opens on a ``RESOLVED`` port: one the user brought into being by wiring an
``ADD`` slot or collapsing a selection. Its id is shown but not editable —
edges key on it, and ADR 0036 settles that an interface port's label may change
while its id may not.

Applying commits every field that changed through one
``Editor.set_port_metadata`` call, so the whole edit is a single undo step.

Built on :class:`Popup` rather than ``ui.dialog()``: the panel that opens this
lives in a surface that may itself be inside a popup, and a Quasar dialog's
fixed height squishes a form with a rendered widget in it. See the
Popup/dialog direction rule in ``docs/reference/design-guide.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup
from haywire.ui.utils import anchor_cleanup_to_element
from haywire.ui.panel.port_default_widget_model import PortDefaultWidgetModel

if TYPE_CHECKING:
    from haywire.core.graph.editor import Editor
    from haywire.core.types import DataPort


def open_port_edit_dialog(
    port: "DataPort",
    node_id: str,
    editor: "Editor",
    on_applied: Callable[[], None] | None = None,
) -> Popup:
    """Open the edit modal for ``port`` and apply what the user confirms.

    Args:
        port: The port being edited. Must be ``RESOLVED``; the caller gates on
            that, and ``set_port_metadata`` refuses otherwise.
        node_id: The node carrying ``port``, for the undo entry and the write.
        editor: The graph editor whose history the edit is recorded on.
        on_applied: Called after a successful apply, for the caller to redraw.

    Returns:
        The opened :class:`Popup`.
    """
    staged: dict[str, Any] = {}

    popup = Popup(
        title=f"Edit Port — {port.label or port.id}",
        width="420px",
        closable=True,
        backdrop_click_close=False,
        escape_close=True,
    )

    with popup:
        # info_row's copy button earns its place here, where the id is the one
        # thing on the form a user may want to take elsewhere (a farmhand call,
        # an error report). In the ports panel row it does not, which is why
        # that row is built by hand.
        hui.info_row("ID", port.id)

        label_input = ui.input("Label", value=port.label).classes("w-full").props("dense outlined")
        description_input = (
            ui.textarea("Description", value=port.description)
            .classes("w-full")
            .props("dense outlined autogrow")
        )

        default_model = _render_default_field(port, staged)

        def _apply() -> None:
            changes: dict[str, Any] = {}
            if label_input.value != port.label:
                changes["label"] = label_input.value
            if description_input.value != port.description:
                changes["description"] = description_input.value
            if default_model is not None and "default" in staged:
                changes["default"] = default_model.as_default()

            popup.close()
            if not changes:
                return

            ok, reason = editor.set_port_metadata(node_id, port.id, **changes)
            if not ok:
                ui.notify(reason or "Could not edit the port", type="negative", multi_line=True)
                return
            if on_applied is not None:
                on_applied()

        with ui.row().classes("w-full justify-end gap-2 mt-3"):
            ui.button("Cancel", on_click=popup.close).props("flat dense")
            ui.button("Apply", on_click=_apply).props("flat dense").style("color: var(--hw-positive);")

    popup.open()
    return popup


def _render_default_field(
    port: "DataPort",
    staged: dict[str, Any],
) -> PortDefaultWidgetModel | None:
    """Render the default-value editor in the port's own widget, if it has one.

    Built straight from the widget class rather than through
    ``WidgetFactory.render_widget``: the factory's path is for a real
    ``DataPort`` — it reads ``promoted``/``_node`` to decide whether to route
    writes through a setting — and would re-wrap a model that is already one.
    This is the same construction the Properties panel uses for a
    ``SettingWidgetModel``, for the same reason.

    Returns the model holding the staged value, or ``None`` when the port
    declares no widget, or its widget class cannot be resolved — there is then
    no editor to offer, and the default is left alone.
    """
    from haywire.ui.widget.globals import get_widget_class

    if port.widget_key is None:
        return None
    widget_cls = get_widget_class(port.widget_key)
    if widget_cls is None:
        return None

    model = PortDefaultWidgetModel(port, on_edit=lambda value: staged.__setitem__("default", value))
    with ui.column().classes("w-full gap-0 compact-fields"):
        ui.label("Default value").classes("text-xs hw-text-dim pt-1")
        try:
            with ui.element("div").classes("w-full min-w-0") as cell:
                widget = widget_cls(model)
                widget.render()
        except Exception:
            hui.error_label("Could not render the default-value editor")
            return None

    # BaseWidget.render() anchors cleanup to client disconnect, not element
    # deletion, so a closed popup would leave the widget subscribed to a cell
    # nothing can reach. cleanup() is idempotent, so this composes with it.
    anchor_cleanup_to_element(cell, widget.cleanup)
    return model
