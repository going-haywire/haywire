# packages/haywire-app/src/haywire_studio/editors/graph_manager_editor.py
"""
GraphManagerEditor — open-graphs list for the left area.

Shows every graph currently loaded by GraphManager (open files + any new
untitled/unnamed graphs). The user can:
  - Click a row to make that graph active in the GraphEditor
  - Click the "+" button in the header to create a new unnamed graph
  - Save / load haystacks (named graph selections) via the header
  - Start / stop per-graph execution via play/stop buttons on each row

The list rebuilds on ACTIVE_GRAPH_CHANGED (to refresh the active highlight)
and DATA_MUTATED (to reflect unsaved/modified state).
"""

from pathlib import Path
from typing import TYPE_CHECKING

from haywire.ui.protocols import IProjectState
from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.context_events import ContextChangeType, ContextChangedEvent

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent
    from haywire_studio.graph_manager import GraphEntry
    from nicegui.element import Element


_GRAPH_EDITOR_KEY = "studio:editor:graph_editor"


def _workspace_rel_path(path: Path, workspace_root: "Path | None") -> str:
    """Return path relative to workspace_root when possible, else absolute path."""
    if workspace_root is not None:
        try:
            return str(path.relative_to(workspace_root))
        except ValueError:
            pass
    return str(path)


