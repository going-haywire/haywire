"""Protocols for the graph editor library.

GraphContainer is the structural contract a source library must
implement (or satisfy structurally) to host a graph in GraphEditor.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from haywire.core.graph.editor import Editor


@runtime_checkable
class GraphContainer(Protocol):
    """One open graph, ready to be edited by GraphEditor.

    A source library (e.g. haybale-haystack) constructs containers and
    registers them in :class:`GraphAppState`. GraphEditor reads
    containers by binding_id; it never knows which source produced one.

    Attributes:
        binding_id: Stable identifier within :class:`GraphAppState`.
            Workspace-persisted (the wrapper's binding_id field). For a
            saved graph this is typically the file path string; for an
            unsaved graph a synthetic token assigned by the source.
        editor: The graph Editor (undo/redo, mutation API).
        path: Absolute filesystem path, or None for unsaved/in-memory.
        unsaved: True when in-memory state differs from disk.
        display_name: Human label for tab and header chrome.
    """

    binding_id: str
    editor: "Editor"
    path: Optional[Path]
    unsaved: bool
    display_name: str

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
