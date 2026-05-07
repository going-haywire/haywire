"""Library-owned runtime state — see internals/documentation/architecture/library_state.md."""

from haywire.core.state.base import AppState, LibraryState, SessionState
from haywire.core.state.container import LibraryStateContainer
from haywire.core.state.data_namespace import (
    AppDataNamespace,
    SessionDataNamespace,
)
from haywire.core.state.decorator import state
from haywire.core.state.identity import LibraryStateClassIdentity
from haywire.core.state.registry import LibraryStateRegistry

__all__ = [
    "AppDataNamespace",
    "AppState",
    "LibraryState",
    "LibraryStateClassIdentity",
    "LibraryStateContainer",
    "LibraryStateRegistry",
    "SessionDataNamespace",
    "SessionState",
    "state",
]