@editor(
    registry_id="graph_manager",
    label="Graphs",
    icon=hui.icon.graph_manager,
    default_slot="left",
    description='All open graphs. Click to switch; "+" to create a new graph.',
)
class GraphManagerEditor(BaseEditor):
    """
    Left-area editor that lists all graphs tracked by GraphManager.

    One entry per open file or new unnamed graph.  Clicking an entry:
      1. Detaches the session from the current graph.
      2. Attaches the session to the selected graph.
      3. Updates context.active_graph / active_graph_path.
      4. Fires ACTIVE_GRAPH_CHANGED so GraphEditor swaps its canvas.
      5. Switches the middle-area tab to the GraphEditor.

    The "+" header button calls app.create_new_graph() and immediately
    activates the freshly created entry.
    """

    def __init__(self):
        self._list_container = None

    # ------------------------------------------------------------------
    # poll / draw
    # ------------------------------------------------------------------

    def poll(self, context: "SessionContext", event: "ContextChangedEvent") -> bool:
        return event.change_type in (
            ContextChangeType.ACTIVE_GRAPH_CHANGED,
            ContextChangeType.DATA_MUTATED,
        )

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
        with hui.panel_header("GRAPHS", icon=hui.icon.graph_manager):
            hui.icon_action(
                "folder_open", tooltip="Load haystack", on_click=lambda: self._on_load_haystack(context)
            )
            hui.icon_action(
                hui.icon.save, tooltip="Save haystack", on_click=lambda: self._on_save_haystack(context)
            )
            hui.icon_action("add", tooltip="New graph", on_click=lambda: self._on_new(context))

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------

    def _render_list(self, context: "SessionContext") -> None:
        if self._list_container is None:
            return
        self._list_container.clear()

        app = context.app
        if app is None or not hasattr(app, "graph_manager"):
            with self._list_container:
                ui.label("Graph manager not available").classes("text-xs hw-text-dim p-2 italic")
            return

        entries = app.graph_manager.all_entries()
        if not entries:
            with self._list_container:
                ui.label("No graphs open").classes("text-xs hw-text-dim p-2 italic")
            return

        with self._list_container:
            for entry in entries.values():
                self._render_entry(entry, context)

    def _render_entry(self, entry: "GraphEntry", context: "SessionContext") -> None:
        is_active = entry.graph is context.active_graph
        # A graph with no path is definitionally unsaved (never written to disk).
        is_unsaved = entry.unsaved or entry.path is None
        is_executing = entry.is_executing

        row_classes = "w-full px-2 py-1.5 cursor-pointer items-center gap-2 rounded " + (
            "hw-list-item-active " if is_active else "hw-list-item-hover "
        )

        with ui.row().classes(row_classes).on("click", lambda e, en=entry: self._on_select(en, context)):
            # Execution state indicator dot (green=running, amber=unsaved, transparent=clean)
            if is_executing:
                dot_color = "bg-green-400"
            elif is_unsaved:
                dot_color = "bg-amber-400"
            else:
                dot_color = "bg-transparent"
            ui.element("div").classes(f"w-2 h-2 rounded-full flex-shrink-0 {dot_color}").style(
                "border: 1px solid var(--hw-border);"
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
                    # No file path — always show the unsaved hint
                    ui.label("not saved").classes("text-xs hw-text-warning-dim")

            # Play / stop execution toggle
            if is_executing:
                hui.icon_action(
                    "stop",
                    tooltip="Stop execution",
                    on_click=lambda en=entry: self._on_stop_execution(en, context),
                )
            else:
                hui.icon_action(
                    hui.icon.resume,
                    tooltip="Start execution",
                    on_click=lambda en=entry: self._on_start_execution(en, context),
                )

            # Active indicator chevron
            if is_active:
                ui.icon("chevron_right", size="16px").classes("hw-text-accent flex-shrink-0")

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------

    def _on_new(self, context: "SessionContext") -> None:
        """Create a new unnamed graph and activate it."""
        app: IProjectState = context.app
        session = context.session
        if app is None or not hasattr(app, "create_new_graph") or session is None:
            ui.notify("Graph manager not available", type="warning")
            return

        # Detach from current graph
        self._detach_current(app, context, session)

        # Create the new graph and attach this session
        entry = app.create_new_graph(session.session_id)

        # Update context
        context.active_graph = entry.graph
        context.active_graph_path = entry.path

        self._activate_entry(entry, context, session)

    def _on_select(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Activate an existing graph entry."""
        if entry.graph is context.active_graph:
            # Already active — just make sure GraphEditor is visible
            self._switch_to_graph_editor(context)
            return

        app = context.app
        session = context.session
        if app is None or session is None:
            return

        # Detach from current graph
        self._detach_current(app, context, session)

        # Attach to selected entry
        app.graph_manager.session_attach(entry, session.session_id)

        # Update context
        context.active_graph = entry.graph
        context.active_graph_path = entry.path

        self._activate_entry(entry, context, session)

    # ------------------------------------------------------------------
    # execution actions
    # ------------------------------------------------------------------

    def _on_start_execution(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Start execution on a graph entry."""
        entry.start_execution()
        self._notify_data_mutated(context)

    def _on_stop_execution(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Stop execution on a graph entry."""
        entry.stop_execution()
        self._notify_data_mutated(context)

    # ------------------------------------------------------------------
    # haystack actions
    # ------------------------------------------------------------------

    def _on_save_haystack(self, context: "SessionContext") -> None:
        """Save the current set of open graphs as a haystack."""
        app: IProjectState = context.app
        if app is None or not hasattr(app, "graph_manager"):
            ui.notify("Graph manager not available", type="warning")
            return

        gm = app.graph_manager
        haystacks = gm.list_haystacks()

        with ui.dialog() as dlg, ui.card().classes("hw-panel min-w-[300px]"):
            ui.label("Save Haystack").classes("text-sm font-medium hw-text-body")
            name_input = ui.input(
                label="Name",
                value=haystacks[0] if haystacks else "default",
            ).classes("w-full")

            if haystacks:
                ui.label("Existing:").classes("text-xs hw-text-dim mt-2")
                for h in haystacks:
                    ui.label(f"  {h}").classes("text-xs hw-text-muted")

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=dlg.close).props("flat dense")

                def _do_save():
                    name = name_input.value.strip()
                    if not name:
                        ui.notify("Name cannot be empty", type="warning")
                        return
                    gm.save_haystack(name, active_graph_path=context.active_graph_path)
                    # Persist haystack name in workspace state
                    session = context.session
                    if session and session.workspace_manager:
                        session.workspace_manager.active.haystack = name
                        session.workspace_manager.save()
                    ui.notify(f"Haystack '{name}' saved", type="positive")
                    dlg.close()

                ui.button("Save", on_click=_do_save).props("flat dense")

        dlg.open()

    def _on_load_haystack(self, context: "SessionContext") -> None:
        """Load a haystack, replacing all currently open graphs."""
        app: IProjectState = context.app
        if app is None or not hasattr(app, "graph_manager"):
            ui.notify("Graph manager not available", type="warning")
            return

        gm = app.graph_manager
        haystacks = gm.list_haystacks()

        if not haystacks:
            ui.notify("No haystacks found", type="info")
            return

        # Check for unsaved work
        unsaved = gm.unsaved_entries()

        with ui.dialog() as dlg, ui.card().classes("hw-panel min-w-[300px]"):
            ui.label("Load Haystack").classes("text-sm font-medium hw-text-body")

            if unsaved:
                ui.label(
                    f"Warning: {len(unsaved)} graph(s) have unsaved changes that will be lost."
                ).classes("text-xs hw-text-warning-dim")

            selected = {"name": haystacks[0]}

            with ui.column().classes("w-full gap-1 mt-2"):
                for h in haystacks:
                    is_first = h == haystacks[0]
                    with (
                        ui.row()
                        .classes("w-full px-2 py-1 cursor-pointer rounded hw-list-item-hover items-center")
                        .on("click", lambda e, name=h: _select(name))
                    ):
                        ui.radio({h: h}, value=h if is_first else None).props("dense").bind_value_from(
                            selected, "name", lambda v, n=h: n if v == n else None
                        )
                        ui.label(h).classes("text-sm hw-text-body")

            def _select(name):
                selected["name"] = name

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=dlg.close).props("flat dense")

                def _do_load():
                    name = selected["name"]
                    entries, active_rel = gm.load_haystack(name, app._graph_factory)
                    # Subscribe validation handlers
                    for entry in entries:
                        app._subscribe_entry_validation(entry)
                    # Restore active graph
                    if active_rel:
                        ws_root = Path(app.workspace_root)
                        active_path = ws_root / active_rel
                        active_entry = gm.get_by_path(active_path)
                        if active_entry:
                            context.active_graph = active_entry.graph
                            context.active_graph_path = active_entry.path
                    elif entries:
                        context.active_graph = entries[0].graph
                        context.active_graph_path = entries[0].path
                    # Persist haystack name
                    session = context.session
                    if session and session.workspace_manager:
                        session.workspace_manager.active.haystack = name
                        session.workspace_manager.save()
                    # Notify UI
                    self._notify_data_mutated(context)
                    session = context.session
                    if session:
                        session.notify_context_changed(
                            ContextChangedEvent(
                                change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                                source_editor="graph_manager",
                            )
                        )
                    ui.notify(f"Haystack '{name}' loaded", type="positive")
                    dlg.close()

                ui.button("Load", on_click=_do_load).props("flat dense")

        dlg.open()

    def _notify_data_mutated(self, context: "SessionContext") -> None:
        """Fire DATA_MUTATED to refresh the graph list."""
        session = context.session
        if session:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.DATA_MUTATED,
                    source_editor="graph_manager",
                )
            )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _detach_current(self, app, context: "SessionContext", session) -> None:
        """Detach the session from whatever graph it is currently viewing."""
        if context.active_graph_path is not None:
            current_entry = app.graph_manager.get_by_path(context.active_graph_path)
        elif context.active_graph is not None:
            # path=None covers both '__untitled__' and '__new_N__' — use identity
            current_entry = app.graph_manager.get_by_graph(context.active_graph)
        else:
            current_entry = None
        if current_entry is not None:
            app.graph_manager.session_detach(current_entry, session.session_id)

    def _activate_entry(self, entry: "GraphEntry", context: "SessionContext", session) -> None:
        """Fire ACTIVE_GRAPH_CHANGED and switch to the graph editor tab."""
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                source_editor="graph_manager",
                detail=entry,
            )
        )
        self._switch_to_graph_editor(context)

    def _switch_to_graph_editor(self, context: "SessionContext") -> None:
        tabs = context.metadata.get("main_tabs")
        if tabs is not None:
            try:
                tabs.set_value(_GRAPH_EDITOR_KEY)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        self._list_container = None
