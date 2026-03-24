# packages/haywire-app/src/haywire_studio/graph_manager.py
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
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Set, Tuple

if TYPE_CHECKING:
    from haywire.core.graph.base import HaywireGraph
    from haywire.ui.editor.base import BaseEditor

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

    graph: "HaywireGraph"
    editor: "BaseEditor"
    path: Optional[Path] = None
    unsaved: bool = False
    sessions: Set[str] = field(default_factory=set)

    @property
    def key(self) -> str:
        """Registry key: str(path) or '__untitled__'."""
        return str(self.path) if self.path is not None else "__untitled__"

    @property
    def display_name(self) -> str:
        """Human-readable name for UI labels."""
        if self.path is not None:
            return self.path.name
        return getattr(self.graph, "name", None) or "Untitled"


class GraphManager:
    """
    Manages all open graph instances.

    Key design points:
    - One GraphEntry per unique file path; untitled graphs use key '__untitled__'.
    - New unnamed graphs get auto-keyed as '__new_1__', '__new_2__', etc.
    - Sessions attach/detach to track which sessions view which graph.
    - broadcast_data_mutation() in SessionManager uses graph_path to selectively
      notify only the sessions that are viewing the changed graph.
    """

    def __init__(self):
        self._entries: Dict[str, GraphEntry] = {}
        self._new_counter: int = 0

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
        graph, editor = factory("untitled", "Untitled Graph")
        entry = GraphEntry(graph=graph, editor=editor, path=None)
        self._entries["__untitled__"] = entry
        return entry

    def create_new(self, factory: GraphFactory) -> GraphEntry:
        """
        Create a new unnamed graph with a unique auto-generated key and name.

        Unlike ``create_untitled`` this does NOT replace any existing entry.
        Each call produces a fresh entry keyed as ``'__new_1__'``, ``'__new_2__'``, …
        and named ``'Untitled 1'``, ``'Untitled 2'``, …

        Args:
            factory: Callable returning (BaseGraph, Editor) for given id/name.

        Returns:
            The new GraphEntry.
        """
        self._new_counter += 1
        key = f"__new_{self._new_counter}__"
        name = f"Untitled {self._new_counter}"
        graph, editor = factory(key, name)
        entry = GraphEntry(graph=graph, editor=editor, path=None)
        self._entries[key] = entry
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
        # Flush any deferred NODE_ADDED/EDGE_ADDED validation events that
        # load_from_file queues. This must happen BEFORE the entry is created
        # and before any validation handler is subscribed, so that those events
        # don't fire later and incorrectly mark the freshly loaded graph as unsaved.
        graph.force_validation()
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
                # Find and remove the entry's current registry key by identity
                # (cannot use entry.key here — it returns '__untitled__' for any
                # path-less entry, including '__new_N__' ones).
                old_key = next((k for k, v in self._entries.items() if v is entry), None)
                if old_key is not None:
                    self._entries.pop(old_key)
                entry.path = save_as
                self._entries[entry.key] = entry
        return success

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get_untitled(self) -> Optional[GraphEntry]:
        """Return the untitled entry, or None if it doesn't exist."""
        return self._entries.get("__untitled__")

    def get_by_path(self, path: Optional[Path]) -> Optional[GraphEntry]:
        """Return the entry for the given path (None path → untitled)."""
        if path is None:
            return self._entries.get("__untitled__")
        return self._entries.get(str(path))

    def get_by_key(self, key: str) -> Optional[GraphEntry]:
        """Return the entry for the given registry key."""
        return self._entries.get(key)

    def get_by_graph(self, graph) -> Optional[GraphEntry]:
        """Return the entry whose .graph attribute is the given object, or None."""
        for entry in self._entries.values():
            if entry.graph is graph:
                return entry
        return None

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
