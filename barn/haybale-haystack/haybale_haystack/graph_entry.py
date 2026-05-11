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

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph as HaywireGraph
    from haywire.core.execution.interpreter import Interpreter
    from haywire.core.graph.editor import Editor

logger = logging.getLogger(__name__)


@dataclass
class GraphEntry:
    """Holds all runtime state for a single open graph.

    Attributes:
        graph:        The BaseGraph instance.
        editor:       Editor wrapping the graph for undo/redo and mutations.
        path:         Absolute Path to the .haywire file, or None for untitled.
        unsaved:      True if the graph has in-memory changes not yet written to disk.
        interpreter:  Per-graph Interpreter instance (created on execution start).
        _unsaved_id:  Synthetic ``__unsaved_N__`` token, set by Haystack on
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

    def start_execution(self) -> None:
        """Create an Interpreter and start execution for this graph."""
        if self.is_executing:
            return

        from haywire.core.di.context import get_library_state_container
        from haywire.core.execution.interpreter import Interpreter

        library_state_container = get_library_state_container()
        self.interpreter = Interpreter(library_state_container=library_state_container)
        self.interpreter.load_graph(self.graph)
        self.interpreter.start_execution()
        logger.info(f"Execution started for graph '{self.display_name}'")

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
