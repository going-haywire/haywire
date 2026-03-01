# packages/haywire-app/src/haywire_app/graph_manager.py
"""
GraphManager — file-centric multi-graph registry.

Each .haywire file gets its own GraphEntry (graph + editor). Two sessions
opening the same file share the same entry and collaborate in real time.
An untitled entry (path=None) is created at startup and keyed as '__untitled__'.

Usage in app.py::

    graph_manager = GraphManager()
    untitled = graph_manager.create_untitled(factory)

    # When a file is opened:
    entry = graph_manager.open_graph(path, factory)
    graph_manager.session_attach(entry, session_id)

    # On save:
    graph_manager.save_graph(entry)

    # On session disconnect:
    graph_manager.session_detach(entry, session_id)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set, Tuple


# Factory signature: (graph_id: str, name: str) -> (BaseGraph, Editor)
GraphFactory = Callable[[str, str], Tuple[Any, Any]]


@dataclass
class GraphEntry:
    """
    Holds all runtime state for a single open graph.

    Attributes:
        graph:    The BaseGraph instance.
        editor:   Editor wrapping the graph for undo/redo and mutations.
        path:     Absolute Path to the .haywire file, or None for untitled.
        unsaved:  True if the graph has in-memory changes not yet written to disk.
        sessions: Session IDs currently viewing this graph.
    """
    graph: Any
    editor: Any
    path: Optional[Path] = None
    unsaved: bool = False
    sessions: Set[str] = field(default_factory=set)

    @property
    def key(self) -> str:
        """Registry key: str(path) or '__untitled__'."""
        return str(self.path) if self.path is not None else '__untitled__'

    @property
    def display_name(self) -> str:
        """Human-readable name for UI labels."""
        if self.path is not None:
            return self.path.name
        return 'Untitled'


class GraphManager:
    """
    Manages all open graph instances.

    Key design points:
    - One GraphEntry per unique file path; untitled graphs use key '__untitled__'.
    - Sessions attach/detach to track which sessions view which graph.
    - broadcast_data_mutation() in SessionManager uses graph_path to selectively
      notify only the sessions that are viewing the changed graph.
    """

    def __init__(self):
        self._entries: Dict[str, GraphEntry] = {}

    # ------------------------------------------------------------------
    # Graph lifecycle
    # ------------------------------------------------------------------

    def create_untitled(self, factory: GraphFactory) -> GraphEntry:
        """
        Create a new untitled graph and register it under '__untitled__'.

        If an untitled entry already exists it is replaced.

        Args:
            factory: Callable returning (BaseGraph, Editor) for given id/name.

        Returns:
            The new GraphEntry.
        """
        graph, editor = factory('untitled', 'Untitled Graph')
        entry = GraphEntry(graph=graph, editor=editor, path=None)
        self._entries['__untitled__'] = entry
        return entry

    def open_graph(self, path: Path, factory: GraphFactory) -> GraphEntry:
        """
        Open a .haywire file, reusing the existing entry if already loaded.

        Args:
            path: Absolute path to the .haywire file.
            factory: Callable returning (BaseGraph, Editor) for given id/name.

        Returns:
            Existing GraphEntry if the path is already open; otherwise a new one
            loaded from disk.
        """
        key = str(path)
        if key in self._entries:
            return self._entries[key]

        graph, editor = factory(path.stem, str(path))
        graph.load_from_file(str(path))
        entry = GraphEntry(graph=graph, editor=editor, path=path)
        self._entries[key] = entry
        return entry

    def save_graph(self, entry: GraphEntry, save_as: Optional[Path] = None) -> bool:
        """
        Save a graph entry to disk.

        Args:
            entry:   The GraphEntry to save.
            save_as: Override save path (Save As). If provided and different
                     from entry.path, the entry is re-keyed in the registry.

        Returns:
            True if the save succeeded.
        """
        target = save_as or entry.path
        if target is None:
            return False  # untitled with no explicit path — caller must supply one

        success = entry.graph.save_to_file(str(target))
        if success:
            entry.unsaved = False
            if save_as and save_as != entry.path:
                # Re-key the entry under the new path
                self._entries.pop(entry.key, None)
                entry.path = save_as
                self._entries[entry.key] = entry
        return success

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get_untitled(self) -> Optional[GraphEntry]:
        """Return the untitled entry, or None if it doesn't exist."""
        return self._entries.get('__untitled__')

    def get_by_path(self, path: Optional[Path]) -> Optional[GraphEntry]:
        """Return the entry for the given path (None path → untitled)."""
        if path is None:
            return self._entries.get('__untitled__')
        return self._entries.get(str(path))

    def get_by_key(self, key: str) -> Optional[GraphEntry]:
        """Return the entry for the given registry key."""
        return self._entries.get(key)

    def all_entries(self) -> Dict[str, GraphEntry]:
        """Return a snapshot dict of all entries."""
        return dict(self._entries)

    # ------------------------------------------------------------------
    # Session tracking
    # ------------------------------------------------------------------

    def session_attach(self, entry: GraphEntry, session_id: str) -> None:
        """Record that a session is now viewing this graph."""
        entry.sessions.add(session_id)

    def session_detach(self, entry: GraphEntry, session_id: str) -> None:
        """Remove a session from this graph."""
        entry.sessions.discard(session_id)

    def sessions_for_entry(self, entry: GraphEntry) -> Set[str]:
        """Return the set of session IDs currently viewing the entry."""
        return set(entry.sessions)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Remove all entries (call on application shutdown)."""
        self._entries.clear()
