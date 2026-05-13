"""
TabSlot — the Slot subclass for main / bottom slots.

Renders a column containing a horizontal tab bar on top (``ui.tabs``, plus an
optional chevron for the bottom slot that folds the area in/out) and the
``ui.tab_panels`` area below. Wrapper mutation is inherited from :class:`Slot`
(``reveal`` / ``close_binding`` / ``repayload`` / ``close_tabs_for``); the bar
re-renders on each mutation via ``_refresh_bar``.

"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Literal, cast

from nicegui import ui

from haywire.ui.app.slot import Slot
from haywire.ui.editor.wrapper import EditorWrapper

logger = logging.getLogger(__name__)


class TabSlot(Slot):
    """Tabbed slot for the main and bottom shell slots.

    The optional ``show_fold_toggle`` flag renders the chevron expand/retract
    button at the end of the bar — used by the bottom slot.
    """

    _ORIENTATION: ClassVar[Literal["horizontal", "vertical"]] = "vertical"

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, parent: ui.element) -> None:
        """Build ``[bar / area]`` or ``[area / bar]`` column inside ``parent``."""
        wrapper_flex = "flex: 1" if not self._show_fold_toggle else "flex: 0 0 auto"
        with parent:
            wrapper = (
                ui.column()
                .classes("gap-0")
                .style(f"width: 100%; {wrapper_flex}; min-height: 0; overflow: hidden;")
            )

        if self._bar_place == "top":
            with wrapper:
                self._render_bar_row()
                self._area_parent_box = self._create_content_box()
        else:
            with wrapper:
                self._area_parent_box = self._create_content_box()
                self._render_bar_row()

        self._render_area_contents(self._area_parent_box)
        self._area_parent_box.set_visibility(self._visible)

    def _render_bar_contents(self) -> None:
        """Render tab row + optional chevron."""
        if self._bindings:
            active_id = self._active.editor_binding_id if self._active is not None else None
            ids = [b.editor_binding_id for b in self._bindings]
            initial = active_id if active_id in ids else (ids[0] if ids else None)
            with (
                ui.tabs(value=cast(Any, initial), on_change=lambda e: self._on_tab_clicked(e.value))
                .props("dense align=left")
                .classes("hw-slot-bar-tabs")
                .style("flex: 1; min-height: 36px;")
            ):
                for wrapper in self._bindings:
                    tab_el = ui.tab(name=wrapper.editor_binding_id, label="").props("no-caps")
                    with tab_el:
                        with ui.row().classes("items-center gap-1 no-wrap"):
                            if wrapper.label:
                                label = wrapper.label
                            elif wrapper.editor_cls is not None:
                                label = getattr(
                                    wrapper.editor_cls.class_identity, "label", wrapper.editor_key
                                )
                            else:
                                label = wrapper.editor_key
                            if wrapper.state is not None and wrapper.state.is_dirty:
                                label = f"• {label}"
                            ui.label(label)
                            if wrapper.can_close:
                                tab_id = wrapper.editor_binding_id
                                (
                                    ui.button(
                                        icon="close",
                                        on_click=lambda _e, tid=tab_id: self._on_tab_close_clicked(tid),
                                    )
                                    .props("flat round dense size=xs")
                                    .classes("hw-tab-close -mr-1")
                                    .on("click.stop", lambda _e: None)
                                )

        if self._show_fold_toggle:
            chevron_icon = "expand_less" if self._visible else "expand_more"
            self._fold_button = (
                ui.button(icon=chevron_icon, on_click=self._on_fold_toggle_clicked)
                .props("flat round dense size=sm")
                .tooltip(f"Toggle {self.name} slot")
                .classes("flex-shrink-0 mr-1")
            )

    # ------------------------------------------------------------------
    # User actions
    # ------------------------------------------------------------------

    def _on_tab_clicked(self, tab_id: str) -> None:
        """Switch to the clicked tab.

        ``slot.switch_to`` already calls ``editor.on_focus`` via
        ``Slot._activate`` (slot.py:499-505), so no separate context
        notification is needed — focus-followers run on the on_focus path.
        """
        editor_key, binding_id = EditorWrapper.split_id(tab_id)
        if not self.switch_to(editor_key, binding_id):
            return
        self._refresh_bar()

    async def _on_tab_close_clicked(self, tab_id: str) -> None:
        """Ask the editor whether to close, then close if allowed.

        The wrapper awaits ``handle_close_request`` on the editor instance
        (which can show a save-or-discard dialog) and only invokes
        ``slot.close_binding`` if the editor allows the close.
        """
        editor_key, binding_id = EditorWrapper.split_id(tab_id)
        wrapper = self.find_binding(editor_key, binding_id)
        if wrapper is None:
            return
        await wrapper.close()

    def _on_fold_toggle_clicked(self) -> None:
        self.set_visible(not self._visible)
