"""DataNamespace — typed proxy exposing the LibraryStateContainer.

Used as the `data` attribute on both SessionContext and ExecutionContext.
The only access pattern is class-keyed:

    ctx.data[MidiPool].devices.value     # raises KeyError if MidiPool not registered
    ctx.data.get(MidiPool)               # returns Optional[MidiPool]

Type-checking: __getitem__ is generic over T = TypeVar('T', bound=LibraryState),
so type-checkers infer the correct return type.
"""

from __future__ import annotations

from typing import TypeVar

from haywire.core.state.base import LibraryState
from haywire.core.state.container import LibraryStateContainer

T = TypeVar("T", bound=LibraryState)


class DataNamespace:
    """Typed proxy over a LibraryStateContainer.

    Pure indirection — every access does a live container lookup. No caching,
    no notifications. Phase 2 reactive auto-tracking will subscribe through
    the container, not this proxy.
    """

    __slots__ = ("_container",)

    def __init__(self, container: LibraryStateContainer) -> None:
        self._container = container

    def __getitem__(self, cls: type[T]) -> T:
        return self._container[cls]

    def get(self, cls: type[T]) -> T | None:
        return self._container.get(cls)

    def __contains__(self, cls: type) -> bool:
        return cls in self._container
