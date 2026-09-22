from dataclasses import dataclass
from typing import Optional

from haywire.core.library.identity import LibraryIdentity
from .identity import NodeIdentity


@dataclass(frozen=True)
class NodeInfo:
    """Composed node metadata used by NodeFactory discovery APIs."""

    identity: NodeIdentity
    library: Optional[LibraryIdentity]
    is_macro: bool = False
    """Whether this entry is a macro document rather than a node class.

    Decided where the info is built, so a consumer needs neither the registry
    nor ``is_macro_key`` to tell the two apart. Unrelated to
    ``NodeIdentity._is_macro_node``, which marks the single class that stands
    for a placement.
    """
