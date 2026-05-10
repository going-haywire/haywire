# barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py
"""
HaystackEditor — open-graphs list for the left area.

Shows every graph currently loaded by Haystack (open files + any new
untitled/unnamed graphs). The user can:
  - Click a row to make that graph active in the GraphEditor
  - Click the "+" button in the header to create a new unnamed graph
  - Save / load haystacks (named graph selections) via the header
  - Start / stop per-graph execution via play/stop buttons on each row
  - Save / Save-As / Rename / Delete graphs via per-row overflow menu

The list rebuilds on ACTIVE_GRAPH_CHANGED (to refresh the active highlight)
and DATA_MUTATED (to reflect unsaved/modified state).
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from haywire.core.session.protocols import IProjectState
from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.core.session.signals_and_lifecycle import (
    ActiveGraphMoved,
    BroadcastClose,
    Close,
    GraphDataMutated,
    Reveal,
)
from haywire.ui.components.popup import Popup

from haybale_haystack.signals import HaystackReloaded, HaystackTeardown
from haybale_haystack.state.haystack_state import HaystackState
from haybale_haystack.editors.graph_editor import GraphEditor
from haybale_studio.state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.core.session.signals_and_lifecycle import ContextSignal
    from haybale_haystack.graph_entry import GraphEntry
    from nicegui.element import Element


logger = logging.getLogger(__name__)


def _workspace_rel_path(path: Path, workspace_root: "Path | None") -> str:
    """Return path relative to workspace_root when possible, else absolute path."""
    if workspace_root is not None:
        try:
            return str(path.relative_to(workspace_root))
        except ValueError:
            pass
    return str(path)


@editor(
    label="Haystack",
    icon=hui.icon.haystack,
    default_slot="left",
    description='All open graphs. Click to switch; "+" to create a new graph.',
)
class HaystackEditor(BaseEditor):
    """
    Left-area editor that lists all graphs tracked by Haystack.

    One entry per open file or new unnamed graph.  Clicking an entry fires
    EDITOR_FOCUSED with reveal_editor=GraphEditor and reveal_payload=entry.entry_id.
    The shell reveals the matching tab, then GraphEditor.on_focus updates
    context.data[EditState].active_graph / active_graph_path and broadcasts ACTIVE_GRAPH_CHANGED.

    The "+" header button calls HaystackState.create_new() and fires
    EDITOR_FOCUSED with reveal_editor=GraphEditor to activate the
    freshly created entry.
    """

    def __init__(self):
        self._list_container = None
        self._header_title_label = None
        self._rename_haystack_menu_item = None

    # ------------------------------------------------------------------
    # signal hooks / draw
    # ------------------------------------------------------------------

    def on_signal(self, context: "SessionContext", signal: "ContextSignal") -> None:
        """Side-effect hook — fires on every wrapper, active or not.

        HaystackTeardown must run regardless of focus: when the
        haystack is hot-reloaded while this editor is backgrounded,
        the GraphEditor tabs in this session still need to be closed.
        Issuing the local ``Close(payload=eid)`` lifecycle commands
        from here (rather than from ``redraw_on_signal``) makes the
        cleanup independent of which left-slot tab the user happens
        to have active.
        """
        if isinstance(signal, HaystackTeardown):
            self._on_haystack_teardown(context, signal)

    def redraw_on_signal(self, context: "SessionContext", signal: "ContextSignal") -> bool:
        """Pure decision: should the active HaystackEditor redraw?

        Backgrounded HaystackEditor instances catch up via on_focus,
        which already calls ``_render_list``. No need to redraw an
        invisible panel.
        """
        return isinstance(signal, (ActiveGraphMoved, GraphDataMutated, HaystackReloaded))

    def _on_haystack_teardown(self, context: "SessionContext", signal: "HaystackTeardown") -> None:
        """Translate the teardown fact into local tab-close lifecycle commands.

        Each session's HaystackEditor receives the cross-session
        HaystackTeardown signal and issues a local ``Close(payload=eid)``
        for every vanishing entry_id. AppShell fans the close across this
        session's TabSlots; sessions with no matching tab are unaffected.
        Local (not BroadcastClose) because the signal already broadcast
        and each session is reacting in parallel — broadcasting again
        would loop.
        """
        session = context.session
        if session is None:
            return
        for eid in signal.entry_ids:
            if not eid:
                continue
            try:
                session.lifecycle(Close(payload=eid))
            except Exception as exc:
                logger.warning(f"HaystackEditor: Close({eid}) failed during teardown: {exc}")

    def on_focus(self, context: "SessionContext") -> None:
        """Refresh the header title and entry list on activation.

        The editor sits in the left slot and shares the slot with other
        sidebar editors. While inactive, ``poll`` does not run, so entries
        added or removed by other editors (e.g. FileBrowser opening a graph)
        don't trigger a redraw. Re-rendering here ensures switching back to
        this tab always shows current haystack state.

        Safe before first ``draw``: both ``_render_header`` and
        ``_render_list`` are no-ops until their target containers exist.
        """
        if self._header_title_label is not None:
            title = self._get_active_haystack_name(context) or "Haystacks"
            self._header_title_label.text = title
            self._update_rename_haystack_enabled(context)
        if self._list_container is not None:
            self._render_list(context)

    def draw(self, context: "SessionContext", container: "Element") -> None:
        with container:
            with ui.column().classes("w-full h-full gap-0"):
                self._render_header(context)
                with ui.scroll_area().classes("flex-1 w-full"):
                    self._list_container = ui.column().classes("w-full gap-0 p-1")
                    self._render_list(context)

    # ------------------------------------------------------------------
    # header
    # ------------------------------------------------------------------

    def _render_header(self, context: "SessionContext") -> None:
        title = self._get_active_haystack_name(context) or "Haystacks"
        with hui.panel_header(title, icon=hui.icon.haystack) as header:
            # Grab the title label so we can update it later (second child after the icon)
            for child in header:
                if isinstance(child, ui.label):
                    self._header_title_label = child
                    break
            with ui.button(icon="more_vert").props("flat round dense size=sm").classes("flex-shrink-0"):
                with ui.menu():
                    ui.menu_item(
                        "Save Haystack",
                        on_click=lambda: self._on_save_haystack(context),
                    )
                    ui.menu_item(
                        "Load Haystack",
                        on_click=lambda: self._on_load_haystack(context),
                    )
                    self._rename_haystack_menu_item = ui.menu_item(
                        "Rename Haystack…",
                        on_click=lambda: self._on_rename_haystack(context),
                    )
                    # Disable rename if no haystack is currently loaded
                    self._update_rename_haystack_enabled(context)

    def _render_add_bar(self, context: "SessionContext") -> None:
        """Slim + button row matching graph entry width and alignment."""
        with ui.row().classes("w-full px-2 py-1.5 items-center justify-center rounded hw-list-item-hover"):
            with ui.button(icon="add").props("flat dense size=sm").classes("w-full"):
                with ui.menu():
                    ui.menu_item(
                        "New Graph",
                        on_click=lambda: self._on_new(context),
                    )
                    ui.menu_item(
                        "Open Graph…",
                        on_click=lambda: self._on_open_graph(context),
                    )

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------

    def _render_list(self, context: "SessionContext") -> None:
        if self._list_container is None:
            return
        self._list_container.clear()

        app = context.app
        if app is None:
            with self._list_container:
                ui.label("Graph manager not available").classes("text-xs hw-text-dim p-2 italic")
            return

        hs = context.app_data[HaystackState]
        entries = hs.all_entries()

        with self._list_container:
            self._render_add_bar(context)
            if not entries:
                ui.label("No graphs open").classes("text-xs hw-text-dim p-2 italic")
                return
            for entry in entries:
                self._render_entry(entry, context)

    def _render_entry(self, entry: "GraphEntry", context: "SessionContext") -> None:
        is_active = entry.graph is context.data[EditState].active_graph.value
        is_unsaved = entry.unsaved or entry.path is None
        is_executing = entry.is_executing

        # Row classes — active highlight or hover, plus execution tint
        row_classes = "w-full px-2 py-1.5 cursor-pointer items-center gap-2 rounded "
        if is_active:
            row_classes += "hw-list-item-active "
        else:
            row_classes += "hw-list-item-hover "

        # Execution state: left border accent
        row_style = "border-left: 3px solid transparent;"
        if is_executing:
            row_style = "border-left: 3px solid var(--hw-success);"

        # Capture entry_id (string) rather than the GraphEntry object so
        # handlers re-resolve through the live HaystackState. After a
        # haystack hot-reload the captured entry would otherwise point at
        # a disposed GraphEntry — clicking play would spawn an orphan
        # interpreter the new registry never sees.
        eid = entry.entry_id

        with (
            ui.row()
            .classes(row_classes)
            .style(row_style)
            .on("click", lambda e, eid=eid: self._on_select(eid, context))
        ):
            # Dirty dot — amber when unsaved, hidden when clean
            if is_unsaved:
                ui.element("div").classes("w-2 h-2 rounded-full flex-shrink-0 bg-amber-400").style(
                    "border: 1px solid var(--hw-border);"
                )
            else:
                # Invisible spacer to keep alignment
                ui.element("div").classes("w-2 h-2 flex-shrink-0")

            # Play / stop execution toggle
            if is_executing:
                hui.icon_action(
                    "stop",
                    tooltip="Stop execution",
                    on_click=lambda eid=eid: self._on_stop_execution(eid, context),
                )
            else:
                hui.icon_action(
                    hui.icon.resume,
                    tooltip="Start execution",
                    on_click=lambda eid=eid: self._on_start_execution(eid, context),
                )

            # Name + subtitle
            with ui.column().classes("flex-1 gap-0 min-w-0"):
                name_classes = "text-sm truncate font-medium " + (
                    "hw-text-body" if is_active else "hw-text-muted"
                )
                ui.label(entry.display_name).classes(name_classes)

                if entry.path is not None:
                    app = context.app
                    ws_root = Path(app.workspace_root) if app and hasattr(app, "workspace_root") else None
                    ui.label(_workspace_rel_path(entry.path, ws_root)).classes(
                        "text-xs hw-text-dim truncate"
                    )
                else:
                    ui.label("not saved").classes("text-xs hw-text-warning-dim")

            # Overflow menu — hidden during execution
            if not is_executing:
                with (
                    ui.button(icon="more_vert")
                    .props("flat round dense size=xs")
                    .classes("flex-shrink-0")
                    .on("click.stop", lambda: None)
                ):
                    with ui.menu():
                        ui.menu_item(
                            "Save",
                            on_click=lambda eid=eid: self._on_entry_save(eid, context),
                        )
                        ui.menu_item(
                            "Save as…",
                            on_click=lambda eid=eid: self._on_entry_save_as(eid, context),
                        )
                        ui.menu_item(
                            "Rename…",
                            on_click=lambda eid=eid: self._on_entry_rename(eid, context),
                        )
                        ui.separator()
                        ui.menu_item(
                            "Remove",
                            on_click=lambda eid=eid: self._on_entry_delete(eid, context),
                        )

    # ------------------------------------------------------------------
    # per-entry file actions
    # ------------------------------------------------------------------

    def _resolve_entry(self, entry_id: str, context: "SessionContext") -> "Optional[GraphEntry]":
        """Re-resolve a captured entry_id against the live HaystackState.

        Returns None and notifies the user if the entry is gone (e.g. the
        haystack was hot-reloaded since the row was rendered). All row
        handlers go through this so a stale lambda click can never act
        on a disposed GraphEntry.
        """
        hs = context.app_data[HaystackState]
        entry = hs.get_by_id(entry_id)
        if entry is None:
            ui.notify("Graph no longer available — list refreshed", type="info", position="top-right")
        return entry

    def _on_entry_save(self, entry_id: str, context: "SessionContext") -> None:
        """Save a graph; opens save-as dialog if untitled."""
        app = context.app
        if app is None:
            ui.notify("Graph manager not available", type="warning")
            return
        entry = self._resolve_entry(entry_id, context)
        if entry is None:
            return

        hs = context.app_data[HaystackState]
        if entry.path is not None:
            success = hs.save_graph(entry)
            if success:
                ui.notify(f"Saved: {entry.path.name}", type="positive", position="top-right")
            else:
                ui.notify("Save failed", type="negative", position="top-right")
            return

        # No path — open save-as dialog
        self._open_save_as_dialog(app, entry, context)

    def _on_entry_save_as(self, entry_id: str, context: "SessionContext") -> None:
        """Always open the save-as dialog."""
        app = context.app
        if app is None:
            ui.notify("Graph manager not available", type="warning")
            return
        entry = self._resolve_entry(entry_id, context)
        if entry is None:
            return
        self._open_save_as_dialog(app, entry, context)

    def _on_entry_rename(self, entry_id: str, context: "SessionContext") -> None:
        """Rename: inline edit for file-backed graphs, save-as for untitled."""
        entry = self._resolve_entry(entry_id, context)
        if entry is None:
            return
        if entry.is_executing:
            ui.notify("Stop execution before renaming", type="warning")
            return
        if entry.path is None:
            # Untitled → redirect to save-as (re-resolve again inside)
            self._on_entry_save_as(entry_id, context)
            return
        self._open_rename_dialog(entry, context)

    def _on_entry_delete(self, entry_id: str, context: "SessionContext") -> None:
        """Remove a graph entry; prompt for dirty entries before discarding."""
        entry = self._resolve_entry(entry_id, context)
        if entry is None:
            return
        if entry.is_executing:
            ui.notify("Stop execution before removing", type="warning")
            return
        app = context.app
        if app is None:
            ui.notify("Graph manager not available", type="warning")
            return

        is_dirty = entry.unsaved or entry.path is None
        if not is_dirty:
            self._remove_entry(entry, context)
            return

        self._open_remove_confirm_dialog(entry, context)

    def _remove_entry(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Tear down a graph entry: stop execution, remove, notify.

        Pre-condition: ``entry`` is not executing and the haystack is available.
        Callers are responsible for the ``is_executing`` guard
        and for any dirty-state confirmation flow before invoking this.
        """
        is_active = entry.graph is context.data[EditState].active_graph.value
        removed_id = entry.entry_id  # capture before remove_entry drops

        # Stop execution if running (defensive — should already be stopped)
        entry.stop_execution()

        # Remove from haystack
        hs = context.app_data[HaystackState]
        hs.remove_entry(entry)

        session = context.session
        if session is not None:
            # Fan tab-close to every session: peer sessions might have a
            # GraphEditor open on this entry, and the entity is gone for
            # everyone. BroadcastClose is the cross-session sibling of
            # Close — each session's AppShell handles it locally.
            # Peer haystack-derived views (the list, etc.) refresh via
            # the GraphDataMutated broadcast that HaystackState.remove_entry
            # fires — no separate observation signal needed.
            session.lifecycle(BroadcastClose(payload=removed_id))

        # If it was the active graph, clear the active graph → empty state
        if is_active:
            edit_state = context.data[EditState]
            edit_state.active_graph.value = None
            edit_state.active_graph_path.value = None
            if session:
                session.signal(ActiveGraphMoved())

        ui.notify(f"Removed: {entry.display_name}", type="info", position="top-right")

    # ------------------------------------------------------------------
    # remove confirmation dialog
    # ------------------------------------------------------------------

    def _open_remove_confirm_dialog(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Confirm before removing a dirty entry.

        For file-backed + modified entries: Save / Save As… / Discard / Cancel.
        For unnamed entries (``path is None``): Save As… / Discard / Cancel
        (no plain Save — there is no target file).
        """
        app = context.app
        can_save_in_place = entry.path is not None

        popup = Popup(
            title="Remove graph?",
            width="400px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
        )
        with popup:
            if can_save_in_place:
                msg = f'"{entry.display_name}" has unsaved changes.'
            else:
                msg = "This graph has never been saved."
            ui.label(msg).classes("text-sm")
            ui.label("What would you like to do?").classes("text-sm hw-text-dim")

            def _save_and_remove():
                hs = context.app_data[HaystackState]
                success = hs.save_graph(entry)
                if success:
                    self._remove_entry(entry, context)
                    popup.close()
                else:
                    ui.notify("Save failed", type="negative", position="top-right")

            def _save_as_and_remove():
                popup.close()
                self._open_save_as_dialog(
                    app,
                    entry,
                    context,
                    on_success=lambda: self._remove_entry(entry, context),
                )

            def _discard_and_remove():
                self._remove_entry(entry, context)
                popup.close()

            with ui.row().classes("w-full justify-end gap-2 mt-3"):
                ui.button("Cancel", on_click=popup.close).props("flat dense")
                ui.button("Discard", on_click=_discard_and_remove).props("flat dense color=negative")
                ui.button("Save As…", on_click=_save_as_and_remove).props("dense")
                if can_save_in_place:
                    ui.button("Save", on_click=_save_and_remove).props("color=positive dense")

        popup.open()

    # ------------------------------------------------------------------
    # rename dialog
    # ------------------------------------------------------------------

    def _open_rename_dialog(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Open a Popup to rename a graph entry."""
        popup = Popup(
            title="Rename Graph",
            width="320px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
        )
        with popup:
            rename_input = hui.input_field(
                label="Name",
                value=entry.path.stem if entry.path else "",
                autofocus=True,
            )
            error_label = ui.label("").classes("text-xs hw-text-danger -mt-1")
            error_label.set_visibility(False)

            def _do_rename():
                new_name = (rename_input.value or "").strip()
                if not new_name:
                    error_label.text = "Name cannot be empty"
                    error_label.set_visibility(True)
                    return

                current_stem = entry.path.stem if entry.path else ""
                if new_name == current_stem:
                    popup.close()
                    return

                app = context.app
                if app is None:
                    ui.notify("Graph manager not available", type="warning")
                    popup.close()
                    return

                hs = context.app_data[HaystackState]
                success = hs.rename_graph(entry, new_name)
                if success:
                    session = context.session
                    if entry.graph is context.data[EditState].active_graph.value:
                        context.data[EditState].active_graph_path.value = entry.path
                        if session:
                            session.signal(ActiveGraphMoved())
                    ui.notify(f"Renamed to: {entry.path.name}", type="positive", position="top-right")
                    popup.close()
                else:
                    error_label.text = "Rename failed — file may already exist"
                    error_label.set_visibility(True)

            hui.dialog_actions(on_confirm=_do_rename, on_cancel=popup.close, confirm_label="Rename")

        popup.open()

    # ------------------------------------------------------------------
    # save-as dialog
    # ------------------------------------------------------------------

    def _default_save_dir(self, app) -> Path:
        """Return workspace_root/graphs/ if it exists, else workspace_root/."""
        root = Path(getattr(app, "workspace_root", str(Path.home())))
        graphs_dir = root / "graphs"
        return graphs_dir if graphs_dir.is_dir() else root

    def _open_save_as_dialog(
        self,
        app,
        entry: "GraphEntry",
        context: "SessionContext",
        on_success: "Optional[Callable[[], None]]" = None,
    ) -> None:
        """Open a Popup for Save-As."""
        workspace_root = Path(getattr(app, "workspace_root", str(Path.home())))

        if entry.path is not None:
            try:
                input_value = str(entry.path.relative_to(workspace_root))
            except ValueError:
                input_value = entry.path.name
        else:
            save_dir = self._default_save_dir(app)
            graph_name = getattr(entry.graph, "name", None) or "untitled"
            safe_name = graph_name.lower().replace(" ", "_")
            try:
                rel_dir = save_dir.relative_to(workspace_root)
                input_value = str(rel_dir / f"{safe_name}.haywire")
            except ValueError:
                input_value = f"{safe_name}.haywire"

        popup = Popup(
            title="Save Graph As",
            width="460px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
        )
        with popup:
            with (
                ui.row()
                .classes("w-full items-center gap-1 px-1")
                .style(
                    "background: var(--hw-bg-page); border-radius: 4px; border: 1px solid var(--hw-border);"
                )
            ):
                ui.icon("folder", size="14px").classes("hw-text-dim flex-shrink-0")
                ui.label(str(workspace_root).rstrip("/") + "/").classes(
                    "text-xs font-mono hw-text-dim truncate py-1"
                )

            exists_warning = ui.label("").classes("text-xs hw-text-danger -mt-1")
            exists_warning.set_visibility(False)

            path_input = (
                ui.input(label="Path within workspace", value=input_value)
                .classes("w-full")
                .props("outlined dense")
                .on("update:model-value", lambda _: exists_warning.set_visibility(False))
            )

            def _do_save_as():
                path_str = (path_input.value or "").strip()
                if not path_str:
                    ui.notify("Please enter a file name", type="warning")
                    return

                save_path = (workspace_root / path_str).resolve()
                if not save_path.suffix:
                    save_path = save_path.with_suffix(".haywire")

                if save_path.exists() and save_path != entry.path:
                    exists_warning.text = f'"{save_path.name}" already exists — choose a different name.'
                    exists_warning.set_visibility(True)
                    return

                hs = context.app_data[HaystackState]
                success = hs.save_graph(entry, save_as=save_path)
                if success:
                    session = context.session
                    if entry.graph is context.data[EditState].active_graph.value:
                        context.data[EditState].active_graph_path.value = save_path
                        if session:
                            session.signal(ActiveGraphMoved())
                    ui.notify(f"Saved: {save_path.name}", type="positive", position="top-right")
                    popup.close()
                    if on_success is not None:
                        on_success()
                else:
                    ui.notify("Save failed — check the path and try again", type="negative")

            with ui.row().classes("w-full justify-end gap-2 mt-1"):
                ui.button("Cancel", on_click=popup.close).props("flat dense")
                ui.button("Save", on_click=_do_save_as).props("color=positive dense")

        popup.open()

    # ------------------------------------------------------------------
    # actions (new graph / select)
    # ------------------------------------------------------------------

    def _on_new(self, context: "SessionContext") -> None:
        """Create a new unnamed graph and activate it."""
        app: IProjectState = context.app
        session = context.session
        if app is None or session is None:
            return

        hs = context.app_data[HaystackState]
        entry = hs.create_new()
        session.lifecycle(
            Reveal(
                editor=GraphEditor,
                payload=entry.entry_id,
                label=entry.display_name,
            )
        )

    def _on_select(self, entry_id: str, context: "SessionContext") -> None:
        """Activate an existing graph entry."""
        session = context.session
        if session is None:
            return
        entry = self._resolve_entry(entry_id, context)
        if entry is None:
            return
        session.lifecycle(
            Reveal(
                editor=GraphEditor,
                payload=entry.entry_id,
                label=entry.display_name,
            )
        )

    # ------------------------------------------------------------------
    # execution actions
    # ------------------------------------------------------------------

    def _on_start_execution(self, entry_id: str, context: "SessionContext") -> None:
        """Start execution on a graph entry."""
        entry = self._resolve_entry(entry_id, context)
        if entry is None:
            return
        entry.start_execution()
        self._notify_data_mutated(context)

    def _on_stop_execution(self, entry_id: str, context: "SessionContext") -> None:
        """Stop execution on a graph entry."""
        entry = self._resolve_entry(entry_id, context)
        if entry is None:
            return
        entry.stop_execution()
        self._notify_data_mutated(context)

    # ------------------------------------------------------------------
    # haystack actions
    # ------------------------------------------------------------------

    def _on_save_haystack(self, context: "SessionContext") -> None:
        """Save the current set of open graphs as a haystack."""
        app: IProjectState = context.app
        if app is None:
            ui.notify("Graph manager not available", type="warning")
            return

        hs = context.app_data[HaystackState]
        haystacks = hs.list_haystacks()

        popup = Popup(
            title="Save Haystack",
            width="320px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
        )
        with popup:
            name_input = hui.input_field(
                label="Name",
                value=haystacks[0] if haystacks else "default",
            )

            if haystacks:
                ui.label("Existing:").classes("text-xs hw-text-dim mt-2")
                for h in haystacks:
                    ui.label(f"  {h}").classes("text-xs hw-text-muted")

            def _do_save():
                name = (name_input.value or "").strip()
                if not name:
                    ui.notify("Name cannot be empty", type="warning")
                    return
                # Task 9 will remove the haystack save from app.save_workspace;
                # this is the new authoritative call site for haystack TOML
                # persistence. Until Task 9 lands, save_workspace also writes
                # the same TOML — the duplicate write is harmless (verified in
                # Task 4 that the schema matches legacy).
                from haybale_haystack import persistence
                from haywire.core.di.context import get_workspace_root

                active_path = context.data[EditState].active_graph_path.value
                persistence.dump_haystack(hs, get_workspace_root(), name, active_path=active_path)

                context.app.workspace_manager.snapshot["haystack"] = name
                context.app.save_workspace(active_graph_path=active_path)
                self._update_header_title(context)
                ui.notify(f"Haystack '{name}' saved", type="positive")
                popup.close()

            hui.dialog_actions(on_confirm=_do_save, on_cancel=popup.close, confirm_label="Save")

        popup.open()

    def _on_load_haystack(self, context: "SessionContext") -> None:
        """Load a haystack, replacing all currently open graphs."""
        app: IProjectState = context.app
        if app is None:
            ui.notify("Graph manager not available", type="warning")
            return

        hs = context.app_data[HaystackState]
        haystacks = hs.list_haystacks()

        if not haystacks:
            ui.notify("No haystacks found", type="info")
            return

        unsaved = hs.unsaved_entries()

        popup = Popup(
            title="Load Haystack",
            width="320px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
        )
        with popup:
            if unsaved:
                ui.label(
                    f"Warning: {len(unsaved)} graph(s) have unsaved changes that will be lost."
                ).classes("text-xs hw-text-warning-dim mt-1")

            haystack_select = (
                ui.select(
                    options=haystacks,
                    value=haystacks[0],
                    label="Haystack",
                )
                .props("dense")
                .classes("w-full mt-2")
            )

            def _do_load():
                name = haystack_select.value

                # persistence.load_haystack does NOT clear the existing entries
                # — that responsibility was deliberately moved to the caller
                # when the I/O was extracted into pure helpers. Clear the
                # registry first so the loaded set replaces, not appends.
                for existing in list(hs.all_entries()):
                    hs.remove_entry(existing)

                from haybale_haystack import persistence
                from haywire.core.di.context import get_workspace_root

                workspace_root = get_workspace_root()
                active_path = persistence.load_haystack(hs, workspace_root, name)

                # Resolve the active entry from the returned absolute path,
                # falling back to the first entry if missing/None.
                active_entry: Optional["GraphEntry"] = None
                if active_path is not None:
                    active_entry = hs.get_by_path(active_path)
                if active_entry is None:
                    entries = hs.all_entries()
                    if entries:
                        active_entry = entries[0]

                context.app.workspace_manager.snapshot["haystack"] = name
                context.app.save_workspace(active_graph_path=context.data[EditState].active_graph_path.value)

                session = context.session
                if active_entry is not None and session is not None:
                    session.lifecycle(
                        Reveal(
                            editor=GraphEditor,
                            payload=active_entry.entry_id,
                            label=active_entry.display_name,
                        )
                    )

                self._update_header_title(context)
                ui.notify(f"Haystack '{name}' loaded", type="positive")
                popup.close()

            hui.dialog_actions(on_confirm=_do_load, on_cancel=popup.close, confirm_label="Load")

        popup.open()

    # ------------------------------------------------------------------
    # open graph dialog
    # ------------------------------------------------------------------

    def _on_open_graph(self, context: "SessionContext") -> None:
        """Open a dialog to pick an existing .haywire file to add to the haystack."""
        app = context.app
        if app is None:
            ui.notify("Graph manager not available", type="warning")
            return

        hs = context.app_data[HaystackState]
        workspace_root = Path(getattr(app, "workspace_root", str(Path.home())))

        # Scan for all .haywire files, excluding those already open
        all_files = hs.list_graph_files()
        open_paths = {entry.path for entry in hs.all_entries() if entry.path is not None}
        available = [f for f in all_files if f not in open_paths]

        if not available:
            ui.notify("All graph files are already open", type="info")
            return

        # Build options: {relative_path_str: absolute_Path}
        options = {}
        for f in available:
            try:
                rel = str(f.relative_to(workspace_root))
            except ValueError:
                rel = str(f)
            options[rel] = f

        popup = Popup(
            title="Open Graph",
            width="360px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
        )
        with popup:
            graph_select = (
                ui.select(
                    options=list(options.keys()),
                    label="Graph file",
                    with_input=True,
                )
                .props("dense use-input")
                .classes("w-full mt-2")
            )

            def _do_open():
                selected = graph_select.value
                if not selected or selected not in options:
                    ui.notify("Please select a graph file", type="warning")
                    return

                path = options[selected]
                session = context.session
                if session is None:
                    ui.notify("Graph manager not available", type="warning")
                    popup.close()
                    return

                entry = hs.open_graph(path)
                session.lifecycle(
                    Reveal(
                        editor=GraphEditor,
                        payload=entry.entry_id,
                        label=entry.display_name,
                    )
                )
                ui.notify(f"Opened: {path.name}", type="positive", position="top-right")
                popup.close()

            hui.dialog_actions(on_confirm=_do_open, on_cancel=popup.close, confirm_label="Open")

        popup.open()

    # ------------------------------------------------------------------
    # rename haystack dialog
    # ------------------------------------------------------------------

    def _get_active_haystack_name(self, context: "SessionContext") -> Optional[str]:
        """Return the name of the currently loaded haystack, or None."""
        app = context.app
        if app is not None and hasattr(app, "workspace_manager"):
            return app.workspace_manager.snapshot.get("haystack")
        return None

    def _update_rename_haystack_enabled(self, context: "SessionContext") -> None:
        """Enable/disable the Rename Haystack menu item based on whether a haystack is loaded."""
        if self._rename_haystack_menu_item is None:
            return
        name = self._get_active_haystack_name(context)
        if name:
            self._rename_haystack_menu_item.props(remove="disable")
        else:
            self._rename_haystack_menu_item.props("disable")

    def _on_rename_haystack(self, context: "SessionContext") -> None:
        """Open a Popup to rename the current haystack."""
        old_name = self._get_active_haystack_name(context)
        if not old_name:
            ui.notify("No haystack is currently loaded", type="warning")
            return

        popup = Popup(
            title="Rename Haystack",
            width="320px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
        )
        with popup:
            name_input = hui.input_field(label="Name", value=old_name, autofocus=True)
            error_label = ui.label("").classes("text-xs hw-text-danger -mt-1")
            error_label.set_visibility(False)

            def _do_rename():
                new_name = (name_input.value or "").strip()
                if not new_name:
                    error_label.text = "Name cannot be empty"
                    error_label.set_visibility(True)
                    return

                if new_name == old_name:
                    popup.close()
                    return

                app = context.app
                if app is None:
                    ui.notify("Graph manager not available", type="warning")
                    popup.close()
                    return

                hs = context.app_data[HaystackState]
                success = hs.rename_haystack(old_name, new_name)
                if success:
                    context.app.workspace_manager.snapshot["haystack"] = new_name
                    context.app.save_workspace(
                        active_graph_path=context.data[EditState].active_graph_path.value
                    )
                    self._update_header_title(context)
                    ui.notify(f"Haystack renamed to '{new_name}'", type="positive")
                    popup.close()
                else:
                    error_label.text = "Rename failed — a haystack with that name may already exist"
                    error_label.set_visibility(True)

            hui.dialog_actions(on_confirm=_do_rename, on_cancel=popup.close, confirm_label="Rename")

        popup.open()

    def _notify_data_mutated(self, context: "SessionContext") -> None:
        """Fire ``GraphDataMutated`` cross-session.

        Used for non-mutating UI events that nonetheless want every
        HaystackEditor to redraw — currently just start/stop execution
        (the executing flag is per-row chrome, not a registry change).
        Mutating call sites don't need this: ``HaystackState`` itself
        broadcasts ``GraphDataMutated`` from every mutator.
        """
        session = context.session
        if session:
            session.signal(GraphDataMutated())

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _update_header_title(self, context: "SessionContext") -> None:
        """Refresh the header title to show the active haystack name."""
        if self._header_title_label is None:
            return
        name = self._get_active_haystack_name(context)
        self._header_title_label.text = name or "Haystacks"

    # ------------------------------------------------------------------
    # cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        self._header_title_label = None
        self._list_container = None
        self._rename_haystack_menu_item = None
