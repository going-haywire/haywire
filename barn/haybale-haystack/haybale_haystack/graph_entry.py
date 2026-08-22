"""GraphEntry — one open graph in a Haystack.

Carries the graph object, its editor, optional file path, dirty flag,
and an optional Interpreter when execution is running.

Moved from haywire-studio's haystack.py during the haybale-haystack
carve-out.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from haywire.core.di.context import get_library_state_container
from haywire.core.execution.compile_result import CompileResult
from haywire.core.execution.interpreter import Interpreter
from haybale_graph_editor.protocols import GraphContainer
from haybale_haystack.settings.graph_run_settings import GraphRunSettings

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph as HaywireGraph
    from haywire.core.graph.editor import Editor
    from haybale_haystack.state.haystack_state import HaystackState

logger = logging.getLogger(__name__)


@dataclass
class GraphEntry(GraphContainer):
    """Holds all runtime state for a single open graph.

    Attributes:
        graph:        The BaseGraph instance.
        editor:       Editor wrapping the graph for undo/redo and mutations.
        path:         Absolute Path to the .haywire file, or None for untitled.
        unsaved:      True if the graph has in-memory changes not yet written to disk.
        interpreter:  Per-graph Interpreter instance (created on execution start).
        run_settings: Per-entry run policy (e.g. autorestart). Always present;
                      persisted in the haystack TOML under ``[graphs.run]``.
    """

    graph: "HaywireGraph"
    editor: "Editor"
    path: Optional[Path] = None
    unsaved: bool = False
    interpreter: Optional["Interpreter"] = field(default=None, repr=False)
    haystack: "Optional[HaystackState]" = field(default=None, repr=False)
    run_settings: GraphRunSettings = field(default_factory=GraphRunSettings)

    @property
    def binding_id(self) -> str:
        """Stable identifier within the Haystack's ``_entries`` dict.

        ``str(path)`` for saved graphs — required, not incidental: the
        workspace snapshot persists this and reads it back to restore tabs on
        the next launch, so it must survive the process.

        For unsaved graphs it is the graph's own transient ``graph_id``. An
        untitled graph has no file, so no restart can restore it regardless —
        which is why a transient value is safe here and only here. Updates
        automatically when :attr:`path` is assigned on save-as or rename.

        Also serves as this entry's key in
        :class:`haybale_graph_editor.state.GraphAppState`.
        """
        return str(self.path) if self.path is not None else self.graph.graph_id

    @property
    def display_name(self) -> str:
        """Human-readable name for UI labels.

        For file-backed entries returns the stem (no extension); for
        untitled entries returns the graph's ``name`` attribute or
        ``"Untitled"``.
        """
        if self.path is not None:
            return self.path.stem
        return getattr(self.graph, "name", None) or "Untitled"

    @property
    def is_executing(self) -> bool:
        """True if the interpreter is currently executing."""
        return self.interpreter is not None and self.interpreter.is_executing

    def compile(self) -> CompileResult:
        """Build the Interpreter and assemble the graph WITHOUT starting it."""
        if self.is_executing:
            return CompileResult(ok=True, error=None)

        library_state_container = get_library_state_container()
        interpreter = Interpreter(library_state_container=library_state_container)
        try:
            interpreter.load_graph(self.graph)
        except RuntimeError as exc:
            logger.warning(f"Compile failed for graph '{self.display_name}': {exc}")
            self.interpreter = None
            return CompileResult(ok=False, error=str(exc))

        self.interpreter = interpreter
        return CompileResult(ok=True, error=None)

    def start(self) -> None:
        """Start execution on an already-compiled interpreter (dispatch BEGIN_PLAY)."""
        if self.interpreter is None:
            return
        self.interpreter.start_execution()
        logger.info(f"Execution started for graph '{self.display_name}'")

    def start_execution(self) -> CompileResult:
        """Compile then start. Returns the compile verdict."""
        if self.is_executing:
            return CompileResult(ok=True, error=None)
        result = self.compile()
        if result.ok:
            self.start()
        return result

    def stop_execution(self) -> None:
        """Stop execution and shut down the Interpreter."""
        if not self.is_executing:
            return

        assert self.interpreter is not None
        try:
            self.interpreter.stop_execution()
        except Exception as e:
            logger.warning(f"Error stopping execution on '{self.display_name}': {e}")
        self.interpreter = None
        logger.info(f"Execution stopped for graph '{self.display_name}'")

    def save(self, save_as: "Optional[Path]" = None) -> "Optional[str]":
        """Persist this entry via its owning HaystackState.

        Implements the :class:`GraphContainer` protocol's save method.
        Delegates to ``HaystackState._save_entry`` so haystack-internal
        bookkeeping (signals, dirty flag, GraphAppState rekey) all run.

        Returns the new ``binding_id`` if the save-as renamed the entry,
        else ``None``. Failure is signalled by the entry's ``unsaved``
        flag remaining True (the haystack also returns False internally;
        we coerce to None for the protocol contract).
        """
        if self.haystack is None:
            return None  # detached entry — no place to save to
        result = self.haystack._save_entry(self, save_as=save_as)
        if result is False:
            return None
        return result  # None (no rename) or str (new binding_id)
