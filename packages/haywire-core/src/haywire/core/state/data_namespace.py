"""Typed proxies exposing the LibraryStateContainer.

Two namespaces, scope-bound:

  AppDataNamespace      ↔ AppState lookups       — used as ctx.app_data on
                                                   SessionContext + ExecutionContext.
  SessionDataNamespace  ↔ SessionState lookups   — used as ctx.data on
                                                   SessionContext only.

Each namespace binds its TypeVar tightly so a wrong-scope lookup is a
type-check error at the call site. Each access does a live container
lookup — no caching. Phase 2 reactive auto-tracking will subscribe
through the container, not these proxies.

See docs/documentation/architecture/session_state.md §2.3.
"""

from __future__ import annotations

from typing import TypeVar

from haywire.core.state.base import AppState, SessionState
from haywire.core.state.container import LibraryStateContainer

A = TypeVar("A", bound=AppState)
S = TypeVar("S", bound=SessionState)


class AppDataNamespace:
    """Typed proxy over a LibraryStateContainer for AppState lookups."""

    __slots__ = ("_container",)

    def __init__(self, container: LibraryStateContainer) -> None:
        self._container = container

    def __getitem__(self, cls: type[A]) -> A:
        return self._container[cls]

    def get(self, cls: type[A]) -> A | None:
        return self._container.get(cls)

    def __contains__(self, cls: type) -> bool:
        return cls in self._container


class SessionDataNamespace:
    """Typed proxy over a LibraryStateContainer for SessionState lookups, bound to one session."""

    __slots__ = ("_container", "_session_id")

    def __init__(self, container: LibraryStateContainer, session_id: str) -> None:
        self._container = container
        self._session_id = session_id

    def __getitem__(self, cls: type[S]) -> S:
        return self._container.get_session(cls, self._session_id)

    def get(self, cls: type[S]) -> S | None:
        return self._container.get_session_optional(cls, self._session_id)

    def __contains__(self, cls: type) -> bool:
        return self._container.has_session(cls, self._session_id)
