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
from typing import Optional

from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

from haybale_graph_editor.protocols import GraphContainer

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

    def rekey(self, old_id: str, new_id: str) -> None:
        """Move a container from ``old_id`` to ``new_id``.

        Source libraries call this after a save-as that changes the
        container's identity. No-op when ``old_id`` is unknown or
        identical to ``new_id``. When ``new_id`` is already occupied,
        the destination is overwritten — see test_rekey_overwrites_existing_destination.
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
