# packages/haywire-app/src/haywire_studio/haystack.py
"""
Haystack — file-centric multi-graph registry.

Each .haywire file gets its own GraphEntry (graph + editor). Two sessions
opening the same file share the same entry and collaborate in real time.
An untitled entry (path=None) is created at startup and keyed as '__untitled__'.

Haystack support: the current set of open graphs can be saved to / loaded
from a TOML file in the ``haystacks/`` folder at the workspace root.

Usage in app.py::

    haystack = Haystack(workspace_root=Path(...))
    untitled = haystack.create_untitled(factory)

    # When a file is opened:
    entry = haystack.open_graph(path, factory)
    haystack.session_attach(entry, session_id)

    # On save:
    haystack.save_graph(entry)

    # Save/load haystacks:
    haystack.save_haystack("default")
    haystack.load_haystack("default", factory)

    # On session disconnect:
    haystack.session_detach(entry, session_id)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple
import logging

import toml

if TYPE_CHECKING:
    from haywire.core.graph.base import HaywireGraph
    from haywire.core.execution.interpreter import Interpreter
    from haywire.core.graph.editor import Editor

logger = logging.getLogger(__name__)

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
        interpreter:  Per-graph Interpreter instance (created on execution start).
    """

    graph: "HaywireGraph"
    editor: "Editor"
    path: Optional[Path] = None
    unsaved: bool = False
    sessions: Set[str] = field(default_factory=set)
    interpreter: Optional["Interpreter"] = field(default=None, repr=False)

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

    @property
    def is_executing(self) -> bool:
        """True if the interpreter is currently executing."""
        return self.interpreter is not None and self.interpreter.is_executing

    def start_execution(self) -> None:
        """Create an Interpreter and start execution for this graph."""
        if self.is_executing:
            return

        from haywire.core.execution.interpreter import Interpreter

        self.interpreter = Interpreter()
        self.interpreter.load_graph(self.graph)
        self.interpreter.start_execution()
        logger.info(f"Execution started for graph '{self.display_name}'")

    def stop_execution(self) -> None:
        """Stop execution and shut down the Interpreter."""
        if not self.is_executing:
            return

        try:
            self.interpreter.stop_execution()
        except Exception as e:
            logger.warning(f"Error stopping execution on '{self.display_name}': {e}")
        self.interpreter = None
        logger.info(f"Execution stopped for graph '{self.display_name}'")


