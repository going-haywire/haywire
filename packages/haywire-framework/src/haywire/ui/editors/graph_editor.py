# packages/haywire-framework/src/haywire/ui/editors/graph_editor.py
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


@editor(
    registry_id='graph_editor',
    label='Graph Editor',
    icon='account_tree',
    default_area='middle',
    description='Visual node graph editor for wiring data processing pipelines.',
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
        .node_render_factory    (RenderFactory)
        .node_factory           (NodeFactory)
    """

    def __init__(self):
        self._canvas_manager: Optional['GraphCanvasManager'] = None
        self._project_state = None
        self._canvas_wrapper = None      # ui.element — cleared on graph switch
        self._graph_name_label = None    # ui.label in the header
        self._save_as_dialog = None      # ui.dialog — Save As
        self._save_path_input = None     # ui.input inside the dialog
        self._save_exists_warning = None # ui.label — "file already exists" warning

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, container, context: 'SessionContext') -> None:
        self._project_state = context.metadata.get('project_state')
        if self._project_state is None:
            with container:
                ui.label('GraphEditor: no project_state in context.metadata').classes(
                    'text-red-400 p-4'
                )
            logging.warning("GraphEditor.render(): project_state not found in context.metadata")
            return

        with container:
            with ui.column().classes('w-full gap-0').style('height: 100%; overflow: hidden;'):
                # ---- slim header bar ----
                with ui.row().classes(
                    'w-full items-center px-3 gap-2 flex-shrink-0 border-b'
                ).style('min-height: 32px; background: #1a1a2e;'):
                    ui.icon('account_tree', size='14px').classes('text-gray-500')
                    self._graph_name_label = ui.label('Untitled').classes(
                        'text-xs text-gray-400 truncate font-mono flex-1'
                    )
                    ui.button(
                        icon='save',
                        on_click=lambda: self._save_graph(context),
                    ).props('flat round dense size=xs color=grey').tooltip('Save (Ctrl+S)')
                    ui.button(
                        icon='drive_file_rename_outline',
                        on_click=lambda: self._save_as_graph(context),
                    ).props('flat round dense size=xs color=grey').tooltip('Save As…')

                # ---- canvas area (swapped on ACTIVE_GRAPH_CHANGED) ----
                self._canvas_wrapper = ui.element('div').style(
                    'flex: 1; width: 100%; overflow: hidden; min-height: 0;'
                )
                with self._canvas_wrapper:
                    self._build_canvas(context)

            # ---- Save-As dialog (Quasar teleports it to <body>; slot doesn't matter) ----
            self._save_as_dialog = self._build_save_as_dialog(context)

        self._update_header(context)

    # ------------------------------------------------------------------
    # canvas build / swap
    # ------------------------------------------------------------------

    def _build_canvas(self, context: 'SessionContext') -> None:
        """Instantiate a GraphCanvasManager inside _canvas_wrapper."""
        from haywire.ui.graph_canvas.graph_canvas_manager import GraphCanvasManager

        app = self._project_state
        entry = self._get_entry(context)

        # Prefer the entry's editor; fall back to app.editor for untitled
        if entry is not None:
            graph_editor = entry.editor
        elif hasattr(app, 'editor'):
            graph_editor = app.editor
        else:
            ui.label('No graph loaded').classes('text-gray-500 p-4')
            return

        self._canvas_manager = GraphCanvasManager(
            editor=graph_editor,
            node_render_factory=app.node_render_factory,
            node_factory=app.node_factory,
            session_id=context.session_id[:8],
        )
        self._canvas_manager.sync_with_graph()
        logging.info(f"GraphEditor: canvas built for session {context.session_id[:8]}")

    def _get_entry(self, context: 'SessionContext'):
        """Look up the active GraphEntry from the graph_manager, if available."""
        app = self._project_state
        if app is None or not hasattr(app, 'graph_manager'):
            return None
        if context.active_graph_path is not None:
            return app.graph_manager.get_by_path(context.active_graph_path)
        # path is None — could be the '__untitled__' entry OR a '__new_N__' entry.
        # Use graph-object identity so we always return the right entry.
        if context.active_graph is not None and hasattr(app.graph_manager, 'get_by_graph'):
            return app.graph_manager.get_by_graph(context.active_graph)
        return app.graph_manager.get_untitled()

    # ------------------------------------------------------------------
    # header
    # ------------------------------------------------------------------

    def _update_header(self, context: 'SessionContext') -> None:
        """Refresh the name label to reflect the current graph."""
        if self._graph_name_label is None:
            return
        entry = self._get_entry(context)
        if context.active_graph_path is not None:
            name = Path(context.active_graph_path).name
            unsaved = entry.unsaved if entry else False
            self._graph_name_label.text = ('● ' if unsaved else '') + name
            self._graph_name_label.classes(remove='text-gray-400', add='text-gray-200')
        else:
            self._graph_name_label.text = 'Untitled'
            self._graph_name_label.classes(remove='text-gray-200', add='text-gray-400')

    # ------------------------------------------------------------------
    # context changes
    # ------------------------------------------------------------------

    def on_context_changed(
        self, event: 'ContextChangedEvent', context: 'SessionContext'
    ) -> None:
        if event.change_type == ContextChangeType.ACTIVE_GRAPH_CHANGED:
            self._swap_canvas(context)
        elif event.change_type == ContextChangeType.DATA_MUTATED:
            if self._canvas_manager:
                self._canvas_manager.sync_with_graph()

    def _swap_canvas(self, context: 'SessionContext') -> None:
        """Tear down the old canvas and build a fresh one for the new graph."""
        if self._canvas_wrapper is None:
            return

        # Clean up existing canvas manager
        if self._canvas_manager:
            try:
                self._canvas_manager.cleanup()
            except Exception as exc:
                logging.warning(f"GraphEditor: cleanup error during swap: {exc}")
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
        root = Path(getattr(app, 'workspace_root', str(Path.home())))
        graphs_dir = root / 'graphs'
        return graphs_dir if graphs_dir.is_dir() else root

    def _save_graph(self, context: 'SessionContext') -> None:
        """Save the active graph; opens Save-As dialog if no path exists yet."""
        app = context.metadata.get('project_state')
        if app is None or not hasattr(app, 'graph_manager'):
            ui.notify('Graph manager not available', type='warning')
            return

        entry = self._get_entry(context)
        if entry is None:
            ui.notify('No graph to save', type='warning')
            return

        if entry.path is not None:
            # Already has a path — just overwrite it
            success = app.graph_manager.save_graph(entry)
            if success:
                ui.notify(f'Saved: {entry.path.name}', type='positive', position='top-right')
                self._update_header(context)
            else:
                ui.notify('Save failed', type='negative', position='top-right')
            return

        # No path yet — open the Save-As dialog
        self._open_save_as_dialog(app, entry)

    def _save_as_graph(self, context: 'SessionContext') -> None:
        """Always open the Save-As dialog, regardless of whether a path exists."""
        app = context.metadata.get('project_state')
        if app is None or not hasattr(app, 'graph_manager'):
            ui.notify('Graph manager not available', type='warning')
            return
        entry = self._get_entry(context)
        if entry is None:
            ui.notify('No graph to save', type='warning')
            return
        self._open_save_as_dialog(app, entry)

    def _open_save_as_dialog(self, app, entry) -> None:
        """Pre-fill the Save-As dialog and open it."""
        if self._save_as_dialog is None or self._save_path_input is None:
            ui.notify('Save-As dialog not ready', type='warning')
            return
        if entry.path is not None:
            # Pre-fill with the current path so the user can rename/move easily
            self._save_path_input.value = str(entry.path)
        else:
            save_dir = self._default_save_dir(app)
            graph_name = getattr(entry.graph, 'name', 'untitled')
            safe_name = graph_name.lower().replace(' ', '_')
            self._save_path_input.value = str(save_dir / f'{safe_name}.haywire')
        if self._save_exists_warning is not None:
            self._save_exists_warning.set_visibility(False)
        self._save_as_dialog.open()

    def _build_save_as_dialog(self, context: 'SessionContext'):
        """Create the Save-As dialog once during render(). Returns the dialog."""
        with ui.dialog() as dialog, ui.card().style('min-width: 440px; max-width: 640px'):
            with ui.column().classes('w-full gap-3'):
                ui.label('Save Graph As').classes('text-base font-semibold')
                ui.label(
                    'Enter the full path for the .haywire file.'
                ).classes('text-xs text-gray-400 -mt-2')
                self._save_path_input = (
                    ui.input(label='File path')
                    .classes('w-full')
                    .props('outlined dense')
                    .on('update:model-value', lambda _: self._clear_exists_warning())
                )
                self._save_exists_warning = (
                    ui.label('')
                    .classes('text-xs text-red-400 -mt-1')
                )
                self._save_exists_warning.set_visibility(False)
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button('Cancel', on_click=dialog.close).props('flat dense')
                    ui.button(
                        'Save',
                        on_click=lambda: self._do_save_as(context, dialog),
                    ).props('color=primary dense')
        return dialog

    def _clear_exists_warning(self) -> None:
        if self._save_exists_warning is not None:
            self._save_exists_warning.set_visibility(False)

    def _do_save_as(self, context: 'SessionContext', dialog) -> None:
        """Execute the Save-As from within the dialog."""
        app = context.metadata.get('project_state')
        if app is None:
            ui.notify('App not available', type='warning')
            return

        entry = self._get_entry(context)
        if entry is None:
            ui.notify('No graph to save', type='warning')
            dialog.close()
            return

        path_str = (self._save_path_input.value or '').strip()
        if not path_str:
            ui.notify('Please enter a file path', type='warning')
            return

        save_path = Path(path_str)
        if not save_path.suffix:
            save_path = save_path.with_suffix('.haywire')

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
            session = context.metadata.get('haywire_session')
            if session:
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                        source_editor='graph_editor',
                        detail=entry,
                    )
                )
            ui.notify(f'Saved: {save_path.name}', type='positive', position='top-right')
            dialog.close()
        else:
            ui.notify('Save failed — check the path and try again', type='negative')

    # ------------------------------------------------------------------
    # cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        if self._canvas_manager:
            try:
                self._canvas_manager.cleanup()
            except Exception as exc:
                logging.error(f"GraphEditor.cleanup(): {exc}")
            self._canvas_manager = None
        self._save_as_dialog = None
        self._save_path_input = None
        self._save_exists_warning = None
