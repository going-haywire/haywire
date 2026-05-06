"""reactive_field(): a descriptor whose access mode determines its return type.

- Class-level access (e.g., SomeState.some_field) → ReactivePath.
- Instance-level access (e.g., state.some_field) → Reactive[T] container.

The class hosting reactive_field() descriptors is responsible for
initializing the per-instance Reactive[T] containers in __init__ /
__post_init__. This module exposes `iter_reactive_fields(cls)` for that
purpose.
"""

from __future__ import annotations

from typing import Any, Generic, Iterator, TypeVar

from haywire.ui.reactive.path import ReactivePath
from haywire.ui.reactive.reactive import Reactive

T = TypeVar("T")


class _ReactiveDescriptor(Generic[T]):
    """Internal descriptor returned by reactive_field()."""

    def __init__(self, initial: T) -> None:
        self._initial: T = initial
        self._attr_name: str | None = None  # populated by __set_name__

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            assert self._attr_name is not None, "descriptor missing __set_name__"
            return ReactivePath(owner=owner, attr=self._attr_name)
        # Instance access — return the per-instance Reactive[T] container.
        # Hosting class is responsible for populating instance.__dict__[attr_name].
        assert self._attr_name is not None
        return instance.__dict__[self._attr_name]


def reactive_field(initial: T) -> Reactive[T]:
    """Declare a reactive field on a class.

    Usage:
        class SessionContext:
            active_node: Reactive[NodeWrapper | None] = reactive_field(None)

    The annotation type (`Reactive[T]`) describes instance-level access.
    Class-level access (`SessionContext.active_node`) returns a
    ReactivePath instead — the descriptor handles the dispatch.

    The hosting class must initialize per-instance Reactive[T] containers,
    typically by iterating `iter_reactive_fields(cls)` in __init__ or
    __post_init__.
    """
    # Lie to mypy: the annotation is what panels see (Reactive[T]).
    # The runtime returns a descriptor.
    return _ReactiveDescriptor(initial)  # type: ignore[return-value]


def iter_reactive_fields(cls: type) -> Iterator[tuple[str, Any]]:
    """Yield (attr_name, initial_value) for each reactive_field() on cls.

    Walks the MRO so subclasses inherit reactive fields from their bases.
    If a subclass shadows a base-class field, only the subclass's value
    is yielded (most-derived wins).

    Used by hosting classes to initialize per-instance Reactive[T]
    containers.
    """
    seen: set[str] = set()
    for klass in cls.__mro__:
        for name, attr in klass.__dict__.items():
            if isinstance(attr, _ReactiveDescriptor) and name not in seen:
                seen.add(name)
                yield name, attr._initial
