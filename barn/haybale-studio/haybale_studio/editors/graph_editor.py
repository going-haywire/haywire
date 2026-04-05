# packages/haywire-app/src/haywire_studio/editors/graph_editor.py
"""
GraphEditor — wraps GraphCanvasManager as a BaseEditor.

Supports multiple open graphs via the GraphManager in haywire-app.
When an ACTIVE_GRAPH_CHANGED event arrives the canvas is swapped out for
the new graph's canvas without re-creating the outer shell.

A slim header inside the tab panel shows the open file name and a Save button.
"""

import logging

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.context_events import ContextChangeType, ContextChangedEvent

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.graph_canvas.graph_canvas_manager import GraphCanvasManager

logger = logging.getLogger(__name__)


@editor(
    registry_id="graph_editor",
    label="Graph Editor",
    icon="polyline",
    default_area="middle",
    description="Visual node graph editor for wiring data processing pipelines.",
)
class GraphEditor(BaseEditor):
    """
    The graph canvas editor.

    Wraps GraphCanvasManager inside a thin chrome that includes a header bar
    with the open file name and a Save button.

    Context changes consumed:
        ACTIVE_GRAPH_CHANGED — swap to a different graph / file.
        DATA_MUTATED         — sync canvas from another session.

    Context changes emitted:
        SELECTION_CHANGED    — node / edge selection.
        MODE_CHANGED         — interaction mode.
        DATA_MUTATED         — graph structure changes.

    The 'project_state' entry in context.metadata is set by haywire-app and
    must expose:
        .graph_manager          (GraphManager)  — preferred
        .editor                 (Editor)        — fallback for untitled graph
        .skin_factory           (SkinFactory)
        .node_factory           (NodeFactory)
    """

    def __init__(self):
        self._canvas_manager: Optional["GraphCanvasManager"] = None
        self._project_state = None
        self._context: Optional["SessionContext"] = None
        self._canvas_wrapper = None  # ui.element — cleared on graph switch
        self._graph_name_label = None  # ui.label in the header
        self._undo_button = None  # ui.button — undo
        self._redo_button = None  # ui.button — redo
        self._save_as_dialog = None  # ui.dialog — Save As
        self._save_base_dir: Optional[Path] = None  # fixed prefix (workspace root)
        self._save_base_dir_label = None  # ui.label showing the fixed prefix
        self._save_path_input = None  # ui.input — relative path / filename only
        self._save_exists_warning = None  # ui.label — "file already exists" warning

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, container, context: "SessionContext") -> None:
        self._context = context
        self._project_state = context.app
        if self._project_state is None:
            with container:
                ui.label("GraphEditor: no app in context").classes("hw-text-danger p-4")
            logger.warning("GraphEditor.render(): project_state not found in context.metadata")
            return

        with container:
            with ui.column().classes("w-full gap-0").style("height: 100%; overflow: hidden;"):
                # ---- slim header bar ----
                with (
                    ui.row()
                    .classes("w-full items-center px-3 gap-2 flex-shrink-0 border-b")
                    .style("min-height: 32px; background: var(--hw-bg-surface);")
                ):
                    ui.icon("polyline", size="14px").classes("hw-text-dim")
                    self._graph_name_label = ui.label("Untitled").classes(
                        "text-xs hw-text-muted truncate font-mono flex-1"
                    )
                    self._undo_button = (
                        ui.button(
                            icon="undo",
                            on_click=lambda: self._do_undo(context),
                        )
                        .props("flat round dense size=xs")
                        .tooltip("Undo")
                    )
                    self._redo_button = (
                        ui.button(
                            icon="redo",
                            on_click=lambda: self._do_redo(context),
                        )
                        .props("flat round dense size=xs")
                        .tooltip("Redo")
                    )
                    ui.button(
                        icon="save",
                        on_click=lambda: self._save_graph(context),
                    ).props("flat round dense size=xs").tooltip("Save (Ctrl+S)")
                    ui.button(
                        icon="drive_file_rename_outline",
                        on_click=lambda: self._save_as_graph(context),
                    ).props("flat round dense size=xs").tooltip("Save As…")

                # ---- canvas area (swapped on ACTIVE_GRAPH_CHANGED) ----
                self._canvas_wrapper = ui.element("div").style(
                    "flex: 1; width: 100%; overflow: hidden; min-height: 0; position: relative;"
                )
                with self._canvas_wrapper:
                    self._build_canvas(context)

            # ---- Save-As dialog (Quasar teleports it to <body>; slot doesn't matter) ----
            self._save_as_dialog = self._build_save_as_dialog(context)

        self._update_header(context)

    # ------------------------------------------------------------------
    # canvas build / swap
    # ------------------------------------------------------------------

    def _build_canvas(self, context: "SessionContext") -> None:
        """Instantiate a GraphCanvasManager inside _canvas_wrapper."""
        from haywire.ui.graph_canvas.graph_canvas_manager import GraphCanvasManager

        app = self._project_state
        entry = self._get_entry(context)

        if entry is None:
            # No graph is active — show a welcome/empty placeholder.
            with ui.column().classes("w-full h-full items-center justify-center gap-3"):
                ui.icon("polyline", size="48px").classes("hw-text-dim")
                ui.label("No graph open").classes("hw-text-muted text-sm")
                ui.label(
                    "Use the Graphs panel ( layers ) to create a new graph,\n"
                    "or open a .haywire file from the File Browser."
                ).classes("hw-text-dim text-xs text-center whitespace-pre-line")
            return

        self._canvas_manager = GraphCanvasManager(
            editor=entry.editor,
            skin_factory=app.skin_factory,
            node_factory=app.node_factory,
            panel_registry=app.panel_registry,
            session=context.session,
        )
        self._canvas_manager.sync_with_graph()

        # Center the viewport once the Vue component signals it is mounted
        # (first transform-changed event). fit_to_content for graphs with nodes;
        # center on canvas midpoint (3750, 3750) for empty graphs.
        zoom_container = self._canvas_manager.zoom_container
        has_nodes = len(entry.editor.graph.node_wrappers) > 0
        if has_nodes:
            zoom_container._on_ready = zoom_container.center_on_content
        else:
            zoom_container._on_ready = lambda: zoom_container.center_on(3750, 3750)

        logger.info(f"GraphEditor: canvas built for session {context.session_id[:8]}")

    def _get_entry(self, context: "SessionContext"):
        """Look up the active GraphEntry from the graph_manager, if available."""
        app = self._project_state
        if app is None or not hasattr(app, "graph_manager"):
            return None
        if context.active_graph_path is not None:
            return app.graph_manager.get_by_path(context.active_graph_path)
        # path is None — use graph-object identity for '__new_N__' entries.
        if context.active_graph is not None and hasattr(app.graph_manager, "get_by_graph"):
            return app.graph_manager.get_by_graph(context.active_graph)
        return None

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # header
    # ------------------------------------------------------------------

    def _update_header(self, context: "SessionContext") -> None:
        """Refresh the name label and undo/redo buttons to reflect the current graph."""
        if self._graph_name_label is None:
            return
        entry = self._get_entry(context)
        if entry is None:
            self._graph_name_label.text = "No graph"
            self._graph_name_label.classes(remove="hw-text-body hw-text-muted", add="hw-text-dim")
        elif context.active_graph_path is not None:
            name = Path(context.active_graph_path).name
            self._graph_name_label.text = ("● " if entry.unsaved else "") + name
            self._graph_name_label.classes(remove="hw-text-muted hw-text-dim", add="hw-text-body")
        else:
            # Unnamed / not-yet-saved graph
            self._graph_name_label.text = "● " + entry.display_name
            self._graph_name_label.classes(remove="hw-text-body hw-text-dim", add="hw-text-muted")
        self._update_undo_redo_buttons(entry)

    def _update_undo_redo_buttons(self, entry) -> None:
        """Enable/disable undo and redo buttons based on history state."""
        can_undo = entry is not None and entry.editor.can_undo()
        can_redo = entry is not None and entry.editor.can_redo()
        if self._undo_button is not None:
            self._undo_button.set_enabled(can_undo)
        if self._redo_button is not None:
            self._redo_button.set_enabled(can_redo)

    def _do_undo(self, context: "SessionContext") -> None:
        """Undo the last action on the active graph."""
        entry = self._get_entry(context)
        if entry is None or not entry.editor.can_undo():
            return
        entry.editor.undo()
        session = context.session
        if session is not None:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.DATA_MUTATED,
                    source_editor="graph_editor",
                )
            )

    def _do_redo(self, context: "SessionContext") -> None:
        """Redo the last undone action on the active graph."""
        entry = self._get_entry(context)
        if entry is None or not entry.editor.can_redo():
            return
        entry.editor.redo()
        session = context.session
        if session is not None:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.DATA_MUTATED,
                    source_editor="graph_editor",
                )
            )

    # ------------------------------------------------------------------
    # context changes
    # ------------------------------------------------------------------

    def on_context_changed(self, event: "ContextChangedEvent", context: "SessionContext") -> None:
        if event.change_type == ContextChangeType.ACTIVE_GRAPH_CHANGED:
            self._swap_canvas(context)
        elif event.change_type == ContextChangeType.DATA_MUTATED:
            self._update_header(context)

    def _swap_canvas(self, context: "SessionContext") -> None:
        """Tear down the old canvas and build a fresh one for the new graph."""
        if self._canvas_wrapper is None:
            return

        # Clear selection so PropertiesEditor resets to the graph panel
        context.active_node = None
        context.active_edge = None
        context.selected_nodes = set()
        context.selected_edges = set()
        session = context.session
        if session is not None:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.SELECTION_CHANGED,
                    source_editor="graph_editor",
                )
            )

        # Clean up existing canvas manager
        if self._canvas_manager:
            try:
                self._canvas_manager.cleanup()
            except Exception as exc:
                logger.warning(f"GraphEditor: cleanup error during swap: {exc}")
            self._canvas_manager = None

        self._canvas_wrapper.clear()
        with self._canvas_wrapper:
            self._build_canvas(context)

        self._update_header(context)

    # ------------------------------------------------------------------
    # save
    # ------------------------------------------------------------------

    def _default_save_dir(self, app) -> Path:
        """Return workspace_root/graphs/ if it exists, else workspace_root/."""
        root = Path(getattr(app, "workspace_root", str(Path.home())))
        graphs_dir = root / "graphs"
        return graphs_dir if graphs_dir.is_dir() else root

    def _save_graph(self, context: "SessionContext") -> None:
        """Save the active graph; opens Save-As dialog if no path exists yet."""
        app = context.app
        if app is None or not hasattr(app, "graph_manager"):
            ui.notify("Graph manager not available", type="warning")
            return

        entry = self._get_entry(context)
        if entry is None:
            ui.notify("No graph to save", type="warning")
            return

        if entry.path is not None:
            # Already has a path — just overwrite it
            success = app.graph_manager.save_graph(entry)
            if success:
                ui.notify(f"Saved: {entry.path.name}", type="positive", position="top-right")
                self._update_header(context)
                # Notify all sessions viewing this graph so GraphManagerEditor
                # and other headers clear their dirty indicators.
                if hasattr(app, "session_manager"):
                    try:
                        app.session_manager.broadcast_data_mutation(graph_path=entry.path)
                    except Exception:
                        pass
            else:
                ui.notify("Save failed", type="negative", position="top-right")
            return

        # No path yet — open the Save-As dialog
        self._open_save_as_dialog(app, entry)

    def _save_as_graph(self, context: "SessionContext") -> None:
        """Always open the Save-As dialog, regardless of whether a path exists."""
        app = context.app
        if app is None or not hasattr(app, "graph_manager"):
            ui.notify("Graph manager not available", type="warning")
            return
        entry = self._get_entry(context)
        if entry is None:
            ui.notify("No graph to save", type="warning")
            return
        self._open_save_as_dialog(app, entry)

    def _open_save_as_dialog(self, app, entry) -> None:
        """Pre-fill the Save-As dialog and open it."""
        if self._save_as_dialog is None or self._save_path_input is None:
            ui.notify("Save-As dialog not ready", type="warning")
            return

        workspace_root = Path(getattr(app, "workspace_root", str(Path.home())))
        self._save_base_dir = workspace_root

        # Show the fixed, non-editable workspace prefix in the label
        if self._save_base_dir_label is not None:
            self._save_base_dir_label.text = str(workspace_root).rstrip("/") + "/"

        # Editable portion: path relative to workspace_root
        if entry.path is not None:
            try:
                input_value = str(entry.path.relative_to(workspace_root))
            except ValueError:
                # File is outside the workspace — fall back to just the filename
                input_value = entry.path.name
        else:
            save_dir = self._default_save_dir(app)
            graph_name = getattr(entry.graph, "name", "untitled")
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
        """Create the Save-As dialog once during render(). Returns the dialog."""
        with ui.dialog() as dialog, ui.card().style("min-width: 460px; max-width: 640px"):
            with ui.column().classes("w-full gap-2"):
                ui.label("Save Graph As").classes("text-base font-semibold")

                # Read-only workspace prefix shown above the input
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

                # Editable filename / relative path within the workspace
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
                        on_click=lambda: self._do_save_as(context, dialog),
                    ).props("color=positive dense")
        return dialog

    def _clear_exists_warning(self) -> None:
        if self._save_exists_warning is not None:
            self._save_exists_warning.set_visibility(False)

    def _do_save_as(self, context: "SessionContext", dialog) -> None:
        """Execute the Save-As from within the dialog."""
        app = context.app
        if app is None:
            ui.notify("App not available", type="warning")
            return

        entry = self._get_entry(context)
        if entry is None:
            ui.notify("No graph to save", type="warning")
            dialog.close()
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

        # Warn if the file already exists and the user would be overwriting a
        # *different* graph (i.e. not the entry's own current path).
        if save_path.exists() and save_path != entry.path:
            if self._save_exists_warning is not None:
                self._save_exists_warning.text = (
                    f'"{save_path.name}" already exists — choose a different name.'
                )
                self._save_exists_warning.set_visibility(True)
            return  # stay in the dialog

        success = app.graph_manager.save_graph(entry, save_as=save_path)
        if success:
            context.active_graph_path = save_path
            session = context.session
            if session:
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                        source_editor="graph_editor",
                        detail=entry,
                    )
                )
            # Broadcast to all sessions so their GraphManagerEditor and header
            # also clear the dirty indicator.
            if hasattr(app, "session_manager"):
                try:
                    app.session_manager.broadcast_data_mutation(graph_path=save_path)
                except Exception:
                    pass
            ui.notify(f"Saved: {save_path.name}", type="positive", position="top-right")
            dialog.close()
        else:
            ui.notify("Save failed — check the path and try again", type="negative")

    # ------------------------------------------------------------------
    # cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        if self._canvas_manager:
            try:
                self._canvas_manager.cleanup()
            except Exception as exc:
                logger.error(f"GraphEditor.cleanup(): {exc}")
            self._canvas_manager = None
        self._save_as_dialog = None
        self._save_base_dir = None
        self._save_base_dir_label = None
        self._save_path_input = None
        self._save_exists_warning = None
