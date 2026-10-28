"""GraphAppState — app-wide registry of open GraphContainers.

Lives at ``app_data[GraphAppState]``. Source libraries (haystack,
future cloud-graph libraries, etc.) register their containers when a
graph opens, unregister on close, and rekey on save-as. GraphEditor
looks up the container for its tab by ``binding_id`` on every render.

The registry holds *references* only — owning libraries remain
responsible for the underlying container's lifecycle (file I/O,
execution state, signal broadcast). GraphAppState's jobs are
identity routing: "which container does this binding_id point to?",
and bridging each registered file's undo history to ``GraphHistoryChanged``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from haywire.core.graph.base import BaseGraph
from haywire.core.signals import GraphHistoryChanged
from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

from haybale_graph_editor.protocols import GraphContainer

if TYPE_CHECKING:
    from haywire.core.graph.edit_route import EditRoute
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)


@state(label="Graph App State")
class GraphAppState(AppState):
    """Registry: ``binding_id`` → :class:`GraphContainer`.

    One instance per app, shared across sessions. Source libraries
    coordinate writes; GraphEditor performs reads.

    While a container is registered, every change to its undo history
    publishes ``GraphHistoryChanged`` on the event loop.
    """

    def __init__(self) -> None:
        super().__init__()
        self._graphs: dict[str, GraphContainer] = {}

    def register(self, container: GraphContainer) -> None:
        """Add or replace a container under its current ``binding_id``."""
        replaced = self._graphs.get(container.binding_id)
        if replaced is not None and replaced is not container:
            replaced.editor.history_manager.remove_listener(self._on_history_changed)
        self._graphs[container.binding_id] = container
        container.editor.history_manager.add_listener(self._on_history_changed)

    def unregister(self, binding_id: str) -> None:
        """Remove a container by ``binding_id``. Idempotent."""
        container = self._graphs.pop(binding_id, None)
        if container is not None:
            container.editor.history_manager.remove_listener(self._on_history_changed)

    def _on_history_changed(self) -> None:
        """Publish ``GraphHistoryChanged`` on the event loop; dropped while no loop runs."""
        from nicegui import core

        loop = core.loop
        if loop is None or not loop.is_running():
            return
        # Always deferred: the history calls this mid-operation, and on any thread.
        loop.call_soon_threadsafe(self._signal_emit, GraphHistoryChanged())

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


def route_for(context: "SessionContext") -> "EditRoute | None":
    """Return the edit route of the level this session has on screen, or ``None`` before one is open.

    Example::

        route = route_for(ctx)
        editor = route.editor() if route is not None else None  # None below level mode edit
        if editor is not None:
            editor.remove_port(node_id, port_id)
    """
    from haybale_graph_editor.state.edit_state import EditState

    return context.data[EditState].active_route
