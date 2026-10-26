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
import uuid

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import OpenBehavior, SlotName
from haywire.ui.editor.base import BaseEditor
from haywire.ui.modals.confirm_modal import confirm_modal
from haywire.core.access import AccessTier, LevelMode
from haywire.core.node.layout import PATCH, STAGE
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
    Save,
    SelectAll,
    SelectionMoved,
    ToggleLock,
    ToggleStageView,
    Undo,
)

from haywire.core.graph.edit_route import EditRoute

from haybale_graph_editor.access import level_mode
from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
from haybale_graph_editor.editors.graph_save_as import open_graph_save_as_dialog
from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.state.graph_app_state import GraphAppState
from haybale_graph_editor.protocols import GraphContainer, SubgraphContainer

if TYPE_CHECKING:
    from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import SelectionToolbarProvider
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


#: The views a level can show, and the layout channel each draws.
VIEWS = {"patch": PATCH, "stage": STAGE}

#: Why a level inside a macro placement refuses to unlock (toast).
_PLACEMENT_REFUSAL = "Inside a macro placement this level stays locked. Use Edit Macro… to change the macro."

#: Lock-button tooltip on a level inside a macro placement.
_PLACEMENT_TOOLTIP = "Locked: inside a macro placement"

#: Lock-button tooltip on a macro placement's own level.
_EDIT_INSTANCE_TOOLTIP = "Unlock to edit this instance"


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


def placement_root(container: "GraphContainer") -> bool:
    """Return whether ``container`` is a macro placement's own interior.

    True for a :class:`SubgraphContainer` whose definition has a ``template_key``
    and whose host is not itself inside a placement. A Group nested in the
    interior is not a placement root.
    """
    return (
        isinstance(container, SubgraphContainer)
        and container.definition.template_key is not None
        and not inside_placement(container.host)
    )


@dataclass
class _Level:
    """One graph open in this editor: the document, or a Group inside it."""

    key: str
    container: "GraphContainer"
    view: str = "patch"
    """The view on screen: a key of ``VIEWS``."""
    canvases: dict[str, GraphCanvasManager] = field(default_factory=dict)
    """The canvas of each view mounted so far; the stage mounts on its first showing."""
    panel: Optional["Element"] = field(default=None, repr=False)
    view_panels: Optional[Any] = field(default=None, repr=False)
    """The keep-alive panels inside ``panel``, one per mounted view."""
    watched_props: Optional[Any] = field(default=None, repr=False)
    """The card's ``props`` bag this level's name is read from, while watched."""
    locked: bool = False
    """Whether this session's canvas for the level is locked; per session, per level."""
    inside_placement: bool = False
    """Whether the level is a macro placement's interior or nested in one; it cannot be unlocked."""
    panel_name: str = field(default_factory=lambda: uuid.uuid4().hex)
    """The name of the level's tab panel. Independent of ``key``: the client caches a panel by
    name, so a re-key must not rename it (a new name mounts a second canvas, and undo would
    revive the stale cached one)."""
    route: EditRoute = field(init=False, repr=False)
    """This session's edit route at the level; set by ``GraphEditor._new_level``."""

    @property
    def canvas_manager(self) -> Optional[GraphCanvasManager]:
        """The canvas of the view on screen, or ``None`` while it is not mounted."""
        return self.canvases.get(self.view)


