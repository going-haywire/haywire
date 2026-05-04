"""Reactive[T] value holder.

Phase 1: pure value holder with equality-no-op writes. No subscriber set,
no notification. The `.value` property exists so that read sites in
panels and SessionContext are forward-compatible with Phase 2's auto-
tracking.
"""

from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class Reactive(Generic[T]):
    """A value holder whose `.value` property reads/writes the underlying T.

    Equal-value writes are no-ops. Phase 2 will add a subscriber set and
    ContextVar-based auto-tracking on read.
    """

    def __init__(self, initial: T) -> None:
        self._value: T = initial

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, new: T) -> None:
        if new == self._value:
            return
        self._value = new

    def __repr__(self) -> str:
        return f"Reactive({self._value!r})"
