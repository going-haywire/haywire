"""
TabSlot — the Slot subclass for main / bottom slots.

Renders a column containing a horizontal tab bar on top (``ui.tabs``, plus an
optional chevron for the bottom slot that folds the area in/out) and the
``ui.tab_panels`` area below. Exposes mutators
(``open_tab``/``close_tab``/``repayload_tab``/``close_tabs_for_payload``) that
keep the slot's binding list in sync with the tab bar.

"""

from __future__ import annotations

import logging
from typing import ClassVar, Literal, Optional

from nicegui import ui

from haywire.ui.app.slot import EditorBinding, Slot
from haywire.ui.context_events import ContextChangedEvent, ContextChangeType

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
            active_id = self._active.binding_id if self._active is not None else None
            ids = [b.binding_id for b in self._bindings]
            initial = active_id if active_id in ids else (ids[0] if ids else None)
            with (
                ui.tabs(value=initial, on_change=lambda e: self._on_tab_clicked(e.value))
                .props("dense align=left")
                .classes("hw-slot-bar-tabs")
                .style("flex: 1; min-height: 36px;")
            ):
                for binding in self._bindings:
                    tab_el = ui.tab(name=binding.binding_id, label="").props("no-caps")
                    with tab_el:
                        with ui.row().classes("items-center gap-1 no-wrap"):
                            label = binding.label or getattr(
                                binding.editor_cls.class_identity, "label", binding.editor_key
                            )
                            ui.label(label)
                            if binding.can_close:
                                tab_id = binding.binding_id
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
        """Switch to the clicked tab and broadcast WORKSPACE_CHANGED."""
        editor_key, payload = EditorBinding.split_id(tab_id)
        if not self.switch_to(editor_key, payload):
            return
        self._refresh_bar()
        self._session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )

    def _on_tab_close_clicked(self, tab_id: str) -> None:
        """Emit TAB_CLOSE_REQUESTED so host apps can run domain cleanup."""
        editor_key, payload = EditorBinding.split_id(tab_id)
        self._session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.TAB_CLOSE_REQUESTED,
                source_editor="app_shell",
                detail={"slot_name": self.name, "editor_key": editor_key, "payload": payload},
            )
        )

    def _on_fold_toggle_clicked(self) -> None:
        self.set_visible(not self._visible)

    # ------------------------------------------------------------------
    # Tab mutators — shell delegates to these
    # ------------------------------------------------------------------

    def open_tab(
        self,
        editor_cls: type,
        editor_key: str,
        payload: Optional[str],
        label: str,
    ) -> bool:
        """Ensure a tab for ``(editor_key, payload)`` exists and make it active.

        Returns ``True`` iff the active tab actually changed.
        """
        existing = self.find_binding(editor_key, payload)
        if existing is not None:
            if self._active is existing:
                return False
            self.switch_to(editor_key, payload)
            self._refresh_bar()
            return True

        self.add_binding(
            EditorBinding(editor_key=editor_key, editor_cls=editor_cls, payload=payload),
            activate=True,
        )
        self._refresh_bar()
        return True

    def close_tab(self, editor_key: str, payload: Optional[str]) -> bool:
        """Close one tab — removes binding; promotes sibling when active."""

        def _cleanup(instance) -> None:
            try:
                instance.cleanup()
            except Exception as exc:
                logger.warning(f"TabSlot '{self.name}': cleanup error: {exc}")

        removed = self.remove_binding(editor_key, payload, cleanup=_cleanup)
        if removed is None:
            return False
        self._refresh_bar()
        return True

    def repayload_tab(
        self,
        editor_key: str,
        old_payload: Optional[str],
        new_payload: Optional[str],
        new_label: Optional[str] = None,
    ) -> bool:
        """Re-key a tab in place (e.g. Save-As). Preserves the editor instance."""
        if not self.repayload_binding(editor_key, old_payload, new_payload):
            return False
        if new_label is not None:
            binding = self.find_binding(editor_key, new_payload)
            if binding is not None:
                binding.label = new_label
        self._refresh_bar()
        return True

    def close_tabs_for_payload(self, payload: str) -> int:
        """Close every tab whose binding.payload == ``payload``."""
        matches = [b for b in self._bindings if b.payload == payload]
        closed = 0
        for binding in matches:
            if self.close_tab(binding.editor_key, binding.payload):
                closed += 1
        return closed
