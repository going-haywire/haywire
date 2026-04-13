# packages/haywire-app/src/haywire_studio/editors/graph_manager_editor.py
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
from typing import TYPE_CHECKING, Optional

from haywire.ui.protocols import IProjectState
from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.context_events import ContextChangeType, ContextChangedEvent

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent
    from haywire_studio.haystack import GraphEntry
    from nicegui.element import Element

logger = logging.getLogger(__name__)

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
    label="Haystack",
    icon=hui.icon.haystack,
    default_slot="left",
    description='All open graphs. Click to switch; "+" to create a new graph.',
)
class HaystackEditor(BaseEditor):
    """
    Left-area editor that lists all graphs tracked by Haystack.

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
        # Save-As dialog state
        self._save_as_dialog = None
        self._save_base_dir: Optional[Path] = None
        self._save_base_dir_label = None
        self._save_path_input = None
        self._save_exists_warning = None
        self._save_as_entry: Optional["GraphEntry"] = None
        self._save_as_context: Optional["SessionContext"] = None
        # Rename dialog state
        self._rename_dialog = None
        self._rename_input = None
        self._rename_error_label = None
        self._rename_entry: Optional["GraphEntry"] = None
        self._rename_context: Optional["SessionContext"] = None

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
            # Dialogs (Quasar teleports to <body>)
            self._save_as_dialog = self._build_save_as_dialog(context)
            self._rename_dialog = self._build_rename_dialog()

    # ------------------------------------------------------------------
    # header
    # ------------------------------------------------------------------

    def _render_header(self, context: "SessionContext") -> None:
        with hui.panel_header("Haystacks", icon=hui.icon.haystack):
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
        if app is None or not hasattr(app, "haystack"):
            with self._list_container:
                ui.label("Graph manager not available").classes("text-xs hw-text-dim p-2 italic")
            return

        entries = app.haystack.all_entries()
        if not entries:
            with self._list_container:
                ui.label("No graphs open").classes("text-xs hw-text-dim p-2 italic")
            return

        with self._list_container:
            for entry in entries.values():
                self._render_entry(entry, context)

    def _render_entry(self, entry: "GraphEntry", context: "SessionContext") -> None:
        is_active = entry.graph is context.active_graph
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

        with (
            ui.row()
            .classes(row_classes)
            .style(row_style)
            .on("click", lambda e, en=entry: self._on_select(en, context))
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
                    on_click=lambda en=entry: self._on_stop_execution(en, context),
                )
            else:
                hui.icon_action(
                    hui.icon.resume,
                    tooltip="Start execution",
                    on_click=lambda en=entry: self._on_start_execution(en, context),
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
                            on_click=lambda en=entry: self._on_entry_save(en, context),
                        )
                        ui.menu_item(
                            "Save as…",
                            on_click=lambda en=entry: self._on_entry_save_as(en, context),
                        )
                        ui.menu_item(
                            "Rename…",
                            on_click=lambda en=entry: self._on_entry_rename(en, context),
                        )
                        ui.separator()
                        ui.menu_item(
                            "Remove",
                            on_click=lambda en=entry: self._on_entry_delete(en, context),
                        )

    # ------------------------------------------------------------------
    # per-entry file actions
    # ------------------------------------------------------------------

    def _on_entry_save(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Save a graph; opens save-as dialog if untitled."""
        app = context.app
        if app is None or not hasattr(app, "haystack"):
            ui.notify("Graph manager not available", type="warning")
            return

        if entry.path is not None:
            success = app.haystack.save_graph(entry)
            if success:
                ui.notify(f"Saved: {entry.path.name}", type="positive", position="top-right")
                self._broadcast_mutation(app, entry)
            else:
                ui.notify("Save failed", type="negative", position="top-right")
            return

        # No path — open save-as dialog
        self._open_save_as_dialog(app, entry, context)

    def _on_entry_save_as(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Always open the save-as dialog."""
        app = context.app
        if app is None or not hasattr(app, "haystack"):
            ui.notify("Graph manager not available", type="warning")
            return
        self._open_save_as_dialog(app, entry, context)

    def _on_entry_rename(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Rename: inline edit for file-backed graphs, save-as for untitled."""
        if entry.is_executing:
            ui.notify("Stop execution before renaming", type="warning")
            return
        if entry.path is None:
            # Untitled → redirect to save-as
            self._on_entry_save_as(entry, context)
            return
        self._open_rename_dialog(entry, context)

    def _on_entry_delete(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Remove a graph entry from the haystack (does not delete the file)."""
        if entry.is_executing:
            ui.notify("Stop execution before removing", type="warning")
            return
        app = context.app
        if app is None or not hasattr(app, "haystack"):
            ui.notify("Graph manager not available", type="warning")
            return

        is_active = entry.graph is context.active_graph

        # Stop execution if running
        entry.stop_execution()

        # Detach all sessions
        for sid in list(entry.sessions):
            app.haystack.session_detach(entry, sid)

        # Remove from haystack
        app.haystack.remove_entry(entry)

        # If it was the active graph, clear the active graph → empty state
        if is_active:
            context.active_graph = None
            context.active_graph_path = None
            session = context.session
            if session:
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                        source_editor="haystack",
                    )
                )

        ui.notify(f"Removed: {entry.display_name}", type="info", position="top-right")
        self._notify_data_mutated(context)

    # ------------------------------------------------------------------
    # rename dialog
    # ------------------------------------------------------------------

    def _open_rename_dialog(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Pre-fill the rename dialog and open it."""
        if self._rename_dialog is None or self._rename_input is None:
            ui.notify("Rename dialog not ready", type="warning")
            return

        self._rename_entry = entry
        self._rename_context = context
        self._rename_input.value = entry.path.stem if entry.path else ""
        if self._rename_error_label is not None:
            self._rename_error_label.set_visibility(False)
        self._rename_dialog.open()

    def _build_rename_dialog(self):
        """Create the rename dialog once during draw(). Returns the dialog."""
        with ui.dialog() as dialog, hui.dialog_card("w-[320px]"):
            ui.label("Rename Graph").classes("text-sm font-medium hw-text-body")
            self._rename_input = hui.input_field(label="Name", value="", autofocus=True)
            self._rename_error_label = ui.label("").classes("text-xs hw-text-danger -mt-1")
            self._rename_error_label.set_visibility(False)
            hui.dialog_actions(
                on_confirm=self._do_rename,
                on_cancel=dialog.close,
                confirm_label="Rename",
            )
        return dialog

    def _do_rename(self) -> None:
        """Execute the rename from within the dialog."""
        entry = self._rename_entry
        context = self._rename_context
        if entry is None or context is None or self._rename_dialog is None:
            return

        new_name = (self._rename_input.value or "").strip()
        if not new_name:
            self._rename_error_label.text = "Name cannot be empty"
            self._rename_error_label.set_visibility(True)
            return

        current_stem = entry.path.stem if entry.path else ""
        if new_name == current_stem:
            self._rename_dialog.close()
            return

        app = context.app
        if app is None or not hasattr(app, "haystack"):
            ui.notify("Graph manager not available", type="warning")
            self._rename_dialog.close()
            return

        success = app.haystack.rename_graph(entry, new_name)
        if success:
            if entry.graph is context.active_graph:
                context.active_graph_path = entry.path
                session = context.session
                if session:
                    session.notify_context_changed(
                        ContextChangedEvent(
                            change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                            source_editor="haystack",
                            detail=entry,
                        )
                    )
            self._broadcast_mutation(app, entry)
            ui.notify(f"Renamed to: {entry.path.name}", type="positive", position="top-right")
            self._rename_dialog.close()
        else:
            self._rename_error_label.text = "Rename failed — file may already exist"
            self._rename_error_label.set_visibility(True)

    # ------------------------------------------------------------------
    # save-as dialog
    # ------------------------------------------------------------------

    def _default_save_dir(self, app) -> Path:
        """Return workspace_root/graphs/ if it exists, else workspace_root/."""
        root = Path(getattr(app, "workspace_root", str(Path.home())))
        graphs_dir = root / "graphs"
        return graphs_dir if graphs_dir.is_dir() else root

    def _open_save_as_dialog(self, app, entry: "GraphEntry", context: "SessionContext") -> None:
        """Pre-fill the Save-As dialog and open it."""
        if self._save_as_dialog is None or self._save_path_input is None:
            ui.notify("Save-As dialog not ready", type="warning")
            return

        self._save_as_entry = entry
        self._save_as_context = context

        workspace_root = Path(getattr(app, "workspace_root", str(Path.home())))
        self._save_base_dir = workspace_root

        if self._save_base_dir_label is not None:
            self._save_base_dir_label.text = str(workspace_root).rstrip("/") + "/"

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

        self._save_path_input.value = input_value
        if self._save_exists_warning is not None:
            self._save_exists_warning.set_visibility(False)
        self._save_as_dialog.open()

    def _build_save_as_dialog(self, context: "SessionContext"):
        """Create the Save-As dialog once during draw(). Returns the dialog."""
        with ui.dialog() as dialog, ui.card().style("min-width: 460px; max-width: 640px"):
            with ui.column().classes("w-full gap-2"):
                ui.label("Save Graph As").classes("text-base font-semibold")

                with (
                    ui.row()
                    .classes("w-full items-center gap-1 px-1")
                    .style(
                        "background: var(--hw-bg-page); border-radius: 4px;"
                        " border: 1px solid var(--hw-border);"
                    )
                ):
                    ui.icon("folder", size="14px").classes("hw-text-dim flex-shrink-0")
                    self._save_base_dir_label = ui.label("").classes(
                        "text-xs font-mono hw-text-dim truncate py-1"
                    )

                self._save_path_input = (
                    ui.input(label="Path within workspace")
                    .classes("w-full")
                    .props("outlined dense")
                    .on("update:model-value", lambda _: self._clear_exists_warning())
                )
                self._save_exists_warning = ui.label("").classes("text-xs hw-text-danger -mt-1")
                self._save_exists_warning.set_visibility(False)
                with ui.row().classes("w-full justify-end gap-2 mt-1"):
                    ui.button("Cancel", on_click=dialog.close).props("flat dense")
                    ui.button(
                        "Save",
                        on_click=lambda: self._do_save_as(dialog),
                    ).props("color=positive dense")
        return dialog

    def _clear_exists_warning(self) -> None:
        if self._save_exists_warning is not None:
            self._save_exists_warning.set_visibility(False)

    def _do_save_as(self, dialog) -> None:
        """Execute the Save-As from within the dialog."""
        entry = self._save_as_entry
        context = self._save_as_context
        if entry is None or context is None:
            dialog.close()
            return

        app = context.app
        if app is None:
            ui.notify("App not available", type="warning")
            return

        path_str = (self._save_path_input.value or "").strip()
        if not path_str:
            ui.notify("Please enter a file name", type="warning")
            return

        if self._save_base_dir is None:
            ui.notify("Base directory not set", type="warning")
            return

        save_path = (self._save_base_dir / path_str).resolve()
        if not save_path.suffix:
            save_path = save_path.with_suffix(".haywire")

        if save_path.exists() and save_path != entry.path:
            if self._save_exists_warning is not None:
                self._save_exists_warning.text = (
                    f'"{save_path.name}" already exists — choose a different name.'
                )
                self._save_exists_warning.set_visibility(True)
            return

        success = app.haystack.save_graph(entry, save_as=save_path)
        if success:
            # Update context if this is the active graph
            if entry.graph is context.active_graph:
                context.active_graph_path = save_path
                session = context.session
                if session:
                    session.notify_context_changed(
                        ContextChangedEvent(
                            change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                            source_editor="haystack",
                            detail=entry,
                        )
                    )
            self._broadcast_mutation(app, entry)
            ui.notify(f"Saved: {save_path.name}", type="positive", position="top-right")
            dialog.close()
        else:
            ui.notify("Save failed — check the path and try again", type="negative")

    # ------------------------------------------------------------------
    # actions (new graph / select)
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
        app.haystack.session_attach(entry, session.session_id)

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
        if app is None or not hasattr(app, "haystack"):
            ui.notify("Graph manager not available", type="warning")
            return

        gm = app.haystack
        haystacks = gm.list_haystacks()

        with ui.dialog() as dlg, hui.dialog_card("w-[320px]"):
            ui.label("Save Haystack").classes("text-sm font-medium hw-text-body")
            name_input = hui.input_field(
                label="Name",
                value=haystacks[0] if haystacks else "default",
            )

            if haystacks:
                ui.label("Existing:").classes("text-xs hw-text-dim mt-2")
                for h in haystacks:
                    ui.label(f"  {h}").classes("text-xs hw-text-muted")

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

            hui.dialog_actions(on_confirm=_do_save, on_cancel=dlg.close, confirm_label="Save")

        dlg.open()

    def _on_load_haystack(self, context: "SessionContext") -> None:
        """Load a haystack, replacing all currently open graphs."""
        app: IProjectState = context.app
        if app is None or not hasattr(app, "haystack"):
            ui.notify("Graph manager not available", type="warning")
            return

        gm = app.haystack
        haystacks = gm.list_haystacks()

        if not haystacks:
            ui.notify("No haystacks found", type="info")
            return

        # Check for unsaved work
        unsaved = gm.unsaved_entries()

        with ui.dialog() as dlg, hui.dialog_card("w-[320px]"):
            ui.label("Load Haystack").classes("text-sm font-medium hw-text-body")

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
                            source_editor="haystack",
                        )
                    )
                ui.notify(f"Haystack '{name}' loaded", type="positive")
                dlg.close()

            hui.dialog_actions(on_confirm=_do_load, on_cancel=dlg.close, confirm_label="Load")

        dlg.open()

    def _notify_data_mutated(self, context: "SessionContext") -> None:
        """Fire DATA_MUTATED to refresh the graph list."""
        session = context.session
        if session:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.DATA_MUTATED,
                    source_editor="haystack",
                )
            )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _broadcast_mutation(self, app, entry: "GraphEntry") -> None:
        """Broadcast a DATA_MUTATED event to all sessions viewing this graph."""
        if hasattr(app, "session_manager"):
            try:
                app.session_manager.broadcast_data_mutation(graph_path=entry.path)
            except Exception:
                pass

    def _detach_current(self, app, context: "SessionContext", session) -> None:
        """Detach the session from whatever graph it is currently viewing."""
        if context.active_graph_path is not None:
            current_entry = app.haystack.get_by_path(context.active_graph_path)
        elif context.active_graph is not None:
            # path=None covers both '__untitled__' and '__new_N__' — use identity
            current_entry = app.haystack.get_by_graph(context.active_graph)
        else:
            current_entry = None
        if current_entry is not None:
            app.haystack.session_detach(current_entry, session.session_id)

    def _activate_entry(self, entry: "GraphEntry", context: "SessionContext", session) -> None:
        """Fire ACTIVE_GRAPH_CHANGED and switch to the graph editor tab."""
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                source_editor="haystack",
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
        self._save_as_dialog = None
        self._save_base_dir = None
        self._save_base_dir_label = None
        self._save_path_input = None
        self._save_exists_warning = None
        self._save_as_entry = None
        self._save_as_context = None
        self._rename_dialog = None
        self._rename_input = None
        self._rename_error_label = None
        self._rename_entry = None
        self._rename_context = None
