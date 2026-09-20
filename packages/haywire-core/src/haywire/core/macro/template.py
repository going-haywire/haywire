"""One macro file, parsed and under the component contract."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from haywire.core.library.identity import LibraryIdentity
from haywire.core.node.identity import NodeIdentity


@dataclass
class MacroTemplate:
    """A ``.hwm`` document registered as a component.

    Carries what a placement needs to instantiate an interior — the document's
    ``nodes``/``edges``/``subgraphs`` tables — behind the same
    ``class_identity``/``class_library`` pair a node class exposes, so the
    docs generator, the farmhand helpers and the add-node menu read it without
    knowing it is a file.

    Three things share the name and are not the same: the file on disk, this
    template, and each placement's live ``SubgraphDefinition``.
    """

    document: dict[str, Any]
    path: Path
    content_hash: str
    identity: NodeIdentity
    library: LibraryIdentity

    @property
    def class_identity(self) -> NodeIdentity:
        return self.identity

    @property
    def class_library(self) -> LibraryIdentity:
        return self.library

    @property
    def nodes(self) -> dict[str, Any]:
        """The interior's node table, keyed by the document's own node ids."""
        return self.document.get("nodes", {})

    @property
    def edges(self) -> dict[str, Any]:
        return self.document.get("edges", {})

    @property
    def subgraphs(self) -> dict[str, Any]:
        """Nested Subgraph definitions, instantiated recursively with the interior."""
        return self.document.get("subgraphs", {})