@editor(
    label="Graph Editor",
    icon=hui.icon.graph,
    default_slot=SlotName.EDIT,
    opens=OpenBehavior.ON_PAYLOAD,
    description="Visual node graph editor for wiring data processing pipelines.",
    requires=AccessTier.VIEW,
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
        ``ActiveGraphMoved`` — on tab focus, on a pointer-down in this editor, on a
            pointer gesture on the canvas on screen and on level switch.
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
        self._save_button: Optional[ui.button] = None  # shown only while the document has unsaved edits
        self._breadcrumb = None  # ui.row — where the active level sits in the tree
        self._undo_button = None  # ui.button — undo
        self._redo_button = None  # ui.button — redo
        self._lock_button = None  # ui.button — lock toggle
        self._lock_tooltip = None  # ui.tooltip — names the action a click on the lock takes
        self._view_buttons: dict[str, Any] = {}  # ui.button per view — the Patch | Stage switch

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
            self._levels[DOCUMENT_LEVEL] = self._new_level(context, DOCUMENT_LEVEL, document)
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
            level = self._new_level(context, key, container)
            self._levels[key] = level
            self._watch_level_name(level)
            if self._level_panels is not None:
                self._mount_level(context, level)
        self._switch_level(context, key)
        return key

    def _new_level(self, context: "SessionContext", key: str, container: "GraphContainer") -> _Level:
        """Return a level for ``container``, with ``context``'s edit route at it.

        Locked when the graph's ``open_locked`` is set, or always when the level is
        inside a macro placement. Opens on the graph's ``open_view``. The route reads
        the level's container and lock at each call, so it follows a container swap
        and a lock toggle.
        """
        inside = inside_placement(container)
        props = container.editor.graph.props
        view = getattr(props, "open_view", "patch")
        level = _Level(
            key=key,
            container=container,
            view=view if view in VIEWS else "patch",
            locked=inside or props.open_locked,
            inside_placement=inside,
        )
        level.route = EditRoute(
            lambda: level.container.editor, lambda: level_mode(context.can_access, level.locked)
        )
        return level

    def set_level_locked(self, context: "SessionContext", key: str, locked: bool) -> bool:
        """Lock or unlock the level under ``key`` for this session; the selection stays.

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
        for canvas in level.canvases.values():
            canvas.refresh_mode()
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

    def _switch_view(
        self, context: "SessionContext", level_key: str, view: str, *, claim: bool = True
    ) -> None:
        """Show ``view`` of the level under ``level_key``, mounting its canvas on first sight.

        The canvas left empties its selection. When the level is on screen, the session's selection
        carries over to the canvas shown, pruned to what that canvas draws. Does nothing for an unknown
        level or view, or when ``view`` is already showing.
        """
        level = self._levels.get(level_key)
        if level is None or view not in VIEWS or view == level.view:
            return
        self._hide_toolbars()
        leaving = level.canvas_manager
        if leaving is not None:
            leaving.clear_selection()
        level.view = view
        if view not in level.canvases:
            self._mount_view(context, level, view)
        else:
            level.canvases[view].refresh_mode()
        if level.view_panels is not None:
            # A panel the client has not rendered yet mounts its canvas from scratch here and asks for its
            # edges itself, as a level does.
            level.view_panels.set_value(view)
        if level_key == self._active_level:
            shown = level.canvas_manager
            if shown is not None:
                shown.show_session_selection()
            if claim:
                self._claim_session_state(context)
        self._update_view_switch(level)

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
            # The panel for this level was not rendered while another level was
            # showing, so its canvas mounts from scratch here and asks for its
            # edges itself — see VisualLayerHandlers.process_canvas_mounted.
            self._level_panels.set_value(self._levels[key].panel_name)
        if claim:
            self._claim_session_state(context)
        self._render_level_bar(context)
        self._update_header(context)

    @staticmethod
    def _clear_selection(context: "SessionContext") -> None:
        """Empty the session's node and edge selection; publish ``SelectionMoved`` if it held anything."""
        edit_state = context.data[EditState]
        had_selection = bool(
            edit_state.active_node is not None
            or edit_state.active_edge is not None
            or edit_state.selected_nodes
            or edit_state.selected_edges
            or context.active_component is not None
        )
        edit_state.active_node = None
        edit_state.active_edge = None
        edit_state.selected_nodes = set()
        edit_state.selected_edges = set()
        context.active_component = None
        if had_selection:
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
        whose key the new interior still holds. A level whose definition moved to
        another key, as detaching a placement does, follows it there.

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
            if self._moved_to_another_key(host, level) and container.definition.graph_node_wrapper():
                self._rekey_level(context, level, claim=claim)
            elif current is None or current.graph_node_wrapper() is None:
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

        The replacement shows the view the old level showed. Each new canvas keeps the zoom and
        pan of the old canvas of its view. A re-pointed level on screen claims the session for
        the new container when ``claim``.
        """
        replacement = self._new_level(context, level.key, container)
        replacement.view = level.view
        viewports = self._viewports_of(level)
        self._teardown_level(level)
        self._levels[level.key] = replacement
        self._watch_level_name(replacement)
        if self._level_panels is not None:
            self._remount(context, replacement, viewports)
        if level.key == self._active_level:
            self._switch_level(context, level.key, claim=claim)
        else:
            self._render_level_bar(context)

    def _moved_to_another_key(self, host: "GraphContainer", level: _Level) -> bool:
        """Return whether ``level``'s definition is in ``host``'s Subgraphs under another key."""
        definition = cast(SubgraphContainer, level.container).definition
        own = level.key.rpartition(_LEVEL_SEPARATOR)[2]
        moved_to = next((k for k, d in host.editor.graph.subgraphs.items() if d is definition), None)
        return moved_to is not None and moved_to != own

    def _rekey_level(self, context: "SessionContext", level: _Level, *, claim: bool = True) -> None:
        """Move ``level`` and the levels nested in it to the keys their containers now have.

        The canvas, viewport and selection stay. A level inside a macro placement is
        locked; any other keeps its lock. The level on screen claims the session when ``claim``.
        """
        old_key = level.key
        renames = {old_key: level_key_for(level.container)}
        for key in self._descendant_keys(old_key):
            renames[key] = level_key_for(self._levels[key].container)
        # Rebuilt in order, so a parent still comes before the levels nested in it.
        rebuilt = {renames.get(k, k): v for k, v in self._levels.items()}
        if len(rebuilt) != len(self._levels):
            logger.warning(f"GraphEditor: re-keying {sorted(renames.items())} collided with an open level")
        self._levels = rebuilt
        for old, new in renames.items():
            moved = self._levels[new]
            moved.key = new
            moved.inside_placement = inside_placement(moved.container)
            if moved.inside_placement and not moved.locked:
                moved.locked = True
                for canvas in moved.canvases.values():
                    canvas.refresh_mode()
            self._watch_level_name(moved)
            if self._active_level == old:
                self._active_level = new
        if self._active_level in renames.values():
            self._switch_level(context, self._active_level, claim=claim)
        else:
            self._render_level_bar(context)

    def _holds_session(self, context: "SessionContext") -> bool:
        """Return whether the session's graph state is on this editor's level on screen."""
        entry = self._get_entry(context)
        return entry is not None and context.data[EditState].active_graph is entry.editor.graph

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

        Levels are pruned first: a navigation can arrive before the mutation
        signal that re-keys an open level (detaching a placement publishes one
        straight after the detach), and opening a second level for a Subgraph
        that is already open would orphan the first.

        With ``event.unlocked`` the entered level is unlocked afterwards, which
        ``set_level_locked`` grants only to a session that may edit.
        """
        self._prune_dead_levels(context)
        level = self._level_holding(event.graph_id)
        if level is None:
            return
        if level.key != self._active_level:
            self._switch_level(context, level.key)
        if (
            self.descend_into(context, event.node_id)
            and event.unlocked
            and self.set_level_locked(context, self._active_level, False)
        ):
            self._refresh_lock_buttons(context)

    @react_on(RevealGraphInstance)
    def _on_reveal_graph_instance(self, context: "SessionContext", event: "RevealGraphInstance") -> None:
        """Show the node/edge a reveal names, and select it.

        A revealed node is
        panned to the middle of its canvas; a canvas that is not on screen yet when the
        browser gets the request keeps its viewport. The graph may be
        a Subgraph that is not open yet, in which case the levels down to it are
        opened first. Silent no-op when the graph is not in this document, or the
        node/edge inside it is gone.
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
        canvas = level.canvas_manager
        if event.node_id is not None and canvas is not None:
            canvas.center_on_node(event.node_id)

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
        """Accept a command only in level mode ``EDIT``; the two toggles, Select All and Save always pass.

        Save passes at every level mode; ``_save_graph`` refuses it without edit access.
        """
        if isinstance(command, (ToggleLock, ToggleStageView, SelectAll, Save)):
            return True
        return self._level_mode() is LevelMode.EDIT

    @react_on(ToggleStageView)
    def _on_toggle_stage_view(self, context: "SessionContext", event: ToggleStageView) -> None:
        """Switch the level on screen between its patch and its stage."""
        level = self._levels.get(self._active_level)
        if level is None:
            return
        self._switch_view(context, self._active_level, "patch" if level.view == "stage" else "stage")

    @react_on(ToggleLock)
    def _on_toggle_lock(self, context: "SessionContext", event: ToggleLock) -> None:
        """Flip the lock of the level on screen; unlocking needs the real edit tier.

        Unlocking a macro placement's own level asks first, then detaches the
        placement into a Group (see ``_edit_instance``). A level deeper inside a
        placement refuses.
        """
        level = self._levels.get(self._active_level)
        if level is None:
            return
        if level.locked and placement_root(level.container):
            if not context.can_edit():
                ui.notify("Unlocking needs edit access", type="warning")
                return

            from haywire.core.macro.source import origin_label

            label = origin_label(cast(SubgraphContainer, level.container).definition)

            def confirmed() -> None:
                self._edit_instance(context, level)

            confirm_modal(
                title="Edit Instance",
                message=(
                    f"Edit this instance? It becomes a modified instance of "
                    f"{label} until you Update or Revert."
                ),
                confirm_label="Edit Instance",
                on_confirm=confirmed,
            )
            return
        if self.set_level_locked(context, self._active_level, not level.locked):
            self._refresh_lock_buttons(context)
        else:
            message = _PLACEMENT_REFUSAL if level.inside_placement else "Unlocking needs edit access"
            ui.notify(message, type="warning")

    def _refresh_lock_buttons(self, context: "SessionContext") -> None:
        """Redraw the buttons that follow the lock of the level on screen: Lock, Undo and Redo."""
        self._update_lock_button(context)
        document = self._document()
        if document is not None:
            self._update_undo_redo_buttons(document)

    def _edit_instance(self, context: "SessionContext", level: _Level) -> bool:
        """Detach the placement on ``level`` into a Group and unlock its level.

        The Group carries the placement's origin. The level follows its Subgraph
        to the new key and opens unlocked. Checks the edit tier itself, so a
        caller without edit access changes nothing.

        Returns:
            ``False`` when nothing changed: no edit access, not a placement
            root, the card or the Graph-node class is missing, or the detach
            was refused.
        """
        if not context.can_edit():
            return False
        container = level.container
        if not placement_root(container) or self._project_state is None:
            return False
        container = cast(SubgraphContainer, container)
        card = container.definition.graph_node_wrapper()
        card_cls = self._project_state.node_factory.get_graph_node()
        if card is None or card_cls is None:
            return False
        card_id, refusal = container.host.editor.detach_placement_from_macro(
            card.node_id, card_cls.class_identity.registry_key
        )
        if card_id is None:
            ui.notify(refusal or "Could not edit this instance", type="warning", multi_line=True)
            return False
        # The detach has moved the Subgraph but its mutation signal has not arrived
        # yet, so re-key the level now; the signal published below finds it done.
        self._prune_dead_levels(context)
        unlocked = self.set_level_locked(context, level_key_for(container), False)
        self._update_lock_button(context)
        context.session.publish(GraphDataMutated())
        return unlocked

    @react_on(Save)
    def _on_save(self, context: "SessionContext", event: Save) -> None:
        """Save the document."""
        self._save_graph(context)

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
        """Open the levels down to the Subgraph with ``graph_id``.

        Returns ``None`` and opens nothing when this document has no such Subgraph,
        or when the document level is in level mode ``VIEW``.
        """
        document = self._document()
        app = self._project_state
        if document is None or app is None:
            return None
        document_level = self._levels.get(DOCUMENT_LEVEL)
        if document_level is None or document_level.route.mode() is LevelMode.VIEW:
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
        """Claim the session for the level on screen when the session's target moves to this editor."""
        # The pointer-down that moves the target arrives before the canvas events of the same click.
        if context.target_binding_id == self.wrapper.editor_binding_id:
            self._claim_session_state(context)

    def _on_canvas_gesture(self, context: "SessionContext", manager: GraphCanvasManager) -> None:
        """Claim the session for the level on screen when ``manager`` is its canvas; otherwise do nothing."""
        level = self._levels.get(self._active_level)
        if level is not None and level.canvas_manager is manager:
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
        level = self._levels[self._active_level]
        mode = level.route.mode()
        if (
            edit_state.active_graph is graph
            and edit_state.active_graph_path == entry.path
            and context.level_mode is mode
            and edit_state.active_route is level.route
        ):
            return

        if edit_state.active_graph is not graph:
            # Before the graph moves, so nothing ever sees the new graph with a node of the old one.
            self._clear_selection(context)
        edit_state.active_graph = graph
        edit_state.active_graph_path = entry.path
        context.level_mode = mode
        edit_state.active_route = level.route
        context.session.publish(ActiveGraphMoved())

        provider = self._toolbar_provider()
        if provider and provider._last_bounds is not None:
            provider.show_at(provider._last_bounds)

    def _toolbar_provider(self) -> "SelectionToolbarProvider | None":
        """Return the selection toolbar provider of the canvas on screen, if any."""
        manager = self._canvas_manager
        return manager._toolbar_provider if manager else None

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._context = context
        self._project_state = context.app

        if self._ensure_document_level(context) is None:
            self.wrapper.force_close()
            return

        # Canvases are rebuilt into the new DOM; the levels themselves survive,
        # so a redraw comes back to the Groups that were open, each view at its viewport.
        kept_viewports = self._teardown_canvases_keeping_viewports()
        if self._active_level not in self._levels:
            self._active_level = DOCUMENT_LEVEL

        # The rebuilt canvases select nothing, so neither does the session when it is on them.
        if self._holds_session(context):
            self._clear_selection(context)

        with container:
            with ui.column().classes("w-full gap-0").style("height: 100%; overflow: hidden;"):
                # ---- slim header bar ----
                with hui.editor_toolbar() as toolbar:
                    toolbar.classes("no-wrap")
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
                    self._draw_view_switch(context)
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
                    self._save_button = hui.icon_action(
                        "save", tooltip="Save", on_click=lambda: self._save_graph(context), command=Save
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
                    ui.tab_panels(value=self._levels[self._active_level].panel_name, animated=False)
                    .props("keep-alive")
                    .style("flex: 1; width: 100%; min-height: 0; overflow: hidden;")
                )

        self._mount_levels(context, kept_viewports)

        self._render_level_bar(context)
        self._update_header(context)

    # ------------------------------------------------------------------
    # canvas build / teardown
    # ------------------------------------------------------------------

    @staticmethod
    def _viewports_of(level: _Level) -> dict[str, Viewport]:
        """The viewport of each view ``level`` has mounted, by view; a view with none yet is left out."""
        viewports: dict[str, Viewport] = {}
        for view, canvas in level.canvases.items():
            viewport = canvas.zoom_container.get_viewport()
            if viewport is not None:
                viewports[view] = viewport
        return viewports

    def _teardown_canvases_keeping_viewports(self) -> dict[str, dict[str, Viewport]]:
        """Release every level's canvases; return each mounted view's viewport, by level key then view."""
        kept: dict[str, dict[str, Viewport]] = {}
        for key, level in self._levels.items():
            kept[key] = self._viewports_of(level)
            self._teardown_canvas(level)
        return kept

    def _mount_levels(self, context: "SessionContext", kept: dict[str, dict[str, Viewport]]) -> None:
        """Mount every level, each view it had mounted at its kept viewport (see ``_remount``)."""
        for key, level in self._levels.items():
            self._remount(context, level, kept.get(key, {}))

    def _remount(self, context: "SessionContext", level: _Level, viewports: dict[str, Viewport]) -> None:
        """Mount ``level``: its view on screen at its viewport (fitted without one), and every other
        view in ``viewports`` at its own. A view never mounted before stays lazy."""
        self._mount_level(context, level, viewport=viewports.get(level.view))
        for view, viewport in viewports.items():
            if view != level.view:
                self._mount_view(context, level, view, viewport=viewport)

    def _mount_level(
        self, context: "SessionContext", level: _Level, viewport: Optional[Viewport] = None
    ) -> None:
        """Give ``level`` a panel in the level panels and build its canvas into it.

        The level's panel holds a keep-alive container with one panel per view; only the view on
        screen is built here (see ``_mount_view``). The canvas opens on ``viewport``, or fitted to
        its content when ``None``.
        """
        if self._level_panels is None:
            return
        with self._level_panels:
            level.panel = ui.tab_panel(level.panel_name).style("width: 100%; height: 100%; padding: 0;")
        with level.panel:
            level.view_panels = (
                ui.tab_panels(value=level.view, animated=False)
                .props("keep-alive")
                .style("width: 100%; height: 100%; overflow: hidden;")
            )
        self._mount_view(context, level, level.view, viewport=viewport)

    def _mount_view(
        self, context: "SessionContext", level: _Level, view: str, viewport: Optional[Viewport] = None
    ) -> None:
        """Build ``view``'s canvas into a panel of ``level``'s keep-alive container.

        The first canvas a level mounts reports the load's compatibility summary; later ones do not.
        """
        if level.view_panels is None:
            return
        reports = not level.canvases
        with level.view_panels:
            panel = ui.tab_panel(view).style("width: 100%; height: 100%; padding: 0;")
        with panel:
            canvas_area = ui.element("div").style(
                "flex: 1; width: 100%; height: 100%; overflow: hidden; min-height: 0; position: relative;"
            )
        with canvas_area:
            manager = self._build_canvas(
                context,
                level.route,
                viewport=viewport,
                view=view,
                reports_compatibility=reports,
                patch_viewport_centre=lambda: self._patch_viewport_centre(level),
            )
        if manager is not None:
            level.canvases[view] = manager

    @staticmethod
    def _patch_viewport_centre(level: _Level) -> Optional[tuple[float, float]]:
        """Where ``level``'s patch canvas is looking, or ``None`` while it is not mounted.

        A stage canvas asks this to place a node made on an empty stage. The patch canvas stays
        mounted (keep-alive) while the stage shows, so its last-known viewport is current.
        """
        patch_canvas = level.canvases.get("patch")
        return patch_canvas.viewport_centre() if patch_canvas is not None else None

    def _build_canvas(
        self,
        context: "SessionContext",
        route: EditRoute,
        viewport: Optional[Viewport] = None,
        view: str = "patch",
        reports_compatibility: Optional[bool] = None,
        patch_viewport_centre: Optional[Callable[[], Optional[tuple[float, float]]]] = None,
    ) -> Optional[GraphCanvasManager]:
        """Instantiate a GraphCanvasManager over ``route``'s graph in the current slot, at ``viewport``.

        ``view`` picks the layout channel the canvas draws. ``reports_compatibility`` overrides
        whether it reports the load's compatibility summary; ``None`` leaves that to the patch.
        """
        app = self._project_state
        if app is None:
            return None

        channel = VIEWS[view]
        manager = GraphCanvasManager(
            route=route,
            skin_factory=app.skin_factory,
            node_factory=app.node_factory,
            panel_registry=app.panel_registry,
            session=context.session,
            on_user_event=lambda: self._on_canvas_gesture(context, manager),
            channel=channel,
            patch_viewport_centre=patch_viewport_centre,
        )
        if reports_compatibility is not None:
            manager.visual_layer.reports_compatibility = reports_compatibility
        # Center the viewport once the Vue component signals it is mounted
        # (first transform-changed event). fit_to_content for graphs with nodes;
        # center on canvas midpoint (3750, 3750) for empty graphs, and on the stage
        # origin corner for an empty stage.
        zoom_container = manager.zoom_container
        if channel.stage:
            node_count = manager.visual_layer.included_node_count()
        else:
            node_count = len(route.graph.node_wrappers)
        if viewport is not None:

            def restore_viewport() -> None:
                zoom_container.set_zoom(viewport.zoom)
                zoom_container.set_pan(viewport.pan_x, viewport.pan_y)

            zoom_container._on_ready = restore_viewport
            on_nodes_mounted = restore_viewport
        elif node_count:
            zoom_container._on_ready = zoom_container.center_on_content
            on_nodes_mounted = zoom_container.center_on_content
            # A chunked load mounts its cards in chunks; fit their saved positions now so each lands in view.
            bounds = manager.visual_layer.content_bounds() if node_count >= CHUNKED_LOAD_THRESHOLD else None
            if bounds is not None:
                zoom_container._on_ready = lambda: zoom_container.fit_to_rect(*bounds)
        elif channel.stage:
            stage_corner = (channel.origin + 400, channel.origin + 300)
            zoom_container._on_ready = lambda: zoom_container.center_on(*stage_corner)
            on_nodes_mounted = zoom_container.center_on_content
        else:
            zoom_container._on_ready = lambda: zoom_container.center_on(3750, 3750)
            on_nodes_mounted = zoom_container.center_on_content

        if node_count >= CHUNKED_LOAD_THRESHOLD:
            # Large graph: mount in the background so the server keeps serving
            # every other session while this one fills in.
            manager.start_chunked_sync(
                on_nodes_mounted=on_nodes_mounted,
                graph_name=route.graph.filestem,
            )
        else:
            manager.sync_with_graph()

        logger.info(f"GraphEditor: canvas built for session {context.session_id[:8]}")
        return manager

    def _teardown_canvas(self, level: _Level) -> None:
        """Release every canvas of ``level``, leaving the level itself in place."""
        for view, canvas in level.canvases.items():
            try:
                canvas.cleanup()
            except Exception as exc:
                logger.warning(f"GraphEditor: {view} canvas cleanup raised for level '{level.key}': {exc}")
        level.canvases.clear()
        level.view_panels = None

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
        """Hide the floating selection toolbar of every canvas of every level."""
        for level in self._levels.values():
            for manager in level.canvases.values():
                if manager._toolbar_provider:
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
            when there is no level to descend from, or when the level on screen is in
            level mode ``VIEW``.
        """
        if self._level_mode() is LevelMode.VIEW:
            return False
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
                            ui.icon(self._level_icon(level), size="12px")
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

    @staticmethod
    def _level_icon(level: _Level) -> str:
        """Return the icon of a level's tab: the document, a macro placement, or a Group."""
        if level.key == DOCUMENT_LEVEL:
            return hui.icon.graph
        if placement_root(level.container):
            return hui.icon.macro
        return hui.icon.subgraph

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
        if self._save_button is not None:
            self._save_button.set_visibility(document.unsaved and context.can_edit())
        self._update_undo_redo_buttons(document)
        self._update_lock_button(context)
        self._update_view_switch(self._levels.get(self._active_level))
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
        """Show undo and redo only where the canvas allows editing; enable them from the history."""
        editable = self._edit_allowed()
        if self._undo_button is not None:
            self._undo_button.set_visibility(editable)
            self._undo_button.set_enabled(document.editor.can_undo())
        if self._redo_button is not None:
            self._redo_button.set_visibility(editable)
            self._redo_button.set_enabled(document.editor.can_redo())

    def _level_mode(self) -> LevelMode:
        """Return the level mode of the level on screen; ``VIEW`` when no level is open."""
        level = self._levels.get(self._active_level)
        return LevelMode.VIEW if level is None else level.route.mode()

    def _edit_allowed(self) -> bool:
        """Return whether the level on screen is in level mode ``EDIT``, lock included."""
        return self._level_mode() is LevelMode.EDIT

    def _draw_view_switch(self, context: "SessionContext") -> None:
        """Draw the Patch | Stage switch into the header row being built."""
        self._view_buttons = {}
        with (
            ui.row()
            .classes("items-center gap-0 no-wrap flex-shrink-0")
            .style("border: 1px solid var(--hw-border); border-radius: 4px;")
        ):
            for view, label in (("patch", "Patch"), ("stage", "Stage")):
                button = (
                    ui.button(label, on_click=lambda _e=None, v=view: self._on_view_button(context, v))
                    .props("flat dense no-caps size=xs")
                    .classes("px-2 text-xs hw-shell-toolbar-btn")
                    .style("border-radius: 3px;")
                )
                self._view_buttons[view] = button
                with button:
                    ui.tooltip(
                        f"{label} ({format_combo(ToggleStageView.default_keys[0], mac=False)} toggles)"
                    )
        self._update_view_switch(self._levels.get(self._active_level))

    def _on_view_button(self, context: "SessionContext", view: str) -> None:
        """Show ``view`` of the level on screen."""
        self._switch_view(context, self._active_level, view)

    def _update_view_switch(self, level: Optional[_Level]) -> None:
        """Mark the button of the view ``level`` shows; ``level`` is the one on screen."""
        if level is None or level.key != self._active_level:
            return
        for view, button in self._view_buttons.items():
            shown = view == level.view
            button.classes(
                add="hw-shell-toolbar-btn-active font-medium" if shown else None,
                remove=None if shown else "hw-shell-toolbar-btn-active font-medium",
            )
            button.props(f"aria-pressed={'true' if shown else 'false'}")

    def _update_lock_button(self, context: "SessionContext") -> None:
        """Show the lock icon of the level on screen, and the action a click takes; disabled below
        the real edit tier."""
        button = self._lock_button
        level = self._levels.get(self._active_level)
        if button is None or level is None:
            return
        button.props(f"icon={hui.icon.locked if level.locked else hui.icon.unlocked}")
        if self._lock_tooltip is not None:
            if placement_root(level.container) and context.can_edit():
                self._lock_tooltip.set_text(_EDIT_INSTANCE_TOOLTIP)
            elif level.inside_placement:
                self._lock_tooltip.set_text(_PLACEMENT_TOOLTIP)
            else:
                action = "Unlock" if level.locked else "Lock"
                combo = format_combo(ToggleLock.default_keys[0], mac=False)
                self._lock_tooltip.set_text(f"{action} ({combo})")
        button.set_enabled(
            context.can_edit() and (not level.inside_placement or placement_root(level.container))
        )

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
