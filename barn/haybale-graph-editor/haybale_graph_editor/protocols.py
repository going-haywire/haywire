"""Protocols for the graph editor library.

GraphContainer is the base class a source library must subclass to host a
graph in GraphEditor. SubgraphContainer is the one the editor supplies itself,
so stepping inside a Group needs no source library at all.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from haywire.core.graph.editor import Editor
    from haywire.core.graph.subgraph import SubgraphDefinition
    from haywire.core.node.factory import NodeFactory

#: Separator between a host's ``binding_id`` and a Subgraph key.
SUBGRAPH_BINDING_SEPARATOR = "#"


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


class SubgraphContainer(GraphContainer):
    """One Subgraph, open in the editor as if it were a document.

    The editor builds these itself when the user steps inside a Group — no
    source library is involved, because a Group belongs to the host file rather
    than to one of its own. Everything that belongs to the file therefore
    delegates to the host container: ``path``, ``unsaved`` and ``save()`` are
    the host's answers, and the graph editor records on the host's undo history,
    so Save, the dirty dot and Ctrl+Z all reach the whole file at any depth.

    ``binding_id`` is synthetic — ``<host binding_id>#<subgraph key>`` — which
    :class:`GraphContainer` already allows ("for an unsaved graph a synthetic
    token assigned by the source").

    Example::

        container = SubgraphContainer(host, definition, node_factory)
        app_state.register(container)
        wrapper.repayload(container.binding_id, new_label=container.display_name)
    """

    def __init__(
        self,
        host: GraphContainer,
        definition: "SubgraphDefinition",
        node_factory: "NodeFactory",
    ):
        """Open ``definition`` for editing, saving through ``host``.

        Args:
            host: The container whose file holds this Subgraph. May itself be a
                ``SubgraphContainer``, which is what makes nesting work.
            definition: The Subgraph to edit.
            node_factory: Factory for this Subgraph's editor.
        """
        from haywire.core.graph.editor import Editor

        self.host = host
        self.definition = definition
        # The host's history, not one of its own: an edit inside a Group is an
        # edit to the file holding it, and undoes in order with the rest.
        self.editor = Editor(definition, node_factory, history_manager=host.editor.history_manager)

    @staticmethod
    def binding_id_for(host: GraphContainer, definition: "SubgraphDefinition") -> str:
        """Return the ``binding_id`` a container over ``definition`` inside ``host`` has.

        Lets a caller look a Subgraph up in :class:`GraphAppState` before
        building a container for it, so re-entering an open Group finds the
        container already editing it instead of replacing it with a fresh one
        (which would drop that Group's undo history).
        """
        return f"{host.binding_id}{SUBGRAPH_BINDING_SEPARATOR}{definition.key}"

    @property
    def binding_id(self) -> str:
        return self.binding_id_for(self.host, self.definition)

    @property
    def display_name(self) -> str:
        return self.definition.label

    @property
    def path(self) -> Optional[Path]:  # type: ignore[override]
        """The host's path — a Subgraph has no file of its own."""
        return self.host.path

    @property
    def unsaved(self) -> bool:  # type: ignore[override]
        """The host's dirty state: editing a Subgraph dirties the file holding it."""
        return self.host.unsaved

    @property
    def root_host(self) -> GraphContainer:
        """The document container at the top of this Subgraph's descent stack."""
        container: GraphContainer = self
        while isinstance(container, SubgraphContainer):
            container = container.host
        return container

    def save(self, save_as: Optional[Path] = None) -> Optional[str]:
        """Save the host file; a Subgraph is serialized as part of it.

        Returns the host's new ``binding_id`` when the save rekeyed it, so the
        caller can re-derive this container's own id from it.
        """
        return self.host.save(save_as)
