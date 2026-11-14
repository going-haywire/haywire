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
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from haywire.core.graph.base import BaseGraph
from haywire.core.signals import GraphHistoryChanged
from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

from haybale_graph_editor.notices import GraphNotice, GraphNoticesChanged
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
        self._graphs_listeners: list[Callable[[], None]] = []
        self._notices: dict[str, dict[str, GraphNotice]] = {}
        self._notices_lock = threading.Lock()

    def add_graphs_listener(self, cb: Callable[[], None]) -> None:
        """Call ``cb()`` after a graph is registered, unregistered or rekeyed.

        Listeners take no arguments; re-read :meth:`all_containers`. They run on
        the thread that changed the registry and must not raise.
        """
        if cb not in self._graphs_listeners:
            self._graphs_listeners.append(cb)

    def remove_graphs_listener(self, cb: Callable[[], None]) -> None:
        """Stop calling ``cb``. Idempotent."""
        if cb in self._graphs_listeners:
            self._graphs_listeners.remove(cb)

    def _notify_graphs(self) -> None:
        for cb in list(self._graphs_listeners):
            try:
                cb()
            except Exception:
                logger.exception("graphs listener failed")

    def post_notice(self, binding_id: str, notice: GraphNotice) -> None:
        """Attach ``notice`` to the graph under ``binding_id``, replacing the one with the same key.

        Ignored when no graph is registered under ``binding_id``. Safe to call
        from any thread.
        """
        with self._notices_lock:
            if binding_id not in self._graphs:
                logger.debug("post_notice: unknown binding %s", binding_id)
                return
            bucket = self._notices.setdefault(binding_id, {})
            if bucket.get(notice.key) == notice:
                return
            bucket[notice.key] = notice
        self._emit_notices_changed()

    def retract_notice(self, binding_id: str, key: str) -> None:
        """Remove the notice ``key`` from a graph. Idempotent; safe from any thread."""
        with self._notices_lock:
            bucket = self._notices.get(binding_id)
            if bucket is None or key not in bucket:
                return
            del bucket[key]
            if not bucket:
                del self._notices[binding_id]
        self._emit_notices_changed()

    def notices(self, binding_id: str) -> list[GraphNotice]:
        """Return the notices on a graph in the order they were first posted."""
        with self._notices_lock:
            return list(self._notices.get(binding_id, {}).values())

    def _emit_notices_changed(self) -> None:
        """Publish ``GraphNoticesChanged`` on the event loop; dropped while no loop runs."""
        from nicegui import core

        loop = core.loop
        if loop is None or not loop.is_running():
            return
        loop.call_soon_threadsafe(self._signal_emit, GraphNoticesChanged())

    def register(self, container: GraphContainer) -> None:
        """Add or replace a container under its current ``binding_id``."""
        replaced = self._graphs.get(container.binding_id)
        if replaced is not None and replaced is not container:
            replaced.editor.history_manager.remove_listener(self._on_history_changed)
        self._graphs[container.binding_id] = container
        container.editor.history_manager.add_listener(self._on_history_changed)
        findings = getattr(container.editor.graph, "library_compatibility_findings", None) or []
        for i, finding in enumerate(findings):
            self.post_notice(
                container.binding_id,
                GraphNotice(key=f"haywire:compatibility:{i}", text=finding, dismissable=True),
            )
        self._notify_graphs()

    def unregister(self, binding_id: str) -> None:
        """Remove a container by ``binding_id``. Idempotent."""
        container = self._graphs.pop(binding_id, None)
        if container is not None:
            container.editor.history_manager.remove_listener(self._on_history_changed)
            with self._notices_lock:
                had_notices = self._notices.pop(binding_id, None) is not None
            if had_notices:
                self._emit_notices_changed()
            self._notify_graphs()

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
        with self._notices_lock:
            moved = self._notices.pop(old_id, None)
            if moved is not None:
                self._notices[new_id] = moved
        if moved is not None:
            self._emit_notices_changed()
        self._notify_graphs()

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
    from haybale_graph_editor.states.edit_state import EditState

    return context.data[EditState].active_route
