"""
TabSlot — the Slot subclass for main / bottom slots.

Renders a column containing a horizontal tab bar on top (``ui.tabs``, plus an
optional chevron for the bottom slot that folds the area in/out) and the
``ui.tab_panels`` area below. Unlike ``IconSlot``, ``TabSlot`` owns a
``list[TabState]`` on its ``slot_state`` and exposes mutators
(``open_tab``/``close_tab``/``repayload_tab``/``close_tabs_for_payload``) that
keep the persisted tab list, the slot's bindings, and the active-tab mirror
in lockstep.

Persistence is performed via the ``persist_workspace`` callback passed at
construction so the slot stays framework-agnostic (no direct dependency on
``WorkspaceManager``).
"""

from __future__ import annotations

import logging
from typing import Optional

from nicegui import ui

from haywire.ui.app.slot import EditorBinding, Slot
from haywire.ui.context_events import ContextChangedEvent, ContextChangeType
from haywire.ui.workspace.workspace_state import TabState

logger = logging.getLogger(__name__)


class TabSlot(Slot):
    """Tabbed slot for the main and bottom shell slots.

    Notes:
        ``slot_state`` must expose ``tabs: list[TabState]`` and
        ``active_tab_key: Optional[str]``; main/bottom workspace states
        already do. Bottom slots additionally carry ``visible`` and ``size``.
        The optional ``show_fold_toggle`` flag renders the chevron expand/
        retract button at the end of the bar — used by the bottom slot.
    """

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, parent: ui.element) -> None:
        """Build ``[bar / area]`` column inside ``parent``."""
        # Main fills the remaining space; bottom content-sizes so dragging
        # the inner #hw-slot-bottom area height actually moves the layout.
        wrapper_flex = "flex: 1" if self.name == "main" else "flex: 0 0 auto"
        with parent:
            wrapper = (
                ui.column()
                .classes("gap-0")
                .style(f"width: 100%; {wrapper_flex}; min-height: 0; overflow: hidden;")
            )
        with wrapper:
            self._render_bar_row()
            self._area_parent_box = self._create_content_box()
        self._render_area(self._area_parent_box)
        self._area_parent_box.set_visibility(self._visible)

    def _create_content_box(self) -> ui.element:
        """Create the slot's outer content box — flex:1 for main, fixed height for bottom."""
        if self.name == "bottom":
            size = getattr(self._slot_state, "size", 200) if self._slot_state is not None else 200
            col = (
                ui.column()
                .classes("gap-0")
                .style(f"height: {size}px; min-height: 0; width: 100%; overflow: hidden;")
            )
            col._props["id"] = "hw-slot-bottom"
        else:
            col = ui.column().classes("gap-0 w-full").style("flex: 1; min-height: 0; overflow: hidden;")
            col._props["id"] = f"hw-slot-{self.name}"
        return col

    def _render_bar_row(self) -> None:
        self._bar_container = (
            ui.row()
            .classes("w-full items-center gap-0 flex-shrink-0 hw-slot-bar")
            .style(
                "background: var(--hw-bg-surface);"
                " border-top: 1px solid var(--hw-border);"
                " border-bottom: 1px solid var(--hw-border); min-height: 36px;"
                if self.name == "bottom"
                else "background: var(--hw-bg-surface);"
                " border-bottom: 1px solid var(--hw-border); min-height: 36px;"
            )
        )
        with self._bar_container:
            self._render_bar_contents()

    def _render_bar_contents(self) -> None:
        """Render tab row + optional chevron."""
        tabs = getattr(self._slot_state, "tabs", []) if self._slot_state is not None else []
        if tabs:
            active_tab_key = getattr(self._slot_state, "active_tab_key", None)
            ids = [t.tab_id for t in tabs]
            initial = active_tab_key if active_tab_key in ids else (ids[0] if ids else None)
            with (
                ui.tabs(value=initial, on_change=lambda e: self._on_tab_clicked(e.value))
                .props("dense align=left")
                .classes("hw-slot-bar-tabs")
                .style("flex: 1; min-height: 36px;")
            ):
                for tab in tabs:
                    if tab.editor_key is None:
                        continue
                    tab_el = ui.tab(name=tab.tab_id, label="").props("no-caps")
                    with tab_el:
                        with ui.row().classes("items-center gap-1 no-wrap"):
                            ui.label(tab.label)
                            if self._tab_close_visible(tab):
                                tab_id = tab.tab_id
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

    def _tab_close_visible(self, tab) -> bool:
        """Return True if ``tab`` should render a close button.

        Reads the binding's ``can_close`` when a matching binding exists.
        Falls back to ``True`` if the tab's editor class is no longer
        registered (prevents stranding).
        """
        if tab.editor_key is None:
            return False
        binding = self.find_binding(tab.editor_key, tab.payload)
        return True if binding is None else binding.can_close

    def set_visible(self, visible: bool) -> None:
        """Override: refresh the chevron icon on transition."""
        transitioning = visible != self._visible
        super().set_visible(visible)
        if transitioning:
            self._refresh_bar()

    def _refresh_bar(self) -> None:
        """Clear + re-render the bar so tab highlight and chevron stay in sync."""
        if self._bar_container is None:
            return
        self._bar_container.clear()
        with self._bar_container:
            self._render_bar_contents()

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

        # Drop the seed placeholder (editor_key=None) that default MainSlotState carries.
        if self._slot_state is not None:
            self._slot_state.tabs = [t for t in self._slot_state.tabs if t.editor_key is not None]
            metadata = {"payload": payload} if payload else {}
            self._slot_state.tabs.append(TabState(editor_key=editor_key, label=label, metadata=metadata))

        self.add_binding(
            EditorBinding(editor_key=editor_key, editor_cls=editor_cls, payload=payload),
            activate=True,
        )
        self._refresh_bar()
        self._persist_workspace()
        return True

    def close_tab(self, editor_key: str, payload: Optional[str]) -> bool:
        """Close one tab — removes binding + TabState; promotes sibling when active."""

        def _cleanup(instance) -> None:
            try:
                instance.cleanup()
            except Exception as exc:
                logger.warning(f"TabSlot '{self.name}': cleanup error: {exc}")

        removed = self.remove_binding(editor_key, payload, cleanup=_cleanup)
        if removed is None:
            return False
        tab_id = removed.binding_id
        if self._slot_state is not None:
            self._slot_state.tabs = [t for t in self._slot_state.tabs if t.tab_id != tab_id]
        self._refresh_bar()
        self._persist_workspace()
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
        old_tab_id = f"{editor_key}::{old_payload}" if old_payload else editor_key
        if self._slot_state is not None:
            for tab in self._slot_state.tabs:
                if tab.tab_id == old_tab_id:
                    if new_payload:
                        tab.metadata["payload"] = new_payload
                    else:
                        tab.metadata.pop("payload", None)
                    if new_label is not None:
                        tab.label = new_label
                    break
        self._refresh_bar()
        self._persist_workspace()
        return True

    def close_tabs_for_payload(self, payload: str) -> int:
        """Close every tab whose binding.payload == ``payload``."""
        matches = [b for b in self._bindings if b.payload == payload]
        closed = 0
        for binding in matches:
            if self.close_tab(binding.editor_key, binding.payload):
                closed += 1
        return closed
