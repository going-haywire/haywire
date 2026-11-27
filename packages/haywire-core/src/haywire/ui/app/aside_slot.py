"""AsideSlot — the TabSlot subclass for the ASIDE slot.

A full-height column between the EDIT/INFO column and CONTEXT, with a tab bar
on top. It has no rail: closed, the whole column leaves the layout, and the
only way back in is the top-bar toggle the shell mounts via
:meth:`AsideSlot.render_toggle`. While closed, that toggle region also shows
each editor's tab interior, so a badge an editor draws in ``draw_tab`` stays
in view.
"""

from __future__ import annotations

from typing import ClassVar

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.app.tab_slot import TabSlot


class AsideSlot(TabSlot):
    """Tabbed slot for the ASIDE column, opened and closed from the top bar.

    Notes:
        ``set_visible`` hides the whole column, tab bar included. A
        :meth:`reveal` into a closed ASIDE opens it (see
        :attr:`_expands_on_reveal`). Tabs never fold the column.
    """

    _expands_on_reveal: ClassVar[bool] = True

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._column: ui.element | None = None
        self._toggle_container: ui.element | None = None

    def render(self, parent: ui.element) -> None:
        """Build the column (tab bar over area) inside ``parent``; hidden while closed."""
        with parent:
            self._column = (
                ui.column()
                .classes("gap-0 flex-shrink-0")
                .style(
                    f"width: {self._size}px; min-width: 150px; height: 100%; overflow: hidden; "
                    "background: var(--hw-bg-page); border-left: 1px solid var(--hw-border);"
                )
            )
        # The column carries the slot id: the drag-resize JS sizes it, bar and area together.
        self._column._props["id"] = f"hw-slot-{self.name}"
        super().render(self._column)
        self._column.set_visibility(self._visible)

    def _create_content_box(self) -> ui.element:
        """Create the area box under the tab bar; it fills the column."""
        return ui.column().classes("gap-0 w-full").style("flex: 1; min-height: 0; overflow: hidden;")

    def render_toggle(self, parent: ui.element) -> None:
        """Render the top-bar toggle into ``parent``, kept in sync with the slot from then on.

        The toggle is lit while ASIDE is open. While it is closed, each editor's
        vertical tab interior sits next to the toggle; clicking one opens ASIDE
        on that editor.
        """
        with parent:
            self._toggle_container = ui.row().classes("items-center gap-1 no-wrap")
        self._refresh_toggle()

    def toggle(self) -> None:
        """Open ASIDE when closed, close it when open."""
        self.set_visible(not self._visible)

    def set_visible(self, visible: bool) -> None:
        """Show or hide the whole column, tab bar included. Idempotent."""
        if self._column is not None:
            self._column.set_visibility(visible)
        super().set_visible(visible)

    def _refresh_bar(self) -> None:
        super()._refresh_bar()
        self._refresh_toggle()

    def _refresh_toggle(self) -> None:
        if self._toggle_container is None:
            return
        self._toggle_container.clear()
        with self._toggle_container:
            if not self._visible:
                for wrapper in self._accessible_bindings():
                    with (
                        ui.button(
                            on_click=lambda _e, bid=wrapper.editor_binding_id: self._on_bar_item_clicked(bid)
                        )
                        .props("flat dense no-caps")
                        .classes("hw-shell-toolbar-btn")
                    ):
                        wrapper.render_tab_into(orientation="vertical")
            hui.toolbar_button(
                hui.icon.aside,
                is_active=self._visible,
                tooltip="Close the aside" if self._visible else "Open the aside",
                on_click=self.toggle,
            )
