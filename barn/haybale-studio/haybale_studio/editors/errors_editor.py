"""
ErrorsEditor — master-detail view of the error ledger with seen-state triage.

Sits next to the Terminal editor in the bottom (INFO) slot.

Two live-update paths, both cross-session (every session's editor stays in sync):

- ``ErrorLogged`` — a NEW error was recorded. Arrives from the thread-bridge:
  the process-wide ledger is UI-ignorant and only exposes a zero-arg listener
  hook, which the studio app marshals off the watchdog/scan thread onto the
  event loop and broadcasts as ``ErrorLogged``. Errors logged before the bridge
  is wired (early library scan) are still captured and appear on first ``draw()``.
- ``ErrorLedgerChanged`` — a TRIAGE mutation (seen / unseen / delete / mark-all).
  Published directly via ``session.publish`` from a UI action on the main loop.

Each ledger entry carries a ``seen`` flag. Selecting a row (to read its detail)
marks it seen; the row context menu toggles seen/unseen and deletes; a toolbar
button marks all seen. Unseen rows render bold + full-opacity dot; seen rows
recede (normal weight, dimmed dot). The tab shows a count badge tinted by the
worst *unseen* severity — hidden entirely when nothing is unseen.

Layout: a scrollable row list on the left, a detail pane on the right showing
the selected entry's full formatted report (snapshotted at log() time).
``@react_on`` (targeted re-render, not a full redraw) keeps the detail pane and
splitter position intact when the list changes underneath the user.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.core.errors.haywire_exception import ErrorSeverity
from haywire.core.errors.ledger import get_error_ledger
from haywire.core.session.handlers import react_on
from haywire.core.session.signals import ErrorLedgerChanged, ErrorLogged, Signal
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

# Worst-first ordering for the tab badge's severity tint.
_SEVERITY_RANK = {
    ErrorSeverity.CRITICAL.value: 3,
    ErrorSeverity.ERROR.value: 2,
    ErrorSeverity.WARNING.value: 1,
    ErrorSeverity.INFO.value: 0,
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
        self._context: Optional["SessionContext"] = None
        self._rows_container: Optional[ui.column] = None
        self._detail_container: Optional[ui.column] = None
        self._count_label: Optional[ui.label] = None
        self._entries_by_seq: dict[int, dict] = {}
        self._selected_seq: Optional[int] = None

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._context = context
        with container:
            with ui.splitter(value=45, limits=(15, 85)).classes("w-full h-full") as splitter:
                with splitter.before:
                    with ui.column().classes("w-full h-full gap-0"):
                        with hui.panel_header("Errors", icon=hui.icon.debug):
                            self._count_label = ui.label("").classes("text-xs hw-text-dim ml-auto")
                            hui.icon_action(
                                hui.icon.ok, tooltip="Mark all seen", on_click=self._mark_all_seen
                            )
                            hui.icon_action(hui.icon.delete, tooltip="Clear", on_click=self._clear)
                        with ui.scroll_area().classes("flex-1 w-full"):
                            self._rows_container = ui.column().classes("w-full gap-0")
                with splitter.after:
                    with ui.scroll_area().classes("w-full h-full"):
                        self._detail_container = ui.column().classes("w-full h-full")

            self._selected_seq = None
            self._render_rows()
            self._render_detail()

    def draw_tab(self, context, *, orientation) -> None:
        """Tab interior: label + an unseen badge (count, tinted by worst unseen severity).

        The badge is drawn only when there are unseen errors; when everything is
        seen (or the ledger is empty) the tab shows just the label. Slot owns the
        surrounding chrome, so we never draw the close button / active indicator.
        """
        label = self.wrapper.label or self.class_identity.label
        page = get_error_ledger().query(limit=500)
        unseen = [e for e in page.entries if not e.get("seen")]

        with ui.row().classes("items-center gap-1 no-wrap"):
            if orientation == "vertical":
                ui.icon(self.class_identity.icon).tooltip(self.class_identity.label)
            else:
                ui.label(label)
            if unseen:
                color = _SEVERITY_DOT_COLOR.get(self._worst_severity(unseen), "grey")
                ui.badge(str(len(unseen))).props(f"color={color}").classes("text-xs")

    @staticmethod
    def _worst_severity(entries: list[dict]) -> str:
        """Return the highest-ranked severity value across entries ('' if none)."""
        worst = ""
        worst_rank = -1
        for e in entries:
            sev = e.get("severity") or ""
            rank = _SEVERITY_RANK.get(sev, -1)
            if rank > worst_rank:
                worst_rank, worst = rank, sev
        return worst

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
                self._render_row(entry)

        # Selection may have scrolled out of the ledger's bounded window.
        if self._selected_seq is not None and self._selected_seq not in self._entries_by_seq:
            self._selected_seq = None
            self._render_detail()

    def _render_row(self, entry: dict) -> None:
        seq = entry["seq"]
        seen = bool(entry.get("seen"))
        dot_color = _SEVERITY_DOT_COLOR.get(entry.get("severity") or "", "grey")
        sub_parts = [_format_timestamp(entry["timestamp"])]
        if entry.get("registry_key"):
            sub_parts.append(entry["registry_key"])
        elif entry.get("library"):
            sub_parts.append(entry["library"])

        row = ui.row().classes(
            "w-full px-2 py-1.5 cursor-pointer hw-list-item-hover items-center gap-2 rounded no-wrap"
        )
        if seq == self._selected_seq:
            row.style("background: var(--hw-bg-hover);")
        row.on("click", lambda _e=None, s=seq: self._select(s))
        with row:
            dot = ui.element("div").classes(f"w-2 h-2 rounded-full bg-{dot_color}-500 flex-shrink-0")
            if seen:
                dot.style("opacity: 0.4;")
            with ui.column().classes("flex-1 gap-0 min-w-0"):
                # Unseen = bold (louder scan target); seen = normal weight, dimmed.
                weight = "font-medium" if seen else "font-bold"
                dim = " hw-text-dim" if seen else ""
                ui.label(entry["message"]).classes(f"text-sm truncate {weight}{dim}")
                ui.label(" · ".join(sub_parts)).classes("text-xs hw-text-dim")
            self._build_row_menu(entry)

    def _build_row_menu(self, entry: dict) -> None:
        """Right-click context menu for a row: toggle seen, delete."""
        seq = entry["seq"]
        seen = bool(entry.get("seen"))
        with ui.context_menu():
            if seen:
                ui.menu_item("Mark unseen", on_click=lambda s=seq: self._mark_unseen(s), auto_close=True)
            else:
                ui.menu_item("Mark seen", on_click=lambda s=seq: self._mark_seen(s), auto_close=True)
            ui.menu_item("Delete", on_click=lambda s=seq: self._delete(s), auto_close=True)

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

    # ------------------------------------------------------------------
    # Signal handlers — both refresh list + tab badge
    # ------------------------------------------------------------------

    @react_on(ErrorLogged, ErrorLedgerChanged)
    def _on_ledger_signal(self, context: "SessionContext", signal: Signal) -> None:
        """A new error was recorded, or triage state changed — refresh list + badge.

        ``@react_on`` (targeted) rather than a full editor redraw so the detail
        pane the user may be reading and the dragged splitter position survive.
        Fires even when this tab is backgrounded, so the badge and list stay
        current behind the Terminal tab.
        """
        self._render_rows()
        self.wrapper.refresh_tab_bar()

    # ------------------------------------------------------------------
    # Triage actions — mutate the ledger, then broadcast ErrorLedgerChanged.
    # The signal is cross-session and loops back to this session's own
    # _on_ledger_signal, so these do NOT re-render directly.
    # ------------------------------------------------------------------

    def _select(self, seq: int) -> None:
        # Selecting to read the detail marks the entry seen (per-error granularity).
        self._selected_seq = seq
        get_error_ledger().mark_seen(seq)
        self._render_detail()
        self._publish_changed()

    def _mark_seen(self, seq: int) -> None:
        get_error_ledger().mark_seen(seq)
        self._publish_changed()

    def _mark_unseen(self, seq: int) -> None:
        get_error_ledger().mark_unseen(seq)
        self._publish_changed()

    def _mark_all_seen(self) -> None:
        get_error_ledger().mark_all_seen()
        self._publish_changed()

    def _delete(self, seq: int) -> None:
        if seq == self._selected_seq:
            self._selected_seq = None
            self._render_detail()
        get_error_ledger().delete(seq)
        self._publish_changed()

    def _clear(self) -> None:
        get_error_ledger().clear()
        self._selected_seq = None
        self._render_detail()
        self._publish_changed()

    def _publish_changed(self) -> None:
        """Broadcast a triage mutation so every session's editor re-renders.

        Cross-session, so it loops back to this session too — that return trip
        re-renders our own list + badge via _on_ledger_signal.
        """
        if self._context is not None:
            self._context.session.publish(ErrorLedgerChanged())

    def cleanup(self) -> None:
        # The @react_on bus subscriptions are dropped by the framework at editor
        # cleanup / hot-reload — nothing to unwire here.
        self._context = None
        self._rows_container = None
        self._detail_container = None
        self._count_label = None
        self._entries_by_seq = {}
