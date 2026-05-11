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
from typing import Callable, Optional

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor import BaseEditor, editor
from haywire.core.session import (
    IProjectState,
    SessionContext,
    ContextSignal,
    ActiveGraphMoved,
    BroadcastClose,
    Close,
    GraphDataMutated,
    Reveal,
)
from haywire.ui.modals import confirm_modal, pick_modal, rename_modal, save_as_modal

from haybale_studio.state.edit_state import EditState
from haybale_haystack.signals import HaystackReloaded, HaystackTeardown
from haybale_haystack.state.haystack_state import HaystackState
from haybale_haystack.editors.graph_editor import GraphEditor
from haybale_haystack.graph_entry import GraphEntry

logger = logging.getLogger(__name__)


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
        """Request a redraw on activation.

        The editor sits in the left slot and shares the slot with other
        sidebar editors. While inactive, ``redraw_on_signal`` doesn't fire,
        so entries added or removed by other editors (e.g. FileBrowser
        opening a graph) don't trigger a redraw. Broadcasting
        ``GraphDataMutated`` here ensures switching back to this tab
        always shows current haystack state — and lets the wrapper's
        normal clear+redraw path rebuild the whole editor rather than
        relying on captured-element in-place updates.
        """
        self._notify_data_mutated(context)

    def draw(self, context: "SessionContext", container: ui.element) -> None:
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
        hs = context.app_data[HaystackState]
        is_dirty = hs._haystack_dirty
        # The dirty dot (when is_dirty=True) is rendered by panel_header
        # itself between the icon and the title — we only add the save
        # icon and the overflow menu on the action side here.
        with hui.panel_header(title, icon=hui.icon.haystack, is_dirty=is_dirty):
            # Save icon — paired with the dirty dot; only when dirty.
            if is_dirty:
                hui.icon_action(
                    hui.icon.save,
                    tooltip="Save",
                    on_click=lambda: self._on_save_haystack_in_place(context),
                )

            with ui.button(icon="more_vert").props("flat round dense size=sm").classes("flex-shrink-0"):
                with ui.menu():
                    ui.menu_item(
                        "Save As…",
                        on_click=lambda: self._on_save_haystack(context),
                    )
                    ui.menu_item(
                        "Load…",
                        on_click=lambda: self._on_load_haystack(context),
                    )
                    rename_item = ui.menu_item(
                        "Rename…",
                        on_click=lambda: self._on_rename_haystack(context),
                    )
                    # Disable rename if no haystack is currently loaded.
                    if not self._get_active_haystack_name(context):
                        rename_item.props("disable")

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
            if not entries:
                ui.label("No graphs open").classes("text-xs hw-text-dim p-2 italic")
            else:
                for entry in entries:
                    self._render_entry(entry, context)
                    
            self._render_add_bar(context)


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

            # Dirty dot — amber when unsaved, hidden when clean
            if is_unsaved:
                ui.element("div").classes("w-2 h-2 rounded-full flex-shrink-0 bg-amber-400").style(
                    "border: 1px solid var(--hw-border);"
                )

            # Name (+ subtitle for untitled entries only)
            with ui.column().classes("flex-1 gap-0 min-w-0"):
                name_classes = "text-sm truncate font-medium " + (
                    "hw-text-body" if is_active else "hw-text-muted"
                )
                ui.label(entry.display_name).classes(name_classes)
                if entry.path is None:
                    ui.label("not saved").classes("text-xs hw-text-warning-dim")


            # Save icon — paired with the dirty dot; only when unsaved.
            if is_unsaved:
                hui.icon_action(
                    hui.icon.save,
                    tooltip="Save",
                    on_click=lambda eid=eid: self._on_entry_save(eid, context),
                )

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
        """Remove a graph entry from the haystack.

        Dirty entries (modified or never-saved) get a discard-and-remove
        confirmation that warns about losing unsaved work. Clean entries
        get a milder confirm that calls out that the file stays on disk.
        """
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
        if is_dirty:
            if entry.path is not None:
                message = f'"{entry.display_name}" has unsaved changes. Discard them?'
            else:
                message = "This graph has never been saved. Discard it?"
            confirm_label = "Discard"
        else:
            message = f'Remove "{entry.display_name}" from this haystack? The file stays on disk.'
            confirm_label = "Remove"

        confirm_modal(
            title="Remove graph?",
            message=message,
            confirm_label=confirm_label,
            danger=True,
            on_confirm=lambda: self._remove_entry(entry, context),
        )

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
    # rename dialog
    # ------------------------------------------------------------------

    def _open_rename_dialog(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Open a modal to rename a graph entry.

        Pre-condition: ``entry.path`` is not None. Untitled entries are
        redirected to Save-As by the caller.
        """
        assert entry.path is not None, "_open_rename_dialog requires a file-backed entry"
        current_stem = entry.path.stem
        parent = entry.path.parent

        # Collect stems of sibling .haywire files; rename_graph refuses to
        # overwrite, so disable confirm on collision up front.
        existing_stems = [sibling.stem for sibling in parent.glob("*.haywire") if sibling != entry.path]

        def _do_rename(new_name: str) -> None:
            if new_name == current_stem:
                return  # no-op
            hs = context.app_data[HaystackState]
            success = hs.rename_graph(entry, new_name)
            if not success:
                ui.notify("Rename failed", type="negative", position="top-right")
                return
            session = context.session
            if entry.graph is context.data[EditState].active_graph.value:
                context.data[EditState].active_graph_path.value = entry.path
                if session:
                    session.signal(ActiveGraphMoved())
            ui.notify(f"Renamed to: {entry.path.name}", type="positive", position="top-right")

        rename_modal(
            title="Rename Graph",
            value=current_stem,
            existing=existing_stems,
            classify={"same": "Rename", "changed": "Rename", "existing": "Name taken"},
            allow_overwrite=False,
            on_confirm=_do_rename,
        )

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
        initial_path: "Optional[str]" = None,
    ) -> None:
        """Open the Save-As modal for a graph entry.

        Handles the overwrite-confirm flow: when the chosen path resolves to
        an existing file that is NOT the entry's own current path, a stacked
        :func:`confirm_modal` asks for confirmation before clobbering. On
        cancel the save-as modal reopens with the user's typed path so they
        don't lose their input.

        Args:
            initial_path: Override the default pre-filled value. Used to
                preserve the user's input when reopening after an overwrite
                cancel. When ``None``, the value is derived from
                ``entry.path`` (or a sensible default for unnamed entries).
        """
        workspace_root = Path(getattr(app, "workspace_root", str(Path.home())))

        if initial_path is None:
            if entry.path is not None:
                try:
                    initial_path = str(entry.path.relative_to(workspace_root))
                except ValueError:
                    initial_path = entry.path.name
            else:
                save_dir = self._default_save_dir(app)
                graph_name = getattr(entry.graph, "name", None) or "untitled"
                safe_name = graph_name.lower().replace(" ", "_")
                try:
                    rel_dir = save_dir.relative_to(workspace_root)
                    initial_path = str(rel_dir / f"{safe_name}.haywire")
                except ValueError:
                    initial_path = f"{safe_name}.haywire"

        def _do_save(save_path: Path) -> None:
            hs = context.app_data[HaystackState]
            success = hs.save_graph(entry, save_as=save_path)
            if not success:
                ui.notify("Save failed — check the path and try again", type="negative")
                return
            session = context.session
            if entry.graph is context.data[EditState].active_graph.value:
                context.data[EditState].active_graph_path.value = save_path
                if session:
                    session.signal(ActiveGraphMoved())
            ui.notify(f"Saved: {save_path.name}", type="positive", position="top-right")
            if on_success is not None:
                on_success()

        def _on_confirm(save_path: Path, raw_input: str) -> None:
            # If the chosen path is the entry's own current path, it's an
            # in-place save — no overwrite prompt needed.
            if save_path == entry.path:
                _do_save(save_path)
                return
            if save_path.exists():
                confirm_modal(
                    title="Overwrite file?",
                    message=f'"{save_path.name}" already exists. Overwrite it?',
                    confirm_label="Overwrite",
                    danger=True,
                    on_confirm=lambda: _do_save(save_path),
                    on_cancel=lambda: self._open_save_as_dialog(
                        app, entry, context, on_success, initial_path=raw_input
                    ),
                )
                return
            _do_save(save_path)

        save_as_modal(
            title="Save Graph As",
            workspace_root=workspace_root,
            initial_path=initial_path,
            suffixes=(".haywire",),
            on_confirm=_on_confirm,
        )

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
        hs = context.app_data[HaystackState]
        hs.start_execution(entry)
        self._notify_data_mutated(context)

    def _on_stop_execution(self, entry_id: str, context: "SessionContext") -> None:
        """Stop execution on a graph entry."""
        entry = self._resolve_entry(entry_id, context)
        if entry is None:
            return
        hs = context.app_data[HaystackState]
        hs.stop_execution(entry)
        self._notify_data_mutated(context)

    # ------------------------------------------------------------------
    # haystack actions
    # ------------------------------------------------------------------

    def _on_save_haystack(self, context: "SessionContext") -> None:
        """Save the current set of open graphs as a haystack ("Save As…")."""
        app: IProjectState = context.app
        if app is None:
            ui.notify("Graph manager not available", type="warning")
            return

        hs = context.app_data[HaystackState]

        def _do_save(name: str) -> None:
            active_path = context.data[EditState].active_graph_path.value
            hs.save_haystack(name, active_path=active_path)
            # hs.save_haystack broadcasts GraphDataMutated; the editor
            # redraws and the header chrome reflects the new clean state.
            ui.notify(f"Haystack '{name}' saved", type="positive")

        rename_modal(
            title="Save Haystack",
            value=self._get_active_haystack_name(context) or "untitled",
            existing=hs.list_haystacks(),
            on_confirm=_do_save,
        )

    def _on_save_haystack_in_place(self, context: "SessionContext") -> None:
        """Save the currently-loaded haystack without prompting.

        Falls through to :meth:`_on_save_haystack` (the Save-As modal) when
        no haystack is loaded — there's nothing to overwrite, so the user
        has to name it.
        """
        active = self._get_active_haystack_name(context)
        if not active:
            self._on_save_haystack(context)
            return

        app: IProjectState = context.app
        if app is None:
            ui.notify("Graph manager not available", type="warning")
            return

        hs = context.app_data[HaystackState]
        active_path = context.data[EditState].active_graph_path.value
        hs.save_haystack(active, active_path=active_path)
        ui.notify(f"Haystack '{active}' saved", type="positive")

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

        def _do_load(name: str) -> None:
            # hs.load_haystack does NOT clear existing entries — that
            # responsibility lives at the caller. Clear first so the
            # loaded set replaces, not appends.
            for existing in list(hs.all_entries()):
                hs.remove_entry(existing)

            active_path = hs.load_haystack(name)

            # Resolve the active entry from the returned absolute path,
            # falling back to the first entry if missing/None.
            active_entry: Optional["GraphEntry"] = None
            if active_path is not None:
                active_entry = hs.get_by_path(active_path)
            if active_entry is None:
                entries = hs.all_entries()
                if entries:
                    active_entry = entries[0]

            session = context.session
            if active_entry is not None and session is not None:
                session.lifecycle(
                    Reveal(
                        editor=GraphEditor,
                        payload=active_entry.entry_id,
                        label=active_entry.display_name,
                    )
                )

            # hs.load_haystack broadcasts GraphDataMutated (via the
            # per-entry open_graph calls); the editor redraws and the
            # header chrome reflects the freshly-loaded clean state.
            ui.notify(f"Haystack '{name}' loaded", type="positive")

        pick_modal(
            title="Load Haystack",
            options=haystacks,
            confirm_label="Load",
            on_confirm=_do_load,
        )

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
        options: dict[str, Path] = {}
        for f in available:
            try:
                rel = str(f.relative_to(workspace_root))
            except ValueError:
                rel = str(f)
            options[rel] = f

        def _do_open(selected: str) -> None:
            path = options[selected]
            session = context.session
            if session is None:
                ui.notify("Graph manager not available", type="warning")
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

        pick_modal(
            title="Open Graph",
            options=list(options.keys()),
            confirm_label="Open",
            searchable=True,
            on_confirm=_do_open,
        )

    # ------------------------------------------------------------------
    # rename haystack dialog
    # ------------------------------------------------------------------

    def _get_active_haystack_name(self, context: "SessionContext") -> Optional[str]:
        """Return the currently-active haystack name (or None).

        Reads ``HaystackSettings.last_haystack_name`` — that is the
        authoritative location after PR2's carve-out (Q1-A). The legacy
        ``workspace_manager.snapshot["haystack"]`` key is no longer
        consulted here.
        """
        from haybale_haystack.settings.haystack_settings import HaystackSettings

        try:
            settings = HaystackSettings()
        except Exception:
            return None
        name = settings.last_haystack_name
        return name or None

    def _on_rename_haystack(self, context: "SessionContext") -> None:
        """Open a modal to rename the current haystack."""
        old_name = self._get_active_haystack_name(context)
        if not old_name:
            ui.notify("No haystack is currently loaded", type="warning")
            return

        app = context.app
        if app is None:
            ui.notify("Graph manager not available", type="warning")
            return

        hs = context.app_data[HaystackState]

        def _do_rename(new_name: str) -> None:
            if new_name == old_name:
                return  # no-op
            success = hs.rename_haystack(old_name, new_name)
            if not success:
                ui.notify("Rename failed", type="negative", position="top-right")
                return
            # Keep last_haystack_name in lockstep with the rename — without
            # this, the next on_enable would try to rehydrate from the OLD
            # name (whose TOML was just renamed) and warn-and-skip.
            if hs._haystack_settings is not None and hs._haystack_settings.last_haystack_name == old_name:
                hs._haystack_settings.last_haystack_name = new_name
            # hs.rename_haystack only renames the TOML file — it does NOT
            # broadcast. Trigger a redraw so the header picks up the new
            # active-haystack name.
            self._notify_data_mutated(context)
            ui.notify(f"Haystack renamed to '{new_name}'", type="positive")

        rename_modal(
            title="Rename Haystack",
            value=old_name,
            existing=hs.list_haystacks(),
            classify={"same": "Rename", "changed": "Rename", "existing": "Name taken"},
            allow_overwrite=False,
            on_confirm=_do_rename,
        )

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
    # cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        self._list_container = None
