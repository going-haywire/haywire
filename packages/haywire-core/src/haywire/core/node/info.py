from dataclasses import dataclass
from typing import Optional

from haywire.core.library.identity import LibraryIdentity
from .identity import NodeIdentity


@dataclass(frozen=True)
class NodeSourceInfo:
    """Python class source metadata for a node."""

    class_name: str
    module: str


@dataclass(frozen=True)
class NodeInfo:
    """Composed node metadata used by NodeFactory discovery APIs."""

    identity: NodeIdentity
    library: Optional[LibraryIdentity]
    source: NodeSourceInfo
