"""HaystackState — AppState replacing the old studio.haystack.Haystack class.

In-memory registry of open graphs. One instance per app, shared across
sessions. Dependencies are resolved from the ambient DI context in
``on_enable`` rather than constructor arguments — this is the contract
``LibraryStateContainer`` enforces (it instantiates AppState classes
with ``cls()``, no args).

Three structural changes vs the legacy Haystack:

1. Subclass ``AppState``; instantiated by ``LibraryStateContainer``.
2. ``on_enable`` resolves dependencies from ambient context.
3. Validation broadcast goes directly via ``SessionManager`` — no
   editor or library-bridge intermediary.

Behavioral parity with legacy ``haywire_studio.haystack.Haystack`` is
maintained for every public method documented in the carve-out plan
(create_new, open_graph, save_graph, rename_graph, remove_entry,
get_by_id, get_by_path, get_by_graph, all_entries, has_unsaved,
unsaved_entries, list_haystacks, list_graph_files, rename_haystack,
delete_haystack). Haystack file load/dump are now provided by free
functions in ``persistence.py``; thin wrappers here forward to them.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.validation import ValidationResult
from haywire.core.node.factory import NodeFactory
from haywire.core.session.session_manager import SessionManager
from haywire.core.state import LibraryStateContainer

from ..graph_entry import GraphEntry
from ..settings.haystack_settings import HaystackSettings

from haybale_graph_editor.state.graph_app_state import GraphAppState

logger = logging.getLogger(__name__)


@state(label="Haystack State")
class HaystackState(AppState):
    """In-memory registry of open graphs (one entry per file path).

    Replaces ``haywire_studio.haystack.Haystack``. Dependencies are
    resolved from the ambient DI context inside ``on_enable``; the
    no-arg constructor is required by ``LibraryStateContainer``.
    """

    def __init__(self) -> None:
        super().__init__()
        self._entries: dict[str, GraphEntry] = {}
        self._haystack_dirty: bool = False

        # Dependencies resolved in on_enable.
        self._session_manager: Optional[SessionManager] = None
        self._workspace_root: Optional[Path] = None
        self._node_factory: Optional[NodeFactory] = None
        self._library_state_container: Optional[LibraryStateContainer] = None

        # Reference to the shared graph registry; populated in on_enable.
        # Direct attribute (not in app_data dict) for fast access from
        # save / open / remove hot paths.
        self._graph_app_state: Optional[GraphAppState] = None

        self._haystack_settings: HaystackSettings = HaystackSettings()

    # ------------------------------------------------------------------
    # AppState lifecycle
    # ------------------------------------------------------------------

    def on_enable(self) -> None:
        """Resolve ambient dependencies; rehydrate from settings."""
        from haywire.core.di.context import (
            get_library_state_container,
            get_node_factory,
            get_session_manager,
            get_workspace_root,
        )

        self._session_manager = get_session_manager()
        self._workspace_root = get_workspace_root()
        self._node_factory = get_node_factory()
        self._library_state_container = get_library_state_container()

        # Acquire the shared graph registry. Order is safe: graph_editor
        # library is listed in our dependencies (after Task 14), so its
        # AppState is instantiated before ours.
        self._graph_app_state = self._library_state_container.get(GraphAppState)

        # Rehydrate from last_haystack_name (best-effort).
        # Use self.load_haystack — not the free persistence.load_haystack —
        # so _haystack_dirty is cleared at the end. The free function calls
        # state.open_graph per entry, each of which marks dirty; without
        # the wrapping clear the haystack would appear permanently dirty
        # from the moment startup completes even though the in-memory set
        # exactly mirrors the TOML.
        last = self._haystack_settings.last_haystack_name
        if last:
            try:
                self.load_haystack(last)
                logger.info(f"HaystackState: rehydrated from '{last}'")
            except Exception as exc:
                logger.error(f"HaystackState: failed to rehydrate '{last}': {exc}")

        # Announce that the haystack is back. HaystackEditor reacts by
        # re-rendering its list against the (new) registry. Cross-session,
        # so peer sessions also refresh.
        if self._session_manager is not None:
            from haybale_haystack.signals import HaystackReloaded

            try:
                self._session_manager.broadcast(HaystackReloaded())
            except Exception as exc:
                logger.warning(f"HaystackState.on_enable: HaystackReloaded broadcast failed: {exc}")

    def on_disable(self) -> None:
        """Announce teardown, stop execution on every entry, clear the registry.

        Order matters: snapshot the entry_ids and broadcast
        ``HaystackTeardown`` BEFORE clearing, so HaystackEditor receivers
        can issue a local ``Close(binding_id=eid)`` for each vanishing tab.
        Receivers don't peek at the (about-to-be-cleared) registry — the
        signal binding_id is the source of truth for the teardown set.

        """

        entry_ids = tuple(self._entries.keys())

        if self._session_manager is not None and entry_ids:
            from haybale_haystack.signals import HaystackTeardown

            try:
                self._session_manager.broadcast(HaystackTeardown(entry_ids=entry_ids))
            except Exception as exc:
                logger.warning(f"HaystackState.on_disable: HaystackTeardown broadcast failed: {exc}")

        for entry in list(self._entries.values()):
            try:
                entry.stop_execution()
            except Exception as exc:
                logger.warning(
                    f"HaystackState.on_disable: stop_execution failed for {entry.display_name}: {exc}"
                )
        if self._graph_app_state is not None:
            for binding_id in list(self._entries.keys()):
                self._graph_app_state.unregister(binding_id)
        self._entries.clear()

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------

    def _broadcast_data_mutated(self) -> None:
        """Fire ``GraphDataMutated`` cross-session.

        Called from every mutator (``create_new``, ``open_graph``,
        ``save_graph``, ``rename_graph``, ``remove_entry``) and from
        the per-entry validation handler. Centralising the broadcast
        here means every haystack-mutating call site notifies peer
        sessions automatically — no need for individual UI handlers
        to remember.
        """
        if self._session_manager is None:
            return
        from haywire.core.session.signals import GraphDataMutated

        try:
            self._session_manager.broadcast(GraphDataMutated())
        except Exception as exc:
            logger.warning(f"HaystackState: GraphDataMutated broadcast failed: {exc}")

    # ------------------------------------------------------------------
    # Validation handler — legacy parity with Haystack._on_entry_validation
    # ------------------------------------------------------------------

    def _on_entry_validation(self, entry: GraphEntry, result: "ValidationResult") -> None:
        """Stop execution if reassembly is required, mark unsaved, broadcast.

        Mirrors the three concerns from the legacy Haystack:

        1. Stop execution when the result requires graph reassembly.
        2. Mark the entry unsaved if nodes or edges changed.
        3. Broadcast ``GraphDataMutated`` so peer sessions refresh.
        """
        if entry.is_executing and result.has_changes() and result.graph is not None:
            if result.graph.requires_graph_reassembly():
                entry.stop_execution()

        if bool(result.nodes or result.edges):
            entry.unsaved = True
            self._broadcast_data_mutated()

    # ------------------------------------------------------------------
    # Graph factory (private; mirrors legacy app._graph_factory)
    # ------------------------------------------------------------------

    def _make_graph_and_editor(self, graph_id: str, name: str) -> tuple["BaseGraph", "Editor"]:
        """Construct a fresh (BaseGraph, Editor) pair for this state's deps."""
        from haywire.core.graph.base import BaseGraph
        from haywire.core.graph.editor import Editor
        from haywire.core.undo.config import DEVELOPMENT_CONFIG

        assert self._node_factory is not None, "on_enable must run before _make_graph_and_editor"
        graph = BaseGraph(graph_id, name)
        editor = Editor(graph, self._node_factory, undo_config=DEVELOPMENT_CONFIG)
        return graph, editor

    # ------------------------------------------------------------------
    # Graph lifecycle
    # ------------------------------------------------------------------

    def create_new(self) -> GraphEntry:
        """Create a new untitled graph entry.

        Sets ``_unsaved_id = "__unsaved_N__"`` (with N drawn from
        ``HaystackSettings.new_counter``) and advances the counter.
        """
        counter = self._haystack_settings.new_counter
        binding_id = f"__unsaved_{counter}__"
        name = f"Untitled {counter}"
        self._haystack_settings.new_counter = counter + 1

        graph, editor = self._make_graph_and_editor(binding_id, name)
        entry = GraphEntry(graph=graph, editor=editor, path=None, _unsaved_id=binding_id, haystack=self)
        # binding_id == _unsaved_id when path is None (see GraphEntry.binding_id)
        self._entries[entry.binding_id] = entry
        self._subscribe_validation(entry)
        if self._graph_app_state is not None:
            # GraphEntry's binding_id/display_name are read-only properties;
            # the GraphContainer protocol declares them as settable. Structural
            # compatibility holds at runtime — the registry only reads.
            self._graph_app_state.register(entry)  # type: ignore[arg-type]
        logger.info(f"HaystackState: created new entry '{name}' ({binding_id})")
        self._broadcast_data_mutated()
        self._mark_haystack_dirty()
        return entry

    def open_graph(self, path: Path) -> GraphEntry:
        """Open a .haywire file, reusing the existing entry if loaded.

        On first open: constructs graph/editor, calls
        ``graph.load_from_file`` then ``graph.force_validation`` to flush
        the load-time validation queue *before* subscribing the handler
        (otherwise loaded-state events would mark the entry unsaved).
        """
        binding_id = str(path)
        existing = self._entries.get(binding_id)
        if existing is not None:
            return existing

        graph, editor = self._make_graph_and_editor(path.stem, str(path))
        graph.load_from_file(str(path))
        graph.force_validation()
        entry = GraphEntry(graph=graph, editor=editor, path=path, unsaved=False, haystack=self)
        self._entries[binding_id] = entry
        self._subscribe_validation(entry)
        if self._graph_app_state is not None:
            # See create_new() for note on the type: ignore.
            self._graph_app_state.register(entry)  # type: ignore[arg-type]
        logger.info(f"HaystackState: opened {path}")
        self._broadcast_data_mutated()
        self._mark_haystack_dirty()
        return entry

    def save_graph(self, entry: GraphEntry, save_as: Optional[Path] = None) -> bool:
        """Public alias preserved for backward compatibility.

        Most callers should use ``entry.save(save_as=...)`` now; this
        method routes to the same implementation. Returns True on
        successful save (legacy bool contract); ``entry.save`` returns
        the new binding_id string on rename for the
        :class:`GraphContainer` protocol.
        """
        return self._save_entry(entry, save_as=save_as) is not False

    def _save_entry(self, entry: GraphEntry, save_as: Optional[Path] = None):
        """Internal save implementation.

        Returns:
            - ``False`` on failure
            - ``None`` on save-with-no-rename (success, identity unchanged)
            - ``str`` (new binding_id) on save-as that renamed the entry

        Side effects on success:
            - writes the graph TOML to disk
            - clears ``entry.unsaved``
            - on rename: rekeys ``self._entries`` AND
              ``self._graph_app_state``
            - broadcasts ``GraphDataMutated``
            - marks haystack dirty
        """
        target = save_as or entry.path
        if target is None:
            return False  # untitled with no explicit path

        success = entry.graph.save_to_file(str(target))
        if not success:
            return False

        entry.unsaved = False
        renamed_to: Optional[str] = None

        if save_as is not None and save_as != entry.path:
            old_binding_id = entry.binding_id
            self._entries.pop(old_binding_id, None)
            entry.path = save_as
            self._entries[entry.binding_id] = entry
            if self._graph_app_state is not None:
                self._graph_app_state.rekey(old_binding_id, entry.binding_id)
            renamed_to = entry.binding_id

        self._broadcast_data_mutated()
        self._mark_haystack_dirty()
        return renamed_to  # None when no rename; str on rename

    def rename_graph(self, entry: GraphEntry, new_name: str) -> bool:
        """Rename the underlying file (same directory, new stem)."""
        if entry.path is None:
            return False
        new_path = entry.path.with_stem(new_name)
        if new_path == entry.path:
            return True
        if new_path.exists():
            return False  # refuse to overwrite

        try:
            entry.path.rename(new_path)
        except OSError:
            return False

        old_id = entry.binding_id
        self._entries.pop(old_id, None)
        entry.path = new_path
        self._entries[entry.binding_id] = entry
        entry.unsaved = False
        if self._graph_app_state is not None:
            self._graph_app_state.rekey(old_id, entry.binding_id)
        self._broadcast_data_mutated()
        self._mark_haystack_dirty()
        return True

    def remove_entry(self, entry: GraphEntry) -> bool:
        """Stop execution and drop the entry from the registry.

        Does NOT delete the file on disk.
        """
        try:
            entry.stop_execution()
        except Exception as exc:
            logger.warning(f"HaystackState.remove_entry: stop_execution failed: {exc}")
        if entry.binding_id in self._entries and self._entries[entry.binding_id] is entry:
            if self._graph_app_state is not None:
                self._graph_app_state.unregister(entry.binding_id)
            del self._entries[entry.binding_id]
            self._broadcast_data_mutated()
            self._mark_haystack_dirty()
            return True
        return False

    # ------------------------------------------------------------------
    # Execution wrappers — UI call sites route through these so the
    # state observes start/stop transitions.
    # ------------------------------------------------------------------

    def start_execution(self, entry: GraphEntry) -> None:
        entry.start_execution()
        self._mark_haystack_dirty()

    def stop_execution(self, entry: GraphEntry) -> None:
        entry.stop_execution()
        self._mark_haystack_dirty()

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get_by_id(self, binding_id: str) -> Optional[GraphEntry]:
        return self._entries.get(binding_id)

    def get_by_path(self, path: Path) -> Optional[GraphEntry]:
        return self._entries.get(str(path))

    def get_by_graph(self, graph: object) -> Optional[GraphEntry]:
        for entry in self._entries.values():
            if entry.graph is graph:
                return entry
        return None

    def all_entries(self) -> list[GraphEntry]:
        """Return a list of all open entries (snapshot).

        Note: legacy Haystack returned a dict; PR2 review mandated a
        list. ``persistence.py`` and tests expect a list.
        """
        return list(self._entries.values())

    # ------------------------------------------------------------------
    # Unsaved checks
    # ------------------------------------------------------------------

    def has_unsaved(self) -> bool:
        """True if any entry has unsaved changes or no file path."""
        return any(e.unsaved or e.path is None for e in self._entries.values())

    def unsaved_entries(self) -> list[GraphEntry]:
        """Entries with unsaved changes or no file path."""
        return [e for e in self._entries.values() if e.unsaved or e.path is None]

    # ------------------------------------------------------------------
    # Named-haystack persistence — the authoritative API
    # ------------------------------------------------------------------

    def save_haystack(self, name: str, active_path: Optional[Path] = None) -> Path:
        """Persist the current registry to the named haystack TOML.

        Writes the TOML via ``persistence.dump_haystack`` and, if settings
        are wired, updates ``HaystackSettings.last_haystack_name = name``
        so the next ``on_enable`` rehydrates from the same file.

        Clears ``_haystack_dirty`` and broadcasts ``GraphDataMutated`` so
        the HaystackEditor re-renders and removes the header's dirty
        indicator + save icon.

        Returns the path to the written TOML file.
        """
        from haybale_haystack import persistence

        assert self._workspace_root is not None, "save_haystack requires on_enable to have run"
        target = persistence.dump_haystack(self, self._workspace_root, name, active_path=active_path)
        self._haystack_settings.last_haystack_name = name
        self._haystack_dirty = False
        # State transitioned (dirty → clean); broadcast so HaystackEditor
        # redraws and the header chrome reflects the new clean state.
        self._broadcast_data_mutated()
        return target

    def load_haystack(self, name: str) -> Optional[Path]:
        """Load the named haystack and open all graphs it lists.

        Returns the absolute path of the haystack's stored ``active_graph``
        (if any), so callers can route a ``Reveal`` to that entry. If the
        load succeeded, updates ``HaystackSettings.last_haystack_name = name``.

        Note: caller is responsible for clearing existing entries first if
        the desired semantics are "replace" rather than "merge". Mirrors
        ``persistence.load_haystack`` (which does NOT clear).
        """
        from haybale_haystack import persistence

        assert self._workspace_root is not None, "load_haystack requires on_enable to have run"
        # Check existence BEFORE delegating, so a missing-file load doesn't poison
        # last_haystack_name (persistence.load_haystack returns None silently in
        # that case; without this guard the next on_enable would try to rehydrate
        # a name whose TOML doesn't exist and warn-and-skip).
        source = persistence.haystack_path(self._workspace_root, name)
        active = persistence.load_haystack(self, self._workspace_root, name)
        if source.exists():
            self._haystack_settings.last_haystack_name = name
        # After a fresh load the in-memory set matches the TOML by
        # definition — any prior dirty signal is now stale.
        self._haystack_dirty = False
        return active

    # ------------------------------------------------------------------
    # Haystack file management — thin wrappers over persistence.*
    # ------------------------------------------------------------------

    def list_haystacks(self) -> list[str]:
        from haybale_haystack.persistence import list_haystacks as _list

        if self._workspace_root is None:
            return []
        return _list(self._workspace_root)

    def list_graph_files(self) -> list[Path]:
        """Scan ``<workspace>/graphs/`` recursively for .haywire files."""
        if self._workspace_root is None:
            return []
        graphs_dir = self._workspace_root / "graphs"
        if not graphs_dir.is_dir():
            return []
        return sorted(p for p in graphs_dir.rglob("*.haywire") if p.is_file())

    def rename_haystack(self, old_name: str, new_name: str) -> bool:
        from haybale_haystack.persistence import rename_haystack as _rename

        if self._workspace_root is None:
            return False
        return _rename(self._workspace_root, old_name, new_name)

    def delete_haystack(self, name: str) -> bool:
        from haybale_haystack.persistence import delete_haystack as _delete

        if self._workspace_root is None:
            return False
        return _delete(self._workspace_root, name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mark_haystack_dirty(self) -> None:
        """Mark the haystack-set as diverged from the saved TOML.

        Set whenever a mutator changes the registry shape or execution
        state. Cleared in ``save_haystack``.

        Consumed by HaystackEditor to show a dirty indicator + save
        icon on the haystack header.
        """
        self._haystack_dirty = True

    def _subscribe_validation(self, entry: GraphEntry) -> None:
        """Subscribe ``_on_entry_validation`` to this entry's graph.

        Defensively skips if the graph has no subscribe_to_validation
        method (e.g. test mocks). Does not store the callback for
        unsubscribe — legacy parity, plus the entry's lifetime is
        bounded by ``remove_entry``/``on_disable``.
        """
        try:
            entry.graph.subscribe_to_validation(
                lambda result, _entry=entry: self._on_entry_validation(_entry, result)  # type: ignore[misc]
            )
        except AttributeError:
            pass
