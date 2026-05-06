# packages/haywire-app/src/haywire_studio/haystack.py
"""
Haystack — file-centric multi-graph registry.

Each .haywire file gets its own GraphEntry (graph + editor). Two sessions
opening the same file share the same entry and collaborate in real time.

Haystack support: the current set of open graphs can be saved to / loaded
from a TOML file in the ``haystacks/`` folder at the workspace root.

Usage in app.py::

    haystack = Haystack(
        workspace_root=Path(...),
        graph_factory=app._graph_factory,
        session_manager=app.session_manager,
    )

    # When a file is opened:
    entry = haystack.open_graph(path)

    # When the user creates a new unnamed graph:
    entry = haystack.create_new()

    # On save:
    haystack.save_graph(entry)

    # Save/load haystacks:
    haystack.save_haystack("default")
    haystack.load_haystack("default")
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
import logging

import toml

from haywire.ui.context_signals import GraphDataMutated

if TYPE_CHECKING:
    from haywire.core.graph.base import HaywireGraph
    from haywire.core.execution.interpreter import Interpreter
    from haywire.core.graph.editor import Editor
    from haywire.core.graph.validation import ValidationResult
    from haywire.ui.session_manager import SessionManager

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
        interpreter:  Per-graph Interpreter instance (created on execution start).
        _unsaved_id: Synthetic ``__unsaved_N__`` token, set by Haystack on
            :meth:`Haystack.create_new`. Unused once the entry is saved and
            :attr:`path` becomes non-None. Accessed indirectly via
            :attr:`entry_id`.
    """

    graph: "HaywireGraph"
    editor: "Editor"
    path: Optional[Path] = None
    unsaved: bool = False
    interpreter: Optional["Interpreter"] = field(default=None, repr=False)
    _unsaved_id: str = ""

    @property
    def entry_id(self) -> str:
        """Stable identifier within the Haystack's ``_entries`` dict.

        For saved graphs this is ``str(path)``; for unsaved graphs it is the
        synthetic ``__unsaved_N__`` token set at creation time. Updates
        automatically when :attr:`path` is assigned on save-as or rename.
        """
        return str(self.path) if self.path is not None else self._unsaved_id

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

        from haywire.core.di.config import get_library_system
        from haywire.core.execution.interpreter import Interpreter
        from haywire.core.state import LibraryStateContainer

        library_state_container = get_library_system().injector.get(LibraryStateContainer)
        self.interpreter = Interpreter(library_state_container=library_state_container)
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
    - One GraphEntry per unique file path, keyed by ``str(path)``.
    - New unnamed graphs get auto-keyed as '__unsaved_1__', '__unsaved_2__', etc.
    - Haystacks: named selections of open graphs persisted as TOML in
      ``<workspace>/haystacks/*.toml``.
    """

    def __init__(
        self,
        workspace_root: Path,
        graph_factory: GraphFactory,
        session_manager: "SessionManager",
    ):
        self._entries: Dict[str, GraphEntry] = {}
        self._new_counter: int = 0
        self._workspace_root: Path = workspace_root
        self._graph_factory: GraphFactory = graph_factory
        self._session_manager = session_manager

    # ------------------------------------------------------------------
    # Validation → entry lifecycle + cross-session broadcast
    # ------------------------------------------------------------------

    def _on_entry_validation(self, entry: GraphEntry, result: "ValidationResult") -> None:
        """Handle a validation result on one of this haystack's entries.

        Three concerns, all rooted in the fact that a graph under this
        haystack's ownership just validated:

        1. Stop execution if the result requires graph reassembly.
        2. Mark the entry unsaved if the result mutated data.
        3. Broadcast DATA_MUTATED so peer sessions refresh.
        """
        if entry.is_executing and result.has_changes() and result.graph is not None:
            if result.graph.requires_graph_reassembly():
                entry.stop_execution()

        if bool(result.nodes or result.edges):
            entry.unsaved = True
            # System-level broadcast (no originating session). Every session
            # sees the signal with subject=peer("") — receivers re-read
            # ground-truth state from the shared BaseGraph and don't depend
            # on subject identity here.
            self._session_manager.broadcast_signal(GraphDataMutated(), origin_session_id="")

    # ------------------------------------------------------------------
    # Graph lifecycle
    # ------------------------------------------------------------------

    def create_new(self) -> GraphEntry:
        """
        Create a new unnamed graph.

        Each call produces a fresh entry with ``entry_id`` ``'__unsaved_1__'``,
        ``'__unsaved_2__'``, … and named ``'Untitled 1'``, ``'Untitled 2'``, …

        Returns:
            The new GraphEntry.
        """
        self._new_counter += 1
        entry_id = f"__unsaved_{self._new_counter}__"
        name = f"Untitled {self._new_counter}"
        graph, editor = self._graph_factory(entry_id, name)
        entry = GraphEntry(graph=graph, editor=editor, path=None, _unsaved_id=entry_id)
        self._entries[entry_id] = entry
        entry.graph.subscribe_to_validation(
            lambda result, _entry=entry: self._on_entry_validation(_entry, result)
        )
        return entry

    def open_graph(self, path: Path) -> GraphEntry:
        """
        Open a .haywire file, reusing the existing entry if already loaded.

        On first-time open, subscribes the validation callback.

        Args:
            path: Absolute path to the .haywire file.

        Returns:
            The (existing or newly-loaded) GraphEntry.
        """
        entry_id = str(path)
        entry = self._entries.get(entry_id)
        if entry is None:
            graph, editor = self._graph_factory(path.stem, str(path))
            graph.load_from_file(str(path))
            # Flush the validation queue load_from_file enqueued BEFORE
            # subscribing the handler, otherwise those events fire later
            # and mark the freshly-loaded graph as unsaved.
            graph.force_validation()
            entry = GraphEntry(graph=graph, editor=editor, path=path)
            self._entries[entry_id] = entry
            entry.graph.subscribe_to_validation(
                lambda result, _entry=entry: self._on_entry_validation(_entry, result)
            )
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
                self._entries.pop(entry.entry_id, None)
                entry.path = save_as
                self._entries[entry.entry_id] = entry
        return success

    def remove_entry(self, entry: GraphEntry) -> bool:
        """
        Remove a graph entry from the registry.

        Stops execution if running. Does NOT delete the file on disk.

        Returns:
            True if the entry was found and removed.
        """
        entry.stop_execution()
        if entry.entry_id in self._entries and self._entries[entry.entry_id] is entry:
            del self._entries[entry.entry_id]
            return True
        return False

    def rename_graph(self, entry: GraphEntry, new_name: str) -> bool:
        """
        Rename a graph's file on disk (same directory, new stem).

        The entry's path and registry key are updated. The old file is
        moved to the new name via ``Path.rename()``.

        Args:
            entry:    The GraphEntry to rename.
            new_name: New filename stem (without extension).

        Returns:
            True if the rename succeeded.
        """
        if entry.path is None:
            return False

        new_path = entry.path.with_stem(new_name)
        if new_path == entry.path:
            return True  # nothing to do
        if new_path.exists():
            return False  # refuse to overwrite

        try:
            entry.path.rename(new_path)
        except OSError:
            return False

        self._entries.pop(entry.entry_id, None)
        entry.path = new_path
        self._entries[entry.entry_id] = entry
        entry.unsaved = False
        return True

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get_by_path(self, path: Path) -> Optional[GraphEntry]:
        """Return the entry for the given file path, or ``None`` if not loaded."""
        return self._entries.get(str(path))

    def get_by_id(self, entry_id: str) -> Optional[GraphEntry]:
        """Return the entry for the given ``entry_id``."""
        return self._entries.get(entry_id)

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

    def _haystacks_dir(self) -> Path:
        """Return the haystacks/ directory."""
        return self._workspace_root / "haystacks"

    def list_haystacks(self) -> List[str]:
        """Return sorted list of available haystack names (without extension)."""
        hdir = self._haystacks_dir()
        if not hdir.is_dir():
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
    ) -> Tuple[List[GraphEntry], Optional[str]]:
        """
        Load a haystack file, replacing all current entries.

        Stops execution on all current entries, clears the registry,
        then opens each graph listed in the haystack. Graphs marked with
        ``execute = true`` are started automatically. Each freshly-opened
        entry has the validation handler subscribed.

        Args:
            name: Haystack name (filename stem in haystacks/).

        Returns:
            Tuple of (list of opened GraphEntry instances,
            relative path of the active graph or None).

        Raises:
            FileNotFoundError: If the haystack file does not exist.
        """
        hdir = self._haystacks_dir()
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

        # Open each graph — we reuse the entry-creation core by inlining it.
        # Validation subscriber IS invoked.
        opened: List[GraphEntry] = []
        for gd in graphs_data:
            rel_path = gd.get("path")
            if not rel_path:
                continue
            abs_path = self._workspace_root / rel_path
            if not abs_path.exists():
                logger.warning(f"Haystack: skipping missing graph file: {abs_path}")
                continue

            key = str(abs_path)
            graph, editor = self._graph_factory(abs_path.stem, str(abs_path))
            graph.load_from_file(str(abs_path))
            graph.force_validation()
            entry = GraphEntry(graph=graph, editor=editor, path=abs_path)
            self._entries[key] = entry
            entry.graph.subscribe_to_validation(
                lambda result, _entry=entry: self._on_entry_validation(_entry, result)
            )
            opened.append(entry)

            if gd.get("execute", False):
                entry.start_execution()

        logger.info(f"Haystack loaded: {filepath} ({len(opened)}/{len(graphs_data)} graphs)")
        return opened, active_graph_rel

    def rename_haystack(self, old_name: str, new_name: str) -> bool:
        """
        Rename a haystack file on disk.

        Args:
            old_name: Current haystack name (filename stem).
            new_name: Desired haystack name (filename stem).

        Returns:
            True if the rename succeeded.
        """
        hdir = self._haystacks_dir()
        old_path = hdir / f"{old_name}.toml"
        new_path = hdir / f"{new_name}.toml"

        if not old_path.exists():
            return False
        if new_path.exists():
            return False  # refuse to overwrite

        try:
            old_path.rename(new_path)
        except OSError:
            return False

        # Update the stored name inside the TOML
        try:
            data = toml.loads(new_path.read_text())
            if "haystack" in data:
                data["haystack"]["name"] = new_name
                new_path.write_text(toml.dumps(data))
        except Exception:
            pass  # rename succeeded even if TOML update fails

        logger.info(f"Haystack renamed: {old_name} → {new_name}")
        return True

    def list_graph_files(self) -> List[Path]:
        """
        Scan the graphs/ folder for all .haywire files.

        Searches ``<workspace_root>/graphs/`` and its subfolders.

        Returns:
            Sorted list of absolute Paths to .haywire files.
        """
        graphs_dir = self._workspace_root / "graphs"
        if not graphs_dir.is_dir():
            return []
        return sorted(p for p in graphs_dir.rglob("*.haywire") if p.is_file())

    def delete_haystack(self, name: str) -> bool:
        """Delete a haystack file. Returns True if removed."""
        hdir = self._haystacks_dir()
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
