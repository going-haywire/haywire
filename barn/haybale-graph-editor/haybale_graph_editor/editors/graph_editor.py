# barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py
"""
GraphEditor — wraps GraphCanvasManager as a BaseEditor.

Supports multiple open graphs via the shared :class:`GraphAppState`
registry. The source of those graphs (haystack, future cloud-graph
libraries) is opaque to this editor: each tab resolves its container
by ``binding_id`` and reads through the :class:`GraphContainer`
protocol.

One tab is one document, and one document is one editor: the Groups inside it
open as *levels* of that editor, each with its own canvas, on a tab row of its
own below the header. The editor owns them, so the file's undo history, its
dirty dot and Save span every level, and a level whose Subgraph is gone is
closed the moment it goes.

A slim header inside the tab panel shows the open file name and a Save button.
"""

import logging

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, cast

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import OpenBehavior, SlotName
from haywire.ui.editor.base import BaseEditor
from haywire.core.access import AccessTier
from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import react_on
from haywire.core.signals.keys import format_combo
from haywire.core.signals.signal import EditorCommand
from haywire.ui.components.zoom.pan import Viewport
from haywire.core.signals import (
    ActiveGraphMoved,
    Copy,
    Cut,
    Delete,
    Duplicate,
    Paste,
    Redo,
    SubgraphNavigation,
    GraphDataMutated,
    GraphUnsavedChanged,
    Reveal,
    RevealGraphInstance,
    SelectAll,
    SelectionMoved,
    ToggleLock,
    Undo,
)

from ..access import allows
from ..editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
from ..editors.graph_save_as import open_graph_save_as_dialog
from ..state.edit_state import EditState
from ..state.graph_app_state import GraphAppState
from ..protocols import GraphContainer, SubgraphContainer

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.subgraph import SubgraphDefinition
    from haywire.core.session.protocols import IAppState
    from nicegui.element import Element

logger = logging.getLogger(__name__)

# Node count at or above which the canvas mounts in the background
# instead of blocking the event loop.
CHUNKED_LOAD_THRESHOLD = 30

#: Level key of the document itself — the one level every editor always has.
DOCUMENT_LEVEL = "__document__"

#: Separator between the Subgraph keys that make up a level key.
_LEVEL_SEPARATOR = "#"


def level_key_for(container: "GraphContainer") -> str:
    """Return the level key ``container`` is shown under.

    The chain of Subgraph keys from the document down, so a Group nested in a
    Group is addressable and its descendants are recognisable by prefix.
    :data:`DOCUMENT_LEVEL` for a container that is not a Subgraph. Independent
    of ``binding_id``, so a save-as does not re-key the open levels.
    """
    keys: list[str] = []
    cursor: "GraphContainer" = container
    while isinstance(cursor, SubgraphContainer):
        keys.append(cursor.definition.key)
        cursor = cursor.host
    if not keys:
        return DOCUMENT_LEVEL
    return _LEVEL_SEPARATOR.join(reversed(keys))


#: Why a level inside a macro placement refuses to unlock (toast).
_PLACEMENT_REFUSAL = "Inside a macro placement this level stays locked. Use Edit Macro… to change the macro."

#: Lock-button tooltip on a level inside a macro placement.
_PLACEMENT_TOOLTIP = "Locked: inside a macro placement"


def inside_placement(container: "GraphContainer") -> bool:
    """Return whether ``container`` is a macro placement's interior, or nested in one.

    True for a :class:`SubgraphContainer` whose definition has a ``template_key``,
    or whose host chain contains one. ``False`` for a document and for a plain Group.
    """
    cursor: "GraphContainer" = container
    while isinstance(cursor, SubgraphContainer):
        if cursor.definition.template_key is not None:
            return True
        cursor = cursor.host
    return False


