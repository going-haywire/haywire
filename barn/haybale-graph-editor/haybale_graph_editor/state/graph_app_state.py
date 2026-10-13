"""GraphAppState — app-wide registry of open GraphContainers.

Lives at ``app_data[GraphAppState]``. Source libraries (haystack,
future cloud-graph libraries, etc.) register their containers when a
graph opens, unregister on close, and rekey on save-as. GraphEditor
looks up the container for its tab by ``binding_id`` on every render.

The registry holds *references* only — owning libraries remain
responsible for the underlying container's lifecycle (file I/O,
execution state, signal broadcast). GraphAppState's only job is
identity routing: "which container does this binding_id point to?"
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Iterator, Optional

from haywire.core.graph.base import BaseGraph
from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

from haybale_graph_editor.protocols import GraphContainer

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)


@state(label="Graph App State")
class GraphAppState(AppState):
    """Registry: ``binding_id`` → :class:`GraphContainer`.

    One instance per app, shared across sessions. Source libraries
    coordinate writes; GraphEditor performs reads.
    """

    def __init__(self) -> None:
        super().__init__()
        self._graphs: dict[str, GraphContainer] = {}

    def register(self, container: GraphContainer) -> None:
        """Add or replace a container under its current ``binding_id``."""
        self._graphs[container.binding_id] = container

    def unregister(self, binding_id: str) -> None:
        """Remove a container by ``binding_id``. Idempotent."""
        self._graphs.pop(binding_id, None)

    def get(self, binding_id: str) -> Optional[GraphContainer]:
        """Look up a container by ``binding_id``. Returns None when absent."""
        return self._graphs.get(binding_id)

    def get_by_graph(self, graph: BaseGraph) -> Optional[GraphContainer]:
        """Find the container wrapping ``graph`` by identity, or None.

        Used to recover a container whose ``binding_id`` changed out from
        under a holder (e.g. a save-as that rekeyed the entry from another
        editor): the graph object survives the rekey, so a tab can locate
        its new identity by matching ``container.editor.graph is graph``.
        """
        for container in self._graphs.values():
            if container.editor.graph is graph:
                return container
        return None

    def rekey(self, old_id: str, new_id: str) -> None:
        """Move a container from ``old_id`` to ``new_id``.

        ``binding_id`` is ``str(path)`` for saved graphs (absolute filesystem
        path) and the graph's transient ``graph_id`` for unsaved ones. Source
        libraries call this after a save-as that changes the container's
        identity. No-op when ``old_id`` is unknown or identical to ``new_id``.
        When ``new_id`` is already occupied, the destination is overwritten —
        see test_rekey_overwrites_existing_destination.
        """
        if old_id == new_id:
            return
        container = self._graphs.pop(old_id, None)
        if container is None:
            return
        self._graphs[new_id] = container

    def all_containers(self) -> list[GraphContainer]:
        """Snapshot of all registered containers. Mutating the list does
        not affect the registry."""
        return list(self._graphs.values())


def editor_for(context: "SessionContext"):
    """An ``Editor`` over the graph on screen, or ``None`` before one is open.

    A panel is handed the graph, never the container that owns its undo
    history, so the container is found by graph identity — the same way
    ``GraphEditor`` recovers one whose binding_id moved.

    Only *documents* are registered in :class:`GraphAppState`; the
    ``SubgraphContainer`` for an open Group is the graph editor's own and never
    goes in there. So a Group's graph finds no container, and this builds an
    ``Editor`` over it that records on the document's history — which is what
    ``SubgraphContainer`` does too, so an edit inside a Group undoes in order
    with the edits around it. Construction is inert (field assignment only).
    """
    from haywire.core.graph.editor import Editor

    from haybale_graph_editor.state.edit_state import EditState

    graph = context.data[EditState].active_graph
    if graph is None:
        return None

    app_state = context.app_data[GraphAppState]
    container = app_state.get_by_graph(graph)
    if container is not None:
        return container.editor

    node_factory = getattr(context.app, "node_factory", None)
    if node_factory is None:
        return None
    return Editor(graph, node_factory, history_manager=_host_history(app_state, graph))


def _host_history(app_state: GraphAppState, graph) -> Any:
    """The history of the document holding ``graph``, or ``None`` for its own.

    A Subgraph belongs to the file that holds it, so an edit inside one is an
    edit to that file and records on its history. ``None`` when no open
    document claims it, which leaves the new editor a private history rather
    than silently recording nowhere.
    """
    for container in app_state.all_containers():
        document = container.editor.graph
        if any(definition is graph for definition in _subgraphs_of(document)):
            return container.editor.history_manager
    return None


def _subgraphs_of(graph) -> "Iterator[Any]":
    """Every Subgraph beneath ``graph``, at any depth."""
    for definition in getattr(graph, "subgraphs", {}).values():
        yield definition
        yield from _subgraphs_of(definition)