class Haystack:
    """
    Manages all open graph instances and haystack persistence.

    Key design points:
    - One GraphEntry per unique file path; untitled graphs use key '__untitled__'.
    - New unnamed graphs get auto-keyed as '__new_1__', '__new_2__', etc.
    - Sessions attach/detach to track which sessions view which graph.
    - broadcast_data_mutation() in SessionManager uses graph_path to selectively
      notify only the sessions that are viewing the changed graph.
    - Haystacks: named selections of open graphs persisted as TOML in
      ``<workspace>/haystacks/*.toml``.
    """

    def __init__(self, workspace_root: Optional[Path] = None):
        self._entries: Dict[str, GraphEntry] = {}
        self._new_counter: int = 0
        self._workspace_root: Optional[Path] = workspace_root

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
    # Unsaved check
    # ------------------------------------------------------------------

    def has_unsaved(self) -> bool:
        """Return True if any entry has unsaved changes or no file path."""
        return any(e.unsaved or e.path is None for e in self._entries.values())

    def unsaved_entries(self) -> List[GraphEntry]:
        """Return entries that have unsaved changes or no file path."""
        return [e for e in self._entries.values() if e.unsaved or e.path is None]

    # ------------------------------------------------------------------
    # Haystack persistence
    # ------------------------------------------------------------------

    def _haystacks_dir(self) -> Optional[Path]:
        """Return the haystacks/ directory, or None if no workspace root."""
        if self._workspace_root is None:
            return None
        return self._workspace_root / "haystacks"

    def list_haystacks(self) -> List[str]:
        """Return sorted list of available haystack names (without extension)."""
        hdir = self._haystacks_dir()
        if hdir is None or not hdir.is_dir():
            return []
        return sorted(p.stem for p in hdir.glob("*.toml"))

    def save_haystack(self, name: str, active_graph_path: Optional[Path] = None) -> Path:
        """
        Save the current set of open graphs to a haystack file.

        Only file-backed entries (path is not None) are included.
        The active graph and per-graph execution state are stored.

        Args:
            name: Haystack name (used as filename stem).
            active_graph_path: Path of the currently active graph (stored in
                the haystack so it can be restored on load).

        Returns:
            The Path to the written haystack file.
        """
        hdir = self._haystacks_dir()
        if hdir is None:
            raise RuntimeError("Cannot save haystack: no workspace root configured")

        hdir.mkdir(parents=True, exist_ok=True)
        filepath = hdir / f"{name}.toml"

        # Build the active_graph value as a relative path string
        active_rel: Optional[str] = None
        if active_graph_path is not None:
            try:
                active_rel = str(active_graph_path.relative_to(self._workspace_root))
            except ValueError:
                active_rel = str(active_graph_path)

        # Build graph entries — only saved (file-backed) graphs
        graphs_list = []
        for entry in self._entries.values():
            if entry.path is None:
                continue
            try:
                rel = str(entry.path.relative_to(self._workspace_root))
            except ValueError:
                rel = str(entry.path)
            graphs_list.append(
                {
                    "path": rel,
                    "execute": entry.is_executing,
                }
            )

        data: Dict[str, Any] = {
            "haystack": {
                "name": name,
            },
            "graphs": graphs_list,
        }
        if active_rel is not None:
            data["haystack"]["active_graph"] = active_rel

        filepath.write_text(toml.dumps(data))
        logger.info(f"Haystack saved: {filepath} ({len(graphs_list)} graphs)")
        return filepath

    def load_haystack(
        self,
        name: str,
        factory: GraphFactory,
    ) -> Tuple[List[GraphEntry], Optional[str]]:
        """
        Load a haystack file, replacing all current entries.

        Stops execution on all current entries, clears the registry,
        then opens each graph listed in the haystack. Graphs marked with
        ``execute = true`` are started automatically.

        Args:
            name: Haystack name (filename stem in haystacks/).
            factory: Graph factory for opening files.

        Returns:
            Tuple of (list of opened GraphEntry instances,
            relative path of the active graph or None).

        Raises:
            FileNotFoundError: If the haystack file does not exist.
        """
        hdir = self._haystacks_dir()
        if hdir is None:
            raise RuntimeError("Cannot load haystack: no workspace root configured")

        filepath = hdir / f"{name}.toml"
        if not filepath.exists():
            raise FileNotFoundError(f"Haystack not found: {filepath}")

        data = toml.loads(filepath.read_text())
        haystack_meta = data.get("haystack", {})
        active_graph_rel = haystack_meta.get("active_graph")
        graphs_data = data.get("graphs", [])

        # Stop execution and clear all current entries
        self._stop_all_execution()
        self._entries.clear()
        self._new_counter = 0

        # Open each graph
        opened: List[GraphEntry] = []
        for gd in graphs_data:
            rel_path = gd.get("path")
            if not rel_path:
                continue
            abs_path = self._workspace_root / rel_path
            if not abs_path.exists():
                logger.warning(f"Haystack: skipping missing graph file: {abs_path}")
                continue

            entry = self.open_graph(abs_path, factory)
            opened.append(entry)

            if gd.get("execute", False):
                entry.start_execution()

        logger.info(f"Haystack loaded: {filepath} ({len(opened)}/{len(graphs_data)} graphs)")
        return opened, active_graph_rel

    def delete_haystack(self, name: str) -> bool:
        """Delete a haystack file. Returns True if removed."""
        hdir = self._haystacks_dir()
        if hdir is None:
            return False
        filepath = hdir / f"{name}.toml"
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Haystack deleted: {filepath}")
            return True
        return False

    # ------------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------------

    def _stop_all_execution(self) -> None:
        """Stop execution on all entries."""
        for entry in self._entries.values():
            entry.stop_execution()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Stop all execution and remove all entries (call on shutdown)."""
        self._stop_all_execution()
        self._entries.clear()
