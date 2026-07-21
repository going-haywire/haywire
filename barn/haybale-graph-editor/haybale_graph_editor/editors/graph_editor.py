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
from haywire.ui.editor.identity import OpenBehavior, SlotName
from haywire.ui.editor.base import BaseEditor
from haywire.core.session.handlers import react_on
from haywire.core.session.signals import (
    ActiveGraphMoved,
    GraphDataMutated,
    Reveal,
    RevealGraphInstance,
    SelectionMoved,
)

from ..editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
from ..editors.graph_save_as import open_graph_save_as_dialog
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
    default_slot=SlotName.EDIT,
    opens=OpenBehavior.ON_PAYLOAD,
    description="Visual node graph editor for wiring data processing pipelines.",
)
class GraphEditor(BaseEditor):
    """
    The graph canvas editor.

    Wraps GraphCanvasManager inside a thin chrome that includes a header bar
    with the open file name and a Save button.

    Signals consumed:
        ``GraphDataMutated`` — sync canvas from another session.
        ``RevealGraphInstance`` — select a node/edge if this tab's graph matches.

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

    # ------------------------------------------------------------------
    # poll / draw
    # ------------------------------------------------------------------

    # No @redraw_on subscriptions: each GraphEditor instance is pinned to one
    # graph via its wrapper.binding_id. ActiveGraphMoved means "some tab became
    # the foreground" — this instance's own graph hasn't changed, so there is
    # nothing to redraw. The canvas keeps its zoom/pan, selection and DOM state
    # across tab switches, so we never want a full wrapper.redraw() here.
    #
    # GraphDataMutated, however, signals that *graph contents* changed (a node
    # added/moved/deleted, an edge wired) — possibly by an edit in this very
    # tab. The header chrome (dirty dot, tab dirty marker, undo/redo enablement)
    # is derived from entry.unsaved / editor.can_undo(), which only change on
    # such mutations. We react via @react_on (side-effect only, no redraw) to
    # refresh that chrome in place without disturbing the canvas DOM.

    @react_on(GraphDataMutated)
    def _on_graph_data_mutated(self, context: "SessionContext", event: GraphDataMutated) -> None:
        """Refresh header chrome when graph contents change.

        ``GraphDataMutated`` is cross-session and broadcast to every editor,
        including those whose graph did not change; ``_update_header`` simply
        re-reads *this* tab's own entry (``_get_entry``) and reflects its
        current dirty / undo state, so reacting unconditionally is correct and
        cheap. ``_update_header`` no-ops when the header hasn't been drawn yet.
        """
        self._recover_stale_binding_id(context)
        self._update_header(context)

    @react_on(RevealGraphInstance)
    def _on_reveal_graph_instance(self, context: "SessionContext", event: "RevealGraphInstance") -> None:
        """Self-check: is this tab's graph the one the signal is about?

        Compares event.graph_id against. Silent no-op if this isn't 
        the matching graph, or the specific node/edge inside it is gone 
        """
        if self._canvas_manager is None:
            return
        graph = self._canvas_manager.graph
        if graph.graph_id != event.graph_id:
            return

        edit_state = context.data[EditState]

        if event.node_id is not None:
            node_wrapper = graph.get_node_wrapper(event.node_id)
            if node_wrapper is None:
                return  # node gone
            edit_state.active_node = node_wrapper
        elif event.edge_id is not None:
            edge_wrapper = graph.edge_wrappers.get(event.edge_id)
            if edge_wrapper is None:
                return  # edge gone
            edit_state.active_edge = edge_wrapper
        else:
            return  # graph_id-only broadcast, nothing to select

        context.session.publish(
            Reveal(editor=GraphEditor, binding_id=self.wrapper._binding_id, label=graph.name)
        )
        context.session.publish(SelectionMoved())

    def _recover_stale_binding_id(self, context: "SessionContext") -> None:
        """Re-key this tab if its ``binding_id`` was rekeyed elsewhere.

        A save-as initiated from another editor (e.g. the HaystackEditor row
        save) rekeys the container in ``GraphAppState`` (``__unsaved_N__`` →
        file path) but cannot reach this tab's wrapper to follow. The result
        is that ``_get_entry`` resolves to None — the tab keeps its stale
        label and dirty marker. The graph object itself survives the rekey,
        so we recover the container by identity and repayload the tab.
        """
        if self._canvas_manager is None:
            return
        if self._get_entry(context) is not None:
            return  # binding_id still resolves — nothing to recover
        graph_app_state = context.app_data[GraphAppState]
        entry = graph_app_state.get_by_graph(self._canvas_manager.graph)
        if entry is None or entry.binding_id == self.wrapper._binding_id:
            return
        self.wrapper.repayload(entry.binding_id, new_label=entry.display_name)

    def on_focus(self, context: "SessionContext") -> None:
        """Claim ownership of session state when this tab becomes active.

        Resolves ``self.wrapper._binding_id`` (the container key) via
        :class:`GraphAppState` and updates ``context.data[EditState].active_graph``
        + ``active_graph_path`` and emits ``ActiveGraphMoved`` so panels
        (properties, minimap, execution controls) refresh.

        If the binding_id no longer resolves to a container (the graph was
        concurrently removed from the registry), calls
        ``self.wrapper.force_close()`` to close the orphaned tab.

        Short-circuits when the context already reflects this container
        so a redundant call is a no-op.
        """
        binding_id = self.wrapper._binding_id
        assert binding_id is not None
        graph_app_state = context.app_data[GraphAppState]
        entry = graph_app_state.get(binding_id)
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
        context.session.publish(ActiveGraphMoved())

        provider = self._canvas_manager._toolbar_provider if self._canvas_manager else None
        if provider and provider._last_bounds is not None:
            provider.show_at(provider._last_bounds)

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._context = context
        self._project_state = context.app

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
        context.active_component = None

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

        self._update_header(context)

    # ------------------------------------------------------------------
    # canvas build / swap
    # ------------------------------------------------------------------

    def _build_canvas(self, context: "SessionContext") -> None:
        """Instantiate a GraphCanvasManager inside _canvas_wrapper."""
        app = self._project_state
        entry = self._get_entry(context)
        assert entry is not None

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
        """Look up this tab's GraphContainer from GraphAppState via binding_id."""
        binding_id = self.wrapper._binding_id
        assert binding_id is not None
        graph_app_state = context.app_data[GraphAppState]
        return graph_app_state.get(binding_id)

    # ------------------------------------------------------------------
    # header
    # ------------------------------------------------------------------

    def _update_header(self, context: "SessionContext") -> None:
        """Refresh the name label and undo/redo buttons to reflect this tab's graph."""
        if self._graph_name_label is None:
            return
        entry = self._get_entry(context)
        if entry is None:
            self.wrapper.force_close()
            return
        if entry.path is not None:
            root = Path(self._project_state.workspace_root)
            try:
                rel = str(entry.path.relative_to(root))
            except ValueError:
                rel = str(entry.path)
            self._graph_name_label.text = ("● " if entry.unsaved else "") + rel
            self._graph_name_label.classes(remove="hw-text-muted hw-text-dim", add="hw-text-body")
        else:
            self._graph_name_label.text = "● not saved"
            self._graph_name_label.classes(remove="hw-text-body hw-text-dim", add="hw-text-muted")
        self._update_undo_redo_buttons(entry)
        self._sync_tab_dirty(entry)

    def _sync_tab_dirty(self, entry: "GraphContainer") -> None:
        """Mirror the entry's unsaved state to the tab bar via wrapper.set_dirty."""
        self.wrapper.set_dirty(entry.unsaved or entry.path is None, refresh=True)

    def _update_undo_redo_buttons(self, entry: "GraphContainer") -> None:
        """Enable/disable undo and redo buttons based on history state."""
        if self._undo_button is not None:
            self._undo_button.set_enabled(entry.editor.can_undo())
        if self._redo_button is not None:
            self._redo_button.set_enabled(entry.editor.can_redo())

    def _do_undo(self, context: "SessionContext") -> None:
        """Undo the last action on the active graph."""
        entry = self._get_entry(context)
        if entry is None or not entry.editor.can_undo():
            return
        entry.editor.undo()
        context.session.publish(GraphDataMutated())

    def _do_redo(self, context: "SessionContext") -> None:
        """Redo the last undone action on the active graph."""
        entry = self._get_entry(context)
        if entry is None or not entry.editor.can_redo():
            return
        entry.editor.redo()
        context.session.publish(GraphDataMutated())

    # ------------------------------------------------------------------
    # save
    # ------------------------------------------------------------------

    def _save_graph(self, context: "SessionContext") -> None:
        """Save the active graph; opens Save-As dialog if no path exists yet."""
        entry = self._get_entry(context)
        if entry is None:
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
                context.session.publish(GraphDataMutated())
            else:
                ui.notify("Save failed", type="negative", position="top-right")
            return

        # No path yet — open the Save-As dialog
        app = context.app

        def _save_fn(save_path: Path) -> bool:
            old_binding_id = self.wrapper._binding_id
            new_binding_id = entry.save(save_as=save_path)
            if new_binding_id is not None or not entry.unsaved:
                context.data[EditState].active_graph_path = save_path
                if new_binding_id is not None and old_binding_id != new_binding_id:
                    self.wrapper.repayload(new_binding_id, new_label=entry.display_name)
                context.session.publish(ActiveGraphMoved())
                context.session.publish(GraphDataMutated())
                return True
            return False

        open_graph_save_as_dialog(app=app, entry=entry, save_fn=_save_fn)

    def on_blur(self, context: "SessionContext") -> None:
        if self._canvas_manager and self._canvas_manager._toolbar_provider:
            self._canvas_manager._toolbar_provider.hide()

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