@dataclass
class _Level:
    """One graph open in this editor: the document, or a Group inside it."""

    key: str
    container: "GraphContainer"
    canvas_manager: Optional[GraphCanvasManager] = None
    panel: Optional["Element"] = field(default=None, repr=False)
    watched_props: Optional[Any] = field(default=None, repr=False)
    """The card's ``props`` bag this level's name is read from, while watched."""
    locked: bool = False
    """Whether this session's canvas for the level is locked; per session, per level."""
    inside_placement: bool = False
    """Whether the level is a macro placement's interior or nested in one; it cannot be unlocked."""


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
    with the open file name and a Save button, and a level bar listing the
    Groups open inside this document.

    Signals consumed:
        ``GraphDataMutated`` — sync canvas from another session.
        ``GraphUnsavedChanged`` — refresh the unsaved dot and tab marker.
        ``RevealGraphInstance`` — select a node/edge if one of this editor's
            levels holds that graph, opening the level if it is not open yet.
        ``SubgraphNavigation`` — open a Group of one of this editor's levels.
        ``SessionContext.target_binding_id`` — claim the session's graph state
            when a pointer-down lands in this editor.

    Signals emitted:
        ``ActiveGraphMoved`` — on tab focus, on a pointer-down in this editor and on level switch.
        ``SelectionMoved``   — node / edge selection.
        ``GraphDataMutated`` — graph structure changes.
        ``Reveal``           — this document's own tab, to bring it forward.

    The ``context.app`` object provided by haywire-app must expose:
        .skin_factory           (SkinFactory)
        .node_factory           (NodeFactory)
        .panel_registry         (PanelRegistry)
        .workspace_root         (str | Path)

    Open graphs are read from ``app_data[GraphAppState]`` — a registry
    populated by source libraries (haystack, future cloud-graph libs)
    whose internal structure this editor does not know about. The
    ``SubgraphContainer`` for a level never goes in there: it is this editor's
    own, for as long as the level is open.
    """

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self._levels: dict[str, _Level] = {}
        self._active_level: str = DOCUMENT_LEVEL
        self._project_state: Optional["IAppState"] = None
        self._context: Optional["SessionContext"] = None
        self._level_bar = None  # ui.row — one tab per open level
        self._level_panels = None  # ui.tab_panels — one canvas per open level
        self._graph_name_label = None  # ui.label in the header
        self._dirty_marker = None  # ui.label — the unsaved dot beside the path
        self._breadcrumb = None  # ui.row — where the active level sits in the tree
        self._undo_button = None  # ui.button — undo
        self._redo_button = None  # ui.button — redo
        self._lock_button = None  # ui.button — lock toggle
        self._lock_tooltip = None  # ui.tooltip — names the action a click on the lock takes

    # ------------------------------------------------------------------
    # levels
    # ------------------------------------------------------------------

    @property
    def _canvas_manager(self) -> Optional[GraphCanvasManager]:
        """The canvas of the level on screen, or ``None`` before the first draw."""
        level = self._levels.get(self._active_level)
        return level.canvas_manager if level is not None else None

    def _document(self) -> Optional["GraphContainer"]:
        """This editor's document container, or ``None`` before the first draw."""
        level = self._levels.get(DOCUMENT_LEVEL)
        return level.container if level is not None else None

    def _get_entry(self, context: "SessionContext") -> Optional["GraphContainer"]:
        """The container for the level on screen, or ``None`` before the first draw."""
        level = self._levels.get(self._active_level)
        return level.container if level is not None else None

    def _resolve_document(self, context: "SessionContext") -> Optional["GraphContainer"]:
        """Look this tab's document up in :class:`GraphAppState` by ``binding_id``."""
        binding_id = self.wrapper._binding_id
        if binding_id is None:
            return None
        return context.app_data[GraphAppState].get(binding_id)

    def _ensure_document_level(self, context: "SessionContext") -> Optional["GraphContainer"]:
        """Return the document container, opening the level for it on first sight.

        ``None`` when the document no longer resolves. Called before the tab is
        first drawn as well as after, because a slot activates a wrapper —
        ``on_focus`` — before it draws it.
        """
        document = self._resolve_document(context)
        if document is None:
            return None
        level = self._levels.get(DOCUMENT_LEVEL)
        if level is None:
            self._levels[DOCUMENT_LEVEL] = self._new_level(DOCUMENT_LEVEL, document)
        else:
            level.container = document
        return document

    def _descendant_keys(self, key: str) -> list[str]:
        """Every open level nested inside ``key``, deepest last."""
        prefix = f"{key}{_LEVEL_SEPARATOR}"
        return sorted(k for k in self._levels if k.startswith(prefix))

    def _parent_key(self, key: str) -> str:
        """The level key one step up from ``key``."""
        head, _, _tail = key.rpartition(_LEVEL_SEPARATOR)
        return head or DOCUMENT_LEVEL

    def _level_holding(self, graph_id: str) -> Optional[_Level]:
        """The open level whose graph is ``graph_id``, or ``None``."""
        for level in self._levels.values():
            if level.container.editor.graph.graph_id == graph_id:
                return level
        return None

    def _open_level(self, context: "SessionContext", container: "GraphContainer") -> str:
        """Open ``container`` as a level and switch to it; returns its level key.

        A level already open keeps the container it is open through — and with
        it its canvas, its viewport and its selection.
        """
        key = level_key_for(container)
        if key not in self._levels:
            level = self._new_level(key, container)
            self._levels[key] = level
            self._watch_level_name(level)
            if self._level_panels is not None:
                self._mount_level(context, level)
        self._switch_level(context, key)
        return key

    @staticmethod
    def _new_level(key: str, container: "GraphContainer") -> _Level:
        """Return a level for ``container``.

        Locked when the graph's ``open_locked`` is set, or always when the level is
        inside a macro placement.
        """
        inside = inside_placement(container)
        return _Level(
            key=key,
            container=container,
            locked=inside or container.editor.graph.props.open_locked,
            inside_placement=inside,
        )

    def set_level_locked(self, context: "SessionContext", key: str, locked: bool) -> bool:
        """Lock or unlock the level under ``key`` for this session.

        Returns ``False`` and changes nothing when ``key`` is not open, when
        unlocking a level inside a macro placement, or when unlocking without the
        real edit tier.
        """
        level = self._levels.get(key)
        if level is None:
            return False
        if not locked and level.inside_placement:
            return False
        if not locked and not context.can_edit():
            return False
        level.locked = locked
        if level.canvas_manager is not None:
            level.canvas_manager.set_locked(locked)
        if key == self._active_level:
            self._claim_session_state(context)
        return True

    def _watch_level_name(self, level: _Level) -> None:
        """Follow the card that names ``level``, so a rename reaches the tab at once.

        A Group is named by renaming its card, which is a settings write and
        raises no signal of its own. Idempotent, and re-binds when the card has
        been rebuilt under the level.
        """
        container = level.container
        if not isinstance(container, SubgraphContainer):
            return
        card = container.definition.graph_node_wrapper()
        props = card.node.props if card is not None else None
        if props is level.watched_props:
            return
        self._unwatch_level_name(level)
        if props is None:
            return
        try:
            props._subscribe_field("label", self._on_level_renamed)
        except Exception as exc:
            logger.warning(f"GraphEditor: could not watch the name of level '{level.key}': {exc}")
            return
        level.watched_props = props

    def _unwatch_level_name(self, level: _Level) -> None:
        """Stop following the card that names ``level``."""
        if level.watched_props is None:
            return
        try:
            level.watched_props._unsubscribe(self._on_level_renamed)
        except Exception as exc:
            logger.warning(f"GraphEditor: could not unwatch the name of level '{level.key}': {exc}")
        level.watched_props = None

    def _on_level_renamed(self, _value: object, _old: object) -> None:
        """Repaint the level bar and breadcrumb under the Group's new name."""
        context = self._context
        if context is None:
            return
        self._render_level_bar(context)
        self._update_breadcrumb(context)

    def _switch_level(self, context: "SessionContext", key: str, *, claim: bool = True) -> None:
        """Show the level under ``key`` and, when ``claim``, hand it the session's graph state.

        Showing another level empties the session's selection, which belongs to
        the level left behind (see ``_claim_session_state``). With ``claim``
        false the session's graph state and selection are left as they are.
        """
        if key not in self._levels:
            return
        if self._active_level != key:
            self._hide_toolbars()
        self._active_level = key
        if self._level_panels is not None:
            # The panel for `key` was not rendered while another level was
            # showing, so its canvas mounts from scratch here and asks for its
            # edges itself — see VisualLayerHandlers.process_canvas_mounted.
            self._level_panels.set_value(key)
        if claim:
            self._claim_session_state(context)
        self._render_level_bar(context)
        self._update_header(context)

    @staticmethod
    def _clear_selection(context: "SessionContext") -> None:
        """Empty the session's node and edge selection and publish ``SelectionMoved``."""
        edit_state = context.data[EditState]
        edit_state.active_node = None
        edit_state.active_edge = None
        edit_state.selected_nodes = set()
        edit_state.selected_edges = set()
        context.active_component = None
        context.session.publish(SelectionMoved())

    def _close_level(self, context: "SessionContext", key: str, *, claim: bool = True) -> None:
        """Close the level under ``key`` and every level nested inside it.

        The document level cannot be closed — it is the tab. Closing the level
        on screen shows its parent, claiming the session for it when ``claim``
        (see ``_switch_level``).
        """
        if key == DOCUMENT_LEVEL or key not in self._levels:
            return
        for doomed in [*reversed(self._descendant_keys(key)), key]:
            level = self._levels.pop(doomed, None)
            if level is None:
                continue
            self._teardown_level(level)
        if self._active_level not in self._levels:
            # The closed key stays active until the switch, which then leaves it and drops its selection.
            parent = self._parent_key(key)
            self._switch_level(context, parent if parent in self._levels else DOCUMENT_LEVEL, claim=claim)
        else:
            self._render_level_bar(context)

    def _prune_dead_levels(self, context: "SessionContext") -> None:
        """Close or re-point every level whose Subgraph is no longer in the graph above it.

        Expanding a Group, deleting its card, or undoing the collapse that made
        it all leave the level looking at a definition nothing references any
        more, and the level closes. A level inside a macro placement whose
        interior was replaced under the same key, as a macro reload does, is
        re-pointed at the new definition instead, and so is a Group nested in it
        whose key the new interior still holds.

        The session's graph state follows only when it is on this editor's level
        on screen; an editor the session is not on changes its own levels alone.
        """
        keys = [k for k in self._levels if k != DOCUMENT_LEVEL]
        if not keys:
            return
        # Read before any level changes: a re-point or close moves the level on screen.
        claim = self._holds_session(context)
        # Relies on `_levels` holding a parent before the levels nested in it: a
        # parent is re-pointed before its children are checked against it.
        for key in keys:
            level = self._levels.get(key)
            if level is None:
                continue  # already closed as a descendant of an earlier one
            container = level.container
            if not isinstance(container, SubgraphContainer):
                continue
            # The parent level's container, which a re-point earlier in this loop may have replaced.
            parent = self._levels.get(self._parent_key(key))
            host = parent.container if parent is not None else container.host
            current = host.editor.graph.get_subgraph(container.definition.key)
            if current is None or current.graph_node_wrapper() is None:
                self._close_level(context, key, claim=claim)
            elif current is container.definition and host.editor.graph is container.host.editor.graph:
                # The card may have been rebuilt under us; follow the new one.
                self._watch_level_name(level)
            elif level.inside_placement and self._project_state is not None:
                node_factory = self._project_state.node_factory
                repointed = SubgraphContainer(host, current, node_factory)
                self._repoint_level(context, level, repointed, claim=claim)
            else:
                self._close_level(context, key, claim=claim)

    def _repoint_level(
        self, context: "SessionContext", level: _Level, container: SubgraphContainer, *, claim: bool = True
    ) -> None:
        """Show ``container`` under ``level``'s key, with a new canvas, in place of ``level``.

        The new canvas keeps the old one's zoom and pan. A re-pointed level on
        screen claims the session for the new container when ``claim``.
        """
        replacement = self._new_level(level.key, container)
        viewport = level.canvas_manager.zoom_container.get_viewport() if level.canvas_manager else None
        self._teardown_level(level)
        self._levels[level.key] = replacement
        self._watch_level_name(replacement)
        if self._level_panels is not None:
            self._mount_level(context, replacement, viewport=viewport)
        if level.key == self._active_level:
            self._switch_level(context, level.key, claim=claim)
        else:
            self._render_level_bar(context)

    def _holds_session(self, context: "SessionContext") -> bool:
        """Return whether the session's graph state is on this editor's level on screen."""
        level = self._levels.get(self._active_level)
        return level is not None and context.data[EditState].active_graph is level.container.editor.graph

    # ------------------------------------------------------------------
    # poll / draw
    # ------------------------------------------------------------------

    # No @redraw_on subscriptions: each GraphEditor instance is pinned to one
    # document via its wrapper.binding_id. ActiveGraphMoved means "some tab
    # became the foreground" — this instance's own document hasn't changed, so
    # there is nothing to redraw. Every level's canvas keeps its zoom/pan,
    # selection and DOM state across tab and level switches, so we never want a
    # full wrapper.redraw() here.
    #
    # GraphDataMutated, however, signals that *graph contents* changed (a node
    # added/moved/deleted, an edge wired) — possibly by an edit in this very
    # tab. The header chrome (dirty dot, tab dirty marker, undo/redo
    # enablement) and the set of live levels are derived from that, so we react
    # via @react_on (side-effect only, no redraw) to refresh them in place
    # without disturbing any canvas DOM.

    @react_on(GraphDataMutated)
    def _on_graph_data_mutated(self, context: "SessionContext", event: GraphDataMutated) -> None:
        """Refresh the header and drop levels whose Subgraph is gone.

        ``GraphDataMutated`` is cross-session and broadcast to every editor,
        including those whose graph did not change; both steps re-read this
        editor's own state, so reacting unconditionally is correct and cheap.
        Both no-op when nothing has been drawn yet.
        """
        self._recover_stale_binding_id(context)
        self._prune_dead_levels(context)
        self._update_header(context)

    @react_on(GraphUnsavedChanged)
    def _on_graph_unsaved_changed(self, context: "SessionContext", event: GraphUnsavedChanged) -> None:
        """Refresh the header, whose unsaved dot and tab marker follow the document's unsaved state."""
        self._update_header(context)

    @react_on(SubgraphNavigation)
    def _on_subgraph_navigation(self, context: "SessionContext", event: "SubgraphNavigation") -> None:
        """Open the Subgraph on ``event.node_id`` as a level, when one of ours holds that graph.

        Self-check by ``graph_id``, like ``RevealGraphInstance``: the signal is
        broadcast to every editor in the session, and only the one holding that
        graph answers.
        """
        level = self._level_holding(event.graph_id)
        if level is None:
            return
        if level.key != self._active_level:
            self._switch_level(context, level.key)
        self.descend_into(context, event.node_id)

    @react_on(RevealGraphInstance)
    def _on_reveal_graph_instance(self, context: "SessionContext", event: "RevealGraphInstance") -> None:
        """Select a node/edge when this document holds the graph it names.

        The graph may be a Subgraph that is not open yet, in which case the
        levels down to it are opened first. Silent no-op when the graph is not
        in this document, or the node/edge inside it is gone.
        """
        level = self._level_holding(event.graph_id) or self._open_level_for_graph(context, event.graph_id)
        if level is None:
            return
        graph = level.container.editor.graph

        node_wrapper = edge_wrapper = None
        if event.node_id is not None:
            node_wrapper = graph.get_node_wrapper(event.node_id)
            if node_wrapper is None:
                return  # node gone
        elif event.edge_id is not None:
            edge_wrapper = graph.edge_wrappers.get(event.edge_id)
            if edge_wrapper is None:
                return  # edge gone
        else:
            return  # graph_id-only broadcast, nothing to select

        # Claim first: moving the session to this graph, from another level or
        # another tab, empties the selection, so the focus that follows keeps it.
        if level.key != self._active_level:
            self._switch_level(context, level.key)
        else:
            self._claim_session_state(context)
        edit_state = context.data[EditState]
        if node_wrapper is not None:
            edit_state.active_node = node_wrapper
        else:
            edit_state.active_edge = edge_wrapper
        document = self._document()
        context.session.publish(
            Reveal(
                editor=GraphEditor,
                binding_id=self.wrapper._binding_id,
                label=document.display_name if document is not None else graph.filestem,
            )
        )
        context.session.publish(SelectionMoved())

    # ------------------------------------------------------------------
    # keyboard commands (see EditorCommand)
    # ------------------------------------------------------------------

    @react_on(Copy)
    def _on_copy(self, context: "SessionContext", event: Copy) -> None:
        """Copy the selection on the level on screen."""
        if self._canvas_manager is not None:
            self._canvas_manager.copy_selection()

    @react_on(Cut)
    def _on_cut(self, context: "SessionContext", event: Cut) -> None:
        """Cut the selection on the level on screen."""
        if self._canvas_manager is not None:
            self._canvas_manager.cut_selection()

    @react_on(Duplicate)
    def _on_duplicate(self, context: "SessionContext", event: Duplicate) -> None:
        """Duplicate the selection on the level on screen."""
        if self._canvas_manager is not None:
            self._canvas_manager.duplicate_selection()

    @react_on(Paste)
    def _on_paste(self, context: "SessionContext", event: Paste) -> None:
        """Paste at the pointer on the level on screen; without a position, tell the user."""
        manager = self._canvas_manager
        if manager is None:
            return
        if event.position is None:
            ui.notify("Nothing to paste here", type="warning")
            return
        manager.paste(event.position, event.text)

    @react_on(Delete)
    def _on_delete(self, context: "SessionContext", event: Delete) -> None:
        """Delete the selection on the level on screen."""
        if self._canvas_manager is not None:
            self._canvas_manager.delete_selection()

    def accepts_command(self, context: "SessionContext", command: EditorCommand) -> bool:
        """Refuse commands the lock of the level on screen forbids; ``ToggleLock`` always passes."""
        if isinstance(command, ToggleLock):
            return True
        level = self._levels.get(self._active_level)
        locked = level.locked if level is not None else False
        return allows(context.can_access, locked, type(command).access)

    @react_on(ToggleLock)
    def _on_toggle_lock(self, context: "SessionContext", event: ToggleLock) -> None:
        """Flip the lock of the level on screen; unlocking needs the real edit tier."""
        level = self._levels.get(self._active_level)
        if level is None:
            return
        if self.set_level_locked(context, self._active_level, not level.locked):
            self._update_lock_button(context)
            document = self._document()
            if document is not None:
                self._update_undo_redo_buttons(document)
        else:
            message = _PLACEMENT_REFUSAL if level.inside_placement else "Unlocking needs edit access"
            ui.notify(message, type="warning")

    @react_on(Undo)
    def _on_undo(self, context: "SessionContext", event: Undo) -> None:
        """Undo the document's last action."""
        self._do_undo(context)

    @react_on(Redo)
    def _on_redo(self, context: "SessionContext", event: Redo) -> None:
        """Redo the document's last undone action."""
        self._do_redo(context)

    @react_on(SelectAll)
    def _on_select_all(self, context: "SessionContext", event: SelectAll) -> None:
        """Toggle select-all on the level on screen."""
        if self._canvas_manager is not None:
            self._canvas_manager.select_all_toggle()

    def _open_level_for_graph(self, context: "SessionContext", graph_id: str) -> Optional[_Level]:
        """Open the levels down to the Subgraph with ``graph_id``, or ``None`` if this
        document has no such Subgraph."""
        document = self._document()
        app = self._project_state
        if document is None or app is None:
            return None
        path = _definition_path(document.editor.graph, graph_id)
        if path is None:
            return None

        container: "GraphContainer" = document
        for definition in path:
            key = level_key_for(SubgraphContainer(container, definition, app.node_factory))
            open_already = self._levels.get(key)
            if open_already is not None:
                container = open_already.container
                continue
            container = SubgraphContainer(container, definition, app.node_factory)
            self._open_level(context, container)
        return self._levels.get(level_key_for(container))

    def _recover_stale_binding_id(self, context: "SessionContext") -> None:
        """Re-key this tab if its ``binding_id`` was rekeyed elsewhere.

        A save-as initiated from another editor (e.g. the HaystackEditor row
        save) rekeys the container in ``GraphAppState`` (``__unsaved_N__`` →
        file path) but cannot reach this tab's wrapper to follow. The result
        is that the document stops resolving — the tab keeps its stale label
        and dirty marker. The graph object itself survives the rekey, so we
        recover the container by identity and repayload the tab.
        """
        document = self._document()
        if document is None:
            return
        if self._resolve_document(context) is not None:
            return  # binding_id still resolves — nothing to recover
        graph_app_state = context.app_data[GraphAppState]
        entry = graph_app_state.get_by_graph(document.editor.graph)
        if entry is None or entry.binding_id == self.wrapper._binding_id:
            return
        self.wrapper.repayload(entry.binding_id, new_label=entry.display_name)

    def on_focus(self, context: "SessionContext") -> None:
        """Claim ownership of session state when this tab becomes active.

        Points ``context.data[EditState].active_graph`` at the level on screen
        and emits ``ActiveGraphMoved`` so panels (properties, minimap,
        execution controls) refresh. When that moves the session to another
        graph, the selection is emptied and ``SelectionMoved`` published first.

        If the ``binding_id`` no longer resolves to a container (the document
        was concurrently removed from the registry), calls
        ``self.wrapper.force_close()`` to close the orphaned tab.
        """
        if self._ensure_document_level(context) is None:
            # Document vanished from GraphAppState — close ourselves.
            # Programmatic close (no consent dialog needed; the user already
            # removed the underlying graph).
            self.wrapper.force_close()
            return
        self._claim_session_state(context)

    @react_on(SessionContext.target_binding_id)
    def _on_target_moved(self, context: "SessionContext", signal: object) -> None:
        """Claim the session for the level on screen when a pointer-down lands in this editor.

        Shown side by side with another graph editor, this one is already the
        focused tab of its slot, so ``on_focus`` does not run when the user turns
        to it. The pointer-down is reported before the canvas's own events, so
        the selection the click makes lands after the claim.
        """
        if context.target_binding_id == self.wrapper.editor_binding_id:
            self._claim_session_state(context)

    def _claim_session_state(self, context: "SessionContext") -> None:
        """Point the session's graph state at the level on screen.

        Moving the session to another graph, from another level or another tab,
        empties its selection, which names nodes of the graph left behind.
        Short-circuits when the context already reflects that level, so a
        redundant call is a no-op.
        """
        entry = self._get_entry(context)
        if entry is None:
            return

        edit_state = context.data[EditState]
        graph = entry.editor.graph
        locked = self._levels[self._active_level].locked
        if (
            edit_state.active_graph is graph
            and edit_state.active_graph_path == entry.path
            and edit_state.active_locked == locked
        ):
            return

        if edit_state.active_graph is not graph:
            # Before the graph moves, so nothing ever sees the new graph with a node of the old one.
            self._clear_selection(context)
        edit_state.active_graph = graph
        edit_state.active_graph_path = entry.path
        edit_state.active_locked = locked
        context.session.publish(ActiveGraphMoved())

        manager = self._canvas_manager
        provider = manager._toolbar_provider if manager else None
        if provider and provider._last_bounds is not None:
            provider.show_at(provider._last_bounds)

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._context = context
        self._project_state = context.app

        if self._ensure_document_level(context) is None:
            self.wrapper.force_close()
            return

        # Canvases are rebuilt into the new DOM; the levels themselves survive,
        # so a redraw comes back to the Groups that were open.
        for level in self._levels.values():
            self._teardown_canvas(level)
        if self._active_level not in self._levels:
            self._active_level = DOCUMENT_LEVEL

        # The rebuilt canvases select nothing, so neither does the session.
        self._clear_selection(context)

        with container:
            with ui.column().classes("w-full gap-0").style("height: 100%; overflow: hidden;"):
                # ---- slim header bar ----
                with (
                    ui.row()
                    .classes("w-full items-center px-3 gap-2 flex-shrink-0 border-b no-wrap")
                    .style("min-height: 32px; background: var(--hw-bg-surface);")
                ):
                    ui.icon(hui.icon.graph, size="14px").classes("hw-text-dim flex-shrink-0")
                    # The unsaved marker sits outside the label: the label
                    # truncates from the left, which would eat a leading mark
                    # before any of the path.
                    self._dirty_marker = ui.label("●").classes("text-xs flex-shrink-0")
                    self._dirty_marker.set_visibility(False)
                    # min-w-0 lets the path shrink below its text width; without
                    # it the label's automatic minimum keeps the row wider than
                    # the bar and the icon and actions are pushed onto their own
                    # lines. hw-elide-left puts the ellipsis at the start, so the
                    # filename stays visible and widening the pane reveals the
                    # path back towards the root.
                    self._graph_name_label = ui.label("Untitled").classes(
                        "text-xs hw-text-muted font-mono min-w-0 flex-1 hw-elide-left"
                    )
                    # Filled in by _update_breadcrumb when a Group is on screen;
                    # empty at the document level, so the header looks the same
                    # as it always did for an ordinary graph.
                    self._breadcrumb = ui.row().classes("items-center gap-1 min-w-0 no-wrap overflow-hidden")
                    self._lock_button = hui.icon_action(
                        hui.icon.unlocked,
                        on_click=lambda: context.session.publish(
                            ToggleLock(binding_id=self.wrapper.editor_binding_id)
                        ),
                    )
                    with self._lock_button:
                        self._lock_tooltip = ui.tooltip()
                    self._update_lock_button(context)
                    self._undo_button = hui.icon_action(
                        "undo", tooltip="Undo", on_click=lambda: self._do_undo(context), command=Undo
                    )
                    self._redo_button = hui.icon_action(
                        "redo", tooltip="Redo", on_click=lambda: self._do_redo(context), command=Redo
                    )
                    hui.icon_action(
                        "save", tooltip="Save (Ctrl+S)", on_click=lambda: self._save_graph(context)
                    )

                # ---- level bar ----
                # Below the header rather than above it, so the header separates
                # it from the tab row of the slot and the two never read as one.
                self._level_bar = (
                    ui.row()
                    .classes("w-full items-center gap-0 flex-shrink-0 px-2")
                    .style(
                        "min-height: 28px; background: var(--hw-bg-page); "
                        "border-bottom: 1px solid var(--hw-border);"
                    )
                )

                # ---- canvas area, one panel per level ----
                self._level_panels = (
                    ui.tab_panels(value=self._active_level, animated=False)
                    .props("keep-alive")
                    .style("flex: 1; width: 100%; min-height: 0; overflow: hidden;")
                )

        for level in self._levels.values():
            self._mount_level(context, level)

        self._render_level_bar(context)
        self._update_header(context)

    # ------------------------------------------------------------------
    # canvas build / teardown
    # ------------------------------------------------------------------

    def _mount_level(
        self, context: "SessionContext", level: _Level, viewport: Optional[Viewport] = None
    ) -> None:
        """Give ``level`` a panel in the level panels and build its canvas into it.

        The canvas opens on ``viewport``, or fitted to its content when ``None``.
        """
        if self._level_panels is None:
            return
        with self._level_panels:
            level.panel = ui.tab_panel(level.key).style("width: 100%; height: 100%; padding: 0;")
        with level.panel:
            canvas_area = ui.element("div").style(
                "flex: 1; width: 100%; height: 100%; overflow: hidden; min-height: 0; position: relative;"
            )
        with canvas_area:
            level.canvas_manager = self._build_canvas(context, level.container, viewport=viewport)
        if level.canvas_manager is not None:
            level.canvas_manager.set_locked(level.locked)

    def _build_canvas(
        self, context: "SessionContext", entry: "GraphContainer", viewport: Optional[Viewport] = None
    ) -> Optional[GraphCanvasManager]:
        """Instantiate a GraphCanvasManager over ``entry`` in the current slot, opened on ``viewport``."""
        app = self._project_state
        if app is None:
            return None

        manager = GraphCanvasManager(
            editor=entry.editor,
            skin_factory=app.skin_factory,
            node_factory=app.node_factory,
            panel_registry=app.panel_registry,
            session=context.session,
        )
        # Center the viewport once the Vue component signals it is mounted
        # (first transform-changed event). fit_to_content for graphs with nodes;
        # center on canvas midpoint (3750, 3750) for empty graphs.
        zoom_container = manager.zoom_container
        node_count = len(entry.editor.graph.node_wrappers)
        if viewport is not None:

            def restore_viewport() -> None:
                zoom_container.set_zoom(viewport.zoom)
                zoom_container.set_pan(viewport.pan_x, viewport.pan_y)

            zoom_container._on_ready = restore_viewport
            on_nodes_mounted = restore_viewport
        elif node_count:
            zoom_container._on_ready = zoom_container.center_on_content
            on_nodes_mounted = zoom_container.center_on_content
        else:
            zoom_container._on_ready = lambda: zoom_container.center_on(3750, 3750)
            on_nodes_mounted = zoom_container.center_on_content

        if node_count >= CHUNKED_LOAD_THRESHOLD:
            # Large graph: mount in the background so the server keeps serving
            # every other session while this one fills in.
            manager.start_chunked_sync(
                on_nodes_mounted=on_nodes_mounted,
                graph_name=entry.editor.graph.filestem,
            )
        else:
            manager.sync_with_graph()

        logger.info(f"GraphEditor: canvas built for session {context.session_id[:8]}")
        return manager

    def _teardown_canvas(self, level: _Level) -> None:
        """Release ``level``'s canvas, leaving the level itself in place."""
        if level.canvas_manager is None:
            return
        try:
            level.canvas_manager.cleanup()
        except Exception as exc:
            logger.warning(f"GraphEditor: canvas cleanup raised for level '{level.key}': {exc}")
        level.canvas_manager = None

    def _teardown_level(self, level: _Level) -> None:
        """Release ``level`` entirely — its name watch, its canvas and its panel."""
        self._unwatch_level_name(level)
        self._teardown_canvas(level)
        if level.panel is not None:
            try:
                level.panel.delete()
            except Exception as exc:
                logger.warning(f"GraphEditor: panel delete raised for level '{level.key}': {exc}")
            level.panel = None

    def _hide_toolbars(self) -> None:
        """Hide every level's floating selection toolbar."""
        for level in self._levels.values():
            manager = level.canvas_manager
            if manager and manager._toolbar_provider:
                manager._toolbar_provider.hide()

    # ------------------------------------------------------------------
    # descend / ascend
    # ------------------------------------------------------------------

    def descend_into(self, context: "SessionContext", card_node_id: str) -> bool:
        """Open the Group or macro placement on ``card_node_id`` as a level of this editor.

        ``card_node_id`` names a node of the level on screen. The Subgraph is
        opened as a :class:`SubgraphContainer` over that level's container, so
        Save, the dirty dot and the undo history keep reaching the host file at
        any depth. A placement's interior opens locked and stays locked.

        Returns:
            ``False`` when the node is not a Graph-node or placement with a Subgraph bound,
            or when there is no level to descend from.
        """
        entry = self._get_entry(context)
        app = self._project_state
        if entry is None or app is None:
            return False

        wrapper = entry.editor.graph.get_node_wrapper(card_node_id)
        if wrapper is None:
            return False

        resolve = getattr(wrapper.node, "resolve_definition", None)
        definition = resolve() if resolve is not None else None
        if definition is None:
            return False

        self._open_level(context, SubgraphContainer(entry, definition, app.node_factory))
        logger.info(f"GraphEditor: opened subgraph '{definition.key}'")
        return True

    def ascend(self, context: "SessionContext") -> bool:
        """Go back to the level holding the Group on screen.

        Returns:
            ``False`` when the document itself is on screen.
        """
        if self._active_level == DOCUMENT_LEVEL:
            return False
        self._switch_level(context, self._parent_key(self._active_level))
        return True

    def _descent_stack(self) -> list[_Level]:
        """The open levels from the document down to the one on screen."""
        stack: list[_Level] = []
        key = self._active_level
        while True:
            level = self._levels.get(key)
            if level is not None:
                stack.append(level)
            if key == DOCUMENT_LEVEL:
                break
            key = self._parent_key(key)
        stack.reverse()
        return stack

    # ------------------------------------------------------------------
    # level bar / breadcrumb
    # ------------------------------------------------------------------

    def _render_level_bar(self, context: "SessionContext") -> None:
        """Draw one tab per open level; hidden while only the document is open.

        Kept in the same visual language as the slot's tab row — the levels are
        tabs, and reading them as anything else would make a Group look like a
        document.
        """
        if self._level_bar is None:
            return
        self._level_bar.clear()
        self._level_bar.set_visibility(len(self._levels) > 1)
        if len(self._levels) < 2:
            return

        with self._level_bar:
            with (
                ui.tabs(
                    # A tab name, which is what q-tabs actually takes.
                    value=cast(Any, self._active_level),
                    on_change=lambda e: self._on_level_tab_clicked(context, e.value),
                )
                .props("dense align=left")
                .classes("hw-slot-bar-tabs")
                .style("flex: 1; min-height: 28px;")
            ):
                for level in self._levels.values():
                    with ui.tab(name=level.key, label="").props("no-caps"):
                        with ui.row().classes("items-center gap-1 no-wrap"):
                            icon = hui.icon.graph if level.key == DOCUMENT_LEVEL else hui.icon.subgraph
                            ui.icon(icon, size="12px")
                            ui.label(level.container.display_name).classes("text-xs")
                            if level.key != DOCUMENT_LEVEL:
                                (
                                    ui.button(
                                        icon=hui.icon.close,
                                        on_click=lambda _e, key=level.key: self._close_level(context, key),
                                    )
                                    .props("flat round dense size=xs")
                                    .classes("hw-tab-close -mr-1")
                                    .on("click.stop", lambda _e: None)
                                )

    def _on_level_tab_clicked(self, context: "SessionContext", key: str) -> None:
        """Switch to the clicked level, ignoring the echo of a programmatic change."""
        if not key or key == self._active_level:
            return
        self._switch_level(context, key)

    def _update_breadcrumb(self, context: "SessionContext") -> None:
        """Say where the level on screen sits in the tree; clicking a crumb goes there.

        Left empty while the document is on screen, so an ordinary graph's
        header is unchanged.
        """
        if self._breadcrumb is None:
            return
        self._breadcrumb.clear()

        stack = self._descent_stack()
        if len(stack) < 2:
            return

        with self._breadcrumb:
            for depth, level in enumerate(stack):
                if depth:
                    ui.icon("chevron_right", size="12px").classes("hw-text-dim")
                is_current = depth == len(stack) - 1
                label = ui.label(level.container.display_name).classes("text-xs truncate")
                if is_current:
                    label.classes(add="hw-text-body")
                    continue
                label.classes(add="hw-text-muted cursor-pointer hover:underline")
                # `key` is bound per crumb, not per loop variable — otherwise
                # every crumb would go to the last one.
                label.on("click", lambda _e, key=level.key: self._switch_level(context, key))

    # ------------------------------------------------------------------
    # header
    # ------------------------------------------------------------------

    def _set_dirty_marker(self, shown: bool) -> None:
        """Show or hide the unsaved dot in front of the path."""
        if self._dirty_marker is None:
            return
        self._dirty_marker.set_visibility(shown)

    def _update_header(self, context: "SessionContext") -> None:
        """Refresh the name label, undo/redo buttons and breadcrumb."""
        if self._graph_name_label is None:
            return
        document = self._document()
        if document is None or self._resolve_document(context) is None:
            self.wrapper.force_close()
            return
        if document.path is not None:
            app = self._project_state
            if app is None:
                return
            root = Path(app.workspace_root)
            try:
                rel = str(document.path.relative_to(root))
            except ValueError:
                rel = str(document.path)
            # The label is elided from the left, so the whole path is only ever
            # readable via the title attribute when the bar is narrow.
            self._graph_name_label.text = rel
            # Assigned rather than passed through props(): a quote in a
            # filename would break the "key=value" parsing.
            self._graph_name_label._props["title"] = rel
            self._graph_name_label.update()
            self._set_dirty_marker(document.unsaved)
            self._graph_name_label.classes(remove="hw-text-muted hw-text-dim", add="hw-text-body")
        else:
            self._graph_name_label.text = "not saved"
            self._graph_name_label._props.pop("title", None)
            self._graph_name_label.update()
            self._set_dirty_marker(True)
            self._graph_name_label.classes(remove="hw-text-body hw-text-dim", add="hw-text-muted")
        self._update_undo_redo_buttons(document)
        self._update_lock_button(context)
        self._sync_tab_dirty(document)
        self._update_breadcrumb(context)

    def _sync_tab_dirty(self, document: "GraphContainer") -> None:
        """Mirror the document's state to the tab bar.

        Two distinct facts, deliberately not merged: ``dirty`` means edited
        since the last write, ``unsaved`` means no file behind it at all.
        Both light the badge, but only ``unsaved`` decides whether the
        workspace snapshot can persist this binding.
        """
        self.wrapper.set_dirty(document.unsaved)
        self.wrapper.set_unsaved(document.path is None, refresh=True)

    def _update_undo_redo_buttons(self, document: "GraphContainer") -> None:
        """Enable/disable undo and redo buttons from the document's history."""
        editable = self._edit_allowed()
        if self._undo_button is not None:
            self._undo_button.set_enabled(editable and document.editor.can_undo())
        if self._redo_button is not None:
            self._redo_button.set_enabled(editable and document.editor.can_redo())

    def _edit_allowed(self) -> bool:
        """Return whether the canvas on screen allows editing, lock included."""
        manager = self._canvas_manager
        return True if manager is None else manager.allows(AccessTier.EDIT)

    def _update_lock_button(self, context: "SessionContext") -> None:
        """Show the lock icon of the level on screen, and the action a click takes; disabled below
        the real edit tier."""
        button = self._lock_button
        level = self._levels.get(self._active_level)
        if button is None or level is None:
            return
        button.props(f"icon={hui.icon.locked if level.locked else hui.icon.unlocked}")
        if self._lock_tooltip is not None:
            if level.inside_placement:
                self._lock_tooltip.set_text(_PLACEMENT_TOOLTIP)
            else:
                action = "Unlock" if level.locked else "Lock"
                combo = format_combo(ToggleLock.default_keys[0], mac=False)
                self._lock_tooltip.set_text(f"{action} ({combo})")
        button.set_enabled(context.can_edit() and not level.inside_placement)

    def _do_undo(self, context: "SessionContext") -> None:
        """Undo the last action anywhere in this document, including inside a Group."""
        document = self._document()
        if document is None or not self._edit_allowed() or not document.editor.can_undo():
            return
        document.editor.undo()
        context.session.publish(GraphDataMutated())

    def _do_redo(self, context: "SessionContext") -> None:
        """Redo the last undone action anywhere in this document."""
        document = self._document()
        if document is None or not self._edit_allowed() or not document.editor.can_redo():
            return
        document.editor.redo()
        context.session.publish(GraphDataMutated())

    # ------------------------------------------------------------------
    # save
    # ------------------------------------------------------------------

    def _save_graph(self, context: "SessionContext") -> None:
        """Save this document; opens Save-As dialog if no path exists yet.

        Saving is a document operation at every level — a Group is written as
        part of the file holding it.
        """
        entry = self._document()
        if entry is None:
            return
        if not context.can_edit():
            ui.notify("Saving needs edit access", type="warning", position="top-right")
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
                    # Re-keying the tab panel re-creates every canvas under it;
                    # each asks for its edges back as it mounts.
                    self.wrapper.repayload(new_binding_id, new_label=entry.display_name)
                context.session.publish(ActiveGraphMoved())
                context.session.publish(GraphDataMutated())
                return True
            return False

        open_graph_save_as_dialog(app=app, entry=entry, save_fn=_save_fn)

    def on_blur(self, context: "SessionContext") -> None:
        self._hide_toolbars()

    # ------------------------------------------------------------------
    # cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        for level in list(self._levels.values()):
            self._unwatch_level_name(level)
            self._teardown_canvas(level)
        self._levels.clear()


def _definition_path(graph: "BaseGraph", graph_id: str) -> Optional[list["SubgraphDefinition"]]:
    """The Subgraphs from ``graph`` down to the one whose graph is ``graph_id``.

    ``None`` when no Subgraph beneath ``graph`` has that id.
    """
    for definition in graph.subgraphs.values():
        if definition.graph_id == graph_id:
            return [definition]
        deeper = _definition_path(definition, graph_id)
        if deeper is not None:
            return [definition, *deeper]
    return None
