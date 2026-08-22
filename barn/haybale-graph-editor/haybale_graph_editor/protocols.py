"""Protocols for the graph editor library.

GraphContainer is the base class a source library must subclass to host a
graph in GraphEditor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from haywire.core.graph.editor import Editor


class GraphContainer(ABC):
    """One open graph, ready to be edited by GraphEditor.

    A source library (e.g. haybale-haystack) subclasses this, constructs
    containers and registers them in :class:`GraphAppState`. GraphEditor
    reads containers by binding_id; it never knows which source produced
    one.

    Attributes:
        binding_id: Stable identifier within :class:`GraphAppState`.
            Workspace-persisted (the wrapper's binding_id field). For a
            saved graph this is typically the file path string; for an
            unsaved graph a synthetic token assigned by the source.
        editor: The graph Editor (undo/redo, mutation API).
        path: Absolute filesystem path, or None for unsaved/in-memory.
        unsaved: True when in-memory state differs from disk.
        display_name: Human label for tab and header chrome.

    ``editor`` / ``path`` / ``unsaved`` are annotations, NOT abstract
    properties: a subclass supplies them as plain data (``GraphEntry`` is a
    dataclass, and dataclass fields do not satisfy ``@abstractmethod`` —
    ABC clears ``__abstractmethods__`` on class creation, long before a
    field exists on any instance). ``binding_id`` and ``display_name`` are
    abstract because they are genuinely computed.
    """

    editor: "Editor"
    path: Optional[Path]
    unsaved: bool

    @property
    @abstractmethod
    def binding_id(self) -> str: ...

    @property
    @abstractmethod
    def display_name(self) -> str: ...

    @abstractmethod
    def save(self, save_as: Optional[Path] = None) -> Optional[str]:
        """Persist the container.

        Args:
            save_as: When provided and different from ``self.path``,
                this is a save-as: the container's identity changes.

        Returns:
            New ``binding_id`` if the save renamed/rekeyed the container
            (typically only on save-as). ``None`` otherwise — including
            when the save failed; callers detect failure via the
            unchanged ``unsaved`` flag or surface dialog.
        """
        ...
