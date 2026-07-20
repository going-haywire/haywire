"""
ErrorsEditor — master-detail view of the error ledger.

Sits next to the Terminal editor in the bottom (INFO) slot. New errors arrive
live via the cross-session ``ErrorLogged`` signal: the process-wide ledger is
UI-ignorant and only exposes a zero-arg listener hook; the studio app bridges
that hook to ``ErrorLogged`` (marshalling off the watchdog/scan thread onto the
event loop). This editor just subscribes with ``@react_on(ErrorLogged)`` and
re-renders the list — no polling. Errors logged before the bridge is wired
(during early library scan) are still captured in the ledger and appear on this
editor's first ``draw()``.

Layout: a scrollable row list on the left, a detail pane on the right showing
the selected entry's full formatted report (HaywireException.format_detailed(),
snapshotted into the ledger entry at log() time). ``@react_on`` (not a full
redraw) keeps the detail pane and splitter position intact when a new error
arrives while the user is reading one.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.core.errors.haywire_exception import ErrorSeverity
from haywire.core.errors.ledger import get_error_ledger
from haywire.core.session.handlers import react_on
from haywire.core.session.signals import ErrorLogged, Signal
from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from nicegui.element import Element

_SEVERITY_DOT_COLOR = {
    ErrorSeverity.INFO.value: "blue",
    ErrorSeverity.WARNING.value: "yellow",
    ErrorSeverity.ERROR.value: "orange",
    ErrorSeverity.CRITICAL.value: "red",
}


def _format_timestamp(ts: Optional[float]) -> str:
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


@editor(
    label="Errors",
    icon=hui.icon.debug,
    default_slot=SlotName.INFO,
    description="Error ledger. Lists HaywireExceptions logged since startup; click one for details.",
)
class ErrorsEditor(BaseEditor):
    """Renders the process-wide error ledger as a clickable list with a detail pane."""

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self._rows_container: Optional[ui.column] = None
        self._detail_container: Optional[ui.column] = None
        self._count_label: Optional[ui.label] = None
        self._entries_by_seq: dict[int, dict] = {}
        self._selected_seq: Optional[int] = None

    def draw(self, context: "SessionContext", container: "Element") -> None:
        with container:
            with ui.splitter(value=45, limits=(15, 85)).classes("w-full h-full") as splitter:
                with splitter.before:
                    with ui.column().classes("w-full h-full gap-0"):
                        with hui.panel_header("Errors", icon=hui.icon.debug):
                            self._count_label = ui.label("").classes("text-xs hw-text-dim ml-auto")
                            hui.icon_action(hui.icon.delete, tooltip="Clear", on_click=self._clear)
                        with ui.scroll_area().classes("flex-1 w-full"):
                            self._rows_container = ui.column().classes("w-full gap-0")
                with splitter.after:
                    with ui.scroll_area().classes("w-full h-full"):
                        self._detail_container = ui.column().classes("w-full h-full")

            self._selected_seq = None
            self._render_rows()
            self._render_detail()

    @react_on(ErrorLogged)
    def _on_error_logged(self, context: "SessionContext", signal: Signal) -> None:
        """A new error was recorded — refresh just the list.

        ``@react_on`` (targeted) rather than a full editor redraw so the detail
        pane the user may be reading and the dragged splitter position survive.
        Fires even when this tab is backgrounded (kept-alive), so the list stays
        current behind the Terminal tab.
        """
        self._render_rows()

    def _render_rows(self) -> None:
        if self._rows_container is None:
            return
        ledger = get_error_ledger()
        page = ledger.query(limit=500)
        self._entries_by_seq = {entry["seq"]: entry for entry in page.entries}

        if self._count_label is not None:
            self._count_label.text = f"{page.total} entries"

        self._rows_container.clear()
        with self._rows_container:
            if not page.entries:
                hui.empty_state("No errors logged", icon=hui.icon.debug)
                return
            for entry in reversed(page.entries):
                dot_color = _SEVERITY_DOT_COLOR.get(entry.get("severity") or "", "grey")
                sub_parts = [_format_timestamp(entry["timestamp"])]
                if entry.get("registry_key"):
                    sub_parts.append(entry["registry_key"])
                elif entry.get("library"):
                    sub_parts.append(entry["library"])
                seq = entry["seq"]
                row = hui.list_item(
                    entry["message"],
                    sublabel=" · ".join(sub_parts),
                    dot_color=dot_color,
                    on_click=lambda seq=seq: self._select(seq),
                )
                if seq == self._selected_seq:
                    row.style("background: var(--hw-bg-hover);")

        # Selection may have scrolled out of the ledger's bounded window.
        if self._selected_seq is not None and self._selected_seq not in self._entries_by_seq:
            self._selected_seq = None
            self._render_detail()

    def _select(self, seq: int) -> None:
        self._selected_seq = seq
        self._render_rows()
        self._render_detail()

    def _render_detail(self) -> None:
        if self._detail_container is None:
            return
        self._detail_container.clear()
        with self._detail_container:
            entry = self._entries_by_seq.get(self._selected_seq) if self._selected_seq else None
            if entry is None:
                hui.empty_state("Select an error to see details", icon=hui.icon.debug)
                return
            with hui.panel_header(entry["category"] or "Error", icon=hui.icon.debug):
                pass
            if entry.get("suggestions"):
                with ui.column().classes("w-full gap-1 p-2"):
                    hui.section_label("Suggestions")
                    for suggestion in entry["suggestions"]:
                        ui.label(f"• {suggestion}").classes("text-xs hw-text-body")
            ui.code(entry.get("detail") or entry["message"], language="text").classes(
                "w-full text-xs"
            ).style("border-radius: 0; min-height: 100%;")

    def _clear(self) -> None:
        get_error_ledger().clear()
        self._selected_seq = None
        self._render_rows()
        self._render_detail()

    def cleanup(self) -> None:
        # The @react_on(ErrorLogged) bus subscription is dropped by the
        # framework at editor cleanup / hot-reload — nothing to unwire here.
        self._rows_container = None
        self._detail_container = None
        self._count_label = None
        self._entries_by_seq = {}
