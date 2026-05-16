# barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py
"""
GraphEditor — wraps GraphCanvasManager as a BaseEditor.

Supports multiple open graphs via the shared :class:`GraphAppState`
registry. The source of those graphs (haystack, future cloud-graph
libraries) is opaque to this editor: each tab resolves its container
by ``binding_id`` and reads through the :class:`GraphContainer`
protocol.

When an ``ActiveGraphMoved`` signal arrives the canvas is swapped out for
the new graph's canvas without re-creating the outer shell.

A slim header inside the tab panel shows the open file name and a Save button.
"""

import logging

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.core.session.signals import ActiveGraphMoved, GraphDataMutated

from ..editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
from ..state.edit_state import EditState
from ..state.graph_app_state import GraphAppState
from ..protocols import GraphContainer  # noqa: F401  (used in type annotations)

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from nicegui.element import Element

logger = logging.getLogger(__name__)


@editor(
    label="Graph Editor",
    icon=hui.icon.graph,
    default_slot="main",
    opens="on_payload",
    description="Visual node graph editor for wiring data processing pipelines.",
)
class GraphEditor(BaseEditor):
    """
    The graph canvas editor.

    Wraps GraphCanvasManager inside a thin chrome that includes a header bar
    with the open file name and a Save button.

    Signals consumed:
        ``GraphDataMutated`` — sync canvas from another session.

    Signals emitted:
        ``ActiveGraphMoved`` — on tab focus, via on_focus().
        ``SelectionMoved``   — node / edge selection.
        ``GraphDataMutated`` — graph structure changes.

    The ``context.app`` object provided by haywire-app must expose:
        .skin_factory           (SkinFactory)
        .node_factory           (NodeFactory)
        .panel_registry         (PanelRegistry)
        .workspace_root         (str | Path)

    Open graphs are read from ``app_data[GraphAppState]`` — a registry
    populated by source libraries (haystack, future cloud-graph libs)
    whose internal structure this editor does not know about.
    """

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self._canvas_manager: Optional[GraphCanvasManager] = None
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
    # poll / draw
    # ------------------------------------------------------------------

    # No @redraw_on / @react_on subscriptions: each GraphEditor instance is
    # pinned to one graph via its wrapper.binding_id. ActiveGraphMoved means
    # "some tab became the foreground" — this instance's own graph hasn't
    # changed, so there is nothing to redraw. The canvas keeps its zoom/pan,
    # selection and DOM state across tab switches.

    def on_focus(self, context: "SessionContext") -> None:
        """Claim ownership of session state when this tab becomes active.

        Resolves ``self.wrapper._binding_id`` (the container key) via
        :class:`GraphAppState` and, if the container exists, updates
        ``context.data[EditState].active_graph`` + ``active_graph_path``
        and emits ``ActiveGraphMoved`` so panels (properties, minimap,
        execution controls) refresh.

        If the binding_id no longer resolves to a container (the graph was
        concurrently removed from the registry), calls
        ``self.wrapper.force_close()`` to close the orphaned tab.

        Short-circuits when the context already reflects this container
        so a redundant call is a no-op.
        """
        if self.wrapper._binding_id is None:
            return
        binding_id = self.wrapper._binding_id
        graph_app_state = context.app_data.get(GraphAppState)
        if graph_app_state is None:
            return

        entry = graph_app_state.get(binding_id)
        session = getattr(context, "session", None)
        if entry is None:
            # Container vanished from GraphAppState — close ourselves.
            # Programmatic close (no consent dialog needed; the user
            # already removed the underlying graph).
            self.wrapper.force_close()
            return

        edit_state = context.data[EditState]
        graph = entry.editor.graph
        if edit_state.active_graph is graph and edit_state.active_graph_path == entry.path:
            return

        edit_state.active_graph = graph
        edit_state.active_graph_path = entry.path

        if session is not None:
            session.publish(ActiveGraphMoved())

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._context = context
        self._project_state = context.app
        if self._project_state is None:
            with container:
                ui.label("GraphEditor: no app in context").classes("hw-text-danger p-4")
            logger.warning("GraphEditor.draw(): project_state not found in context.metadata")
            return

        # Clean up existing canvas manager before rebuilding
        if self._canvas_manager:
            try:
                self._canvas_manager.cleanup()
            except Exception as exc:
                logger.warning(f"GraphEditor: cleanup error during draw: {exc}")
            self._canvas_manager = None

        # Clear selection so PropertiesEditor resets to the graph panel
        edit_state = context.data[EditState]
        edit_state.active_node = None
        edit_state.active_edge = None
        edit_state.selected_nodes = set()
        edit_state.selected_edges = set()

        with container:
            with ui.column().classes("w-full gap-0").style("height: 100%; overflow: hidden;"):
                # ---- slim header bar ----
                with (
                    ui.row()
                    .classes("w-full items-center px-3 gap-2 flex-shrink-0 border-b")
                    .style("min-height: 32px; background: var(--hw-bg-surface);")
                ):
                    ui.icon(hui.icon.graph, size="14px").classes("hw-text-dim")
                    self._graph_name_label = ui.label("Untitled").classes(
                        "text-xs hw-text-muted truncate font-mono flex-1"
                    )
                    self._undo_button = hui.icon_action(
                        "undo", tooltip="Undo", on_click=lambda: self._do_undo(context)
                    )
                    self._redo_button = hui.icon_action(
                        "redo", tooltip="Redo", on_click=lambda: self._do_redo(context)
                    )
                    hui.icon_action(
                        "save", tooltip="Save (Ctrl+S)", on_click=lambda: self._save_graph(context)
                    )

                # ---- canvas area ----
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
        app = self._project_state
        entry = self._get_entry(context)

        if entry is None:
            # No graph is active — show a welcome/empty placeholder.
            hui.empty_state(
                "No graph open",
                icon=hui.icon.graph,
                hint=(
                    "Use the Graphs panel ( layers ) to create a new graph,\n"
                    "or open a .haywire file from the File Browser."
                ),
            )
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

    def _get_entry(self, context: "SessionContext") -> Optional["GraphContainer"]:
        """Look up this tab's GraphContainer from GraphAppState via binding_id.

        Each GraphEditor instance is bound to one ``(editor_key, binding_id)``
        pair — the binding_id is the ``GraphContainer.binding_id`` (a path
        string for saved graphs, a synthetic token for unsaved). The tab
        owns its graph identity; the session-level ``active_graph_path``
        is no longer consulted here.
        """
        if self.wrapper._binding_id is None:
            return None
        graph_app_state = context.app_data.get(GraphAppState)
        if graph_app_state is None:
            return None
        return graph_app_state.get(self.wrapper._binding_id)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # header
    # ------------------------------------------------------------------

    def _update_header(self, context: "SessionContext") -> None:
        """Refresh the name label and undo/redo buttons to reflect this tab's graph."""
        if self._graph_name_label is None:
            return
        entry = self._get_entry(context)
        if entry is None:
            self._graph_name_label.text = "No graph"
            self._graph_name_label.classes(remove="hw-text-body hw-text-muted", add="hw-text-dim")
        elif entry.path is not None:
            self._graph_name_label.text = ("● " if entry.unsaved else "") + self._workspace_rel(entry.path)
            self._graph_name_label.classes(remove="hw-text-muted hw-text-dim", add="hw-text-body")
        else:
            # Unnamed / not-yet-saved graph
            self._graph_name_label.text = "● not saved"
            self._graph_name_label.classes(remove="hw-text-body hw-text-dim", add="hw-text-muted")
        self._update_undo_redo_buttons(entry)
        self._sync_tab_dirty(entry)

    def _sync_tab_dirty(self, entry) -> None:
        """Mirror the entry's unsaved state to the tab bar via wrapper.set_dirty."""
        is_dirty = entry is not None and (entry.unsaved or entry.path is None)
        self.wrapper.set_dirty(is_dirty)
        slot = getattr(self.wrapper, "_slot", None)
        if slot is not None and hasattr(slot, "_refresh_bar"):
            try:
                slot._refresh_bar()
            except Exception:
                pass

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
            session.publish(GraphDataMutated())

    def _do_redo(self, context: "SessionContext") -> None:
        """Redo the last undone action on the active graph."""
        entry = self._get_entry(context)
        if entry is None or not entry.editor.can_redo():
            return
        entry.editor.redo()
        session = context.session
        if session is not None:
            session.publish(GraphDataMutated())

    # ------------------------------------------------------------------
    # save
    # ------------------------------------------------------------------

    def _default_save_dir(self, app) -> Path:
        """Return workspace_root/graphs/ if it exists, else workspace_root/."""
        root = Path(getattr(app, "workspace_root", str(Path.home())))
        graphs_dir = root / "graphs"
        return graphs_dir if graphs_dir.is_dir() else root

    def _workspace_rel(self, path: Path) -> str:
        """Return ``path`` relative to the project workspace_root, or its full
        path string when ``path`` lies outside the workspace.
        """
        app = self._project_state
        if app is not None:
            root = Path(getattr(app, "workspace_root", str(Path.home())))
            try:
                return str(path.relative_to(root))
            except ValueError:
                pass
        return str(path)

    def _save_graph(self, context: "SessionContext") -> None:
        """Save the active graph; opens Save-As dialog if no path exists yet."""
        entry = self._get_entry(context)
        if entry is None:
            ui.notify("No graph to save", type="warning")
            return

        if entry.path is not None:
            # Already has a path — call container.save().
            # save() returns None on no-rename; binding_id doesn't change
            # for an in-place save, so no repayload needed here. Failure
            # is signalled by `entry.unsaved` remaining True.
            entry.save()
            if not entry.unsaved:
                ui.notify(f"Saved: {entry.path.name}", type="positive", position="top-right")
                self._update_header(context)
                # Notify all sessions viewing this graph so peer editors
                # and headers clear their dirty indicators.
                session = context.session
                if session is not None:
                    session.publish(GraphDataMutated())
            else:
                ui.notify("Save failed", type="negative", position="top-right")
            return

        # No path yet — open the Save-As dialog
        app = context.app
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
            graph_name = getattr(entry.editor.graph, "name", "untitled")
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

        old_binding_id = self.wrapper._binding_id
        new_binding_id: Optional[str] = entry.save(save_as=save_path)
        if new_binding_id is not None or not entry.unsaved:
            context.data[EditState].active_graph_path = save_path
            session = context.session
            if new_binding_id is not None and old_binding_id != new_binding_id:
                # Save-as renamed the container — re-key the tab so the
                # wrapper's binding_id + label reflect the new file path.
                self.wrapper.repayload(new_binding_id, new_label=entry.display_name)
            if session:
                session.publish(ActiveGraphMoved())
                # Notify peer sessions so their HaystackEditor and header
                # also clear the dirty indicator.
                session.publish(GraphDataMutated())
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
