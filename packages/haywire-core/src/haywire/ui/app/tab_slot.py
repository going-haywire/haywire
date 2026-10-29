"""
TabSlot — the Slot subclass for the EDIT / INFO slots.

Renders a column containing a horizontal tab bar on top (``ui.tabs``) and the
``ui.tab_panels`` area below. In the foldable INFO slot, re-clicking the
active tab folds the area and any tab click unfolds it. Wrapper mutation is inherited from :class:`Slot`
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
    """Tabbed slot for the EDIT and INFO shell slots.

    The optional ``foldable`` flag (used by the INFO slot) makes the tabs fold
    and unfold the area, see :meth:`Slot._on_bar_item_clicked`.
    """

    _ORIENTATION: ClassVar[Literal["horizontal", "vertical"]] = "vertical"

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, parent: ui.element) -> None:
        """Build ``[bar / area]`` or ``[area / bar]`` column inside ``parent``."""
        wrapper_flex = "flex: 1" if not self._foldable else "flex: 0 0 auto"
        with parent:
            wrapper = (
                ui.column()
                .classes("gap-0")
                .style(f"width: 100%; {wrapper_flex}; min-height: 0; overflow: hidden;")
                .props(f'data-hw-slot="{self.name.value}"')
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
        """Render the tab row."""
        bindings = self._accessible_bindings()
        if bindings:
            active_id = self._active.editor_binding_id if self._active is not None else None
            ids = [b.editor_binding_id for b in bindings]
            initial = active_id if active_id in ids else (ids[0] if ids else None)
            # A foldable slot is driven by the per-tab click alone (see _on_bar_item_clicked).
            on_change = None if self._foldable else (lambda e: self._on_tab_clicked(e.value))
            with (
                ui.tabs(value=cast(Any, initial), on_change=on_change)
                .props("dense align=left outside-arrows mobile-arrows")
                .classes("hw-slot-bar-tabs")
                # min-width: 0 lets the bar be narrower than its tabs; without it
                # the flex child grows to max-content, Quasar measures no overflow
                # and renders no arrows, and the bar's overflow:hidden clips the
                # excess tabs with no affordance.
                .style("flex: 1; min-width: 0; min-height: 36px;")
            ):
                for wrapper in bindings:
                    tab_el = ui.tab(name=wrapper.editor_binding_id, label="").props("no-caps")
                    if self._foldable:
                        tab_el.on(
                            "click",
                            lambda _e, bid=wrapper.editor_binding_id: self._on_bar_item_clicked(bid),
                        )
                    with tab_el:
                        with ui.row().classes("items-center gap-1 no-wrap"):
                            # Slot-owned chrome: dirty marker renders for every
                            # editor (including custom draw_tab overrides) so
                            # the unsaved-work signal can never be forgotten.
                            # Either flag means work would be lost on close.
                            if wrapper.state is not None and (
                                wrapper.state.is_dirty or wrapper.state.is_unsaved
                            ):
                                ui.icon("circle").classes("hw-tab-dirty").style(
                                    "font-size: 8px; color: var(--hw-text-body);"
                                )
                            # Editor-owned interior: icon and/or label.
                            wrapper.render_tab_into(orientation="horizontal")
                            # Slot-owned chrome: close button.
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
