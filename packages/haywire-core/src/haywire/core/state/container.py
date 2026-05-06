"""LibraryStateContainer — owns the LibraryState instance pool.

Subscribes to LibraryStateRegistry batch lifecycle events. Holds three
internal maps, all keyed by ``class_identity.registry_key``:

  - ``_app``: registry_key → AppState (one instance per class)
  - ``_sessions``: registry_key → dict[session_id, SessionState] (one per (class, session))
  - ``_class_by_registry_key``: registry_key → live class (used to find
    the class behind a key for instantiation and reload)

Keying by registry_key (a stable string) rather than by class object
makes lookups resilient to hot-reload: when a state module is reloaded
its class object is replaced, but the registry_key stays the same, so
callers holding a pre-reload class reference still resolve to the
canonical instance.

Dispatch decision is ``issubclass(cls, SessionState)`` at event time.
See docs/documentation/architecture/session_state.md §3.
"""

from __future__ import annotations

import logging
from typing import TypeVar

from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state.base import AppState, LibraryState, SessionState

logger = logging.getLogger(__name__)

A = TypeVar("A", bound=AppState)
S = TypeVar("S", bound=SessionState)


class LibraryStateContainer:
    """Holds live LibraryState instances across two scopes (app, session).

    Wired to a LibraryStateRegistry via add_batch_event_subscriber:

        registry.add_batch_event_subscriber(container.on_lifecycle_events)

    AppState reactions:
      - CLASS_ADDED       → instantiate, store, call on_enable
      - CLASS_REMOVED     → call on_disable, drop instance
      - CLASS_RELOADED    → on_disable on old, new instance, on_enable on new

    SessionState reactions (fanned out across `_known_session_ids`):
      - CLASS_ADDED       → for each session, instantiate + stamp session_id + on_enable
      - CLASS_REMOVED     → for each session, on_disable + drop
      - CLASS_RELOADED    → for each session, on_disable old, new instance + stamp + on_enable

    Session lifecycle (driven by SessionManager):
      - attach_session(sid) → for each registered SessionState class, instantiate + stamp + on_enable
      - detach_session(sid) → for each registered SessionState class, on_disable + drop
    """

    def __init__(self) -> None:
        # App-scoped: one instance per registered class, keyed by registry_key.
        self._app: dict[str, AppState] = {}
        # Session-scoped: one instance per (class, session_id), keyed by registry_key.
        self._sessions: dict[str, dict[str, SessionState]] = {}
        # Active sessions tracked for fanout on CLASS_ADDED for SessionState classes.
        self._known_session_ids: set[str] = set()
        # registry_key → class. Lets us find the class behind a key for
        # instantiation (attach_session) and lifecycle (CLASS_RELOADED).
        self._class_by_registry_key: dict[str, type[LibraryState]] = {}

    # ------------------------------------------------------------------
    # Public lookup API — used by AppDataNamespace
    # ------------------------------------------------------------------

    def __getitem__(self, cls: type[A]) -> A:
        try:
            return self._app[cls.class_identity.registry_key]  # type: ignore[return-value]
        except KeyError:
            raise KeyError(
                f"No AppState instance registered for class {cls.__name__}. "
                f"Either the owning library is not enabled, or the class is not "
                f"a registered AppState subclass."
            ) from None

    def get(self, cls: type[A]) -> A | None:
        return self._app.get(cls.class_identity.registry_key)  # type: ignore[return-value]

    def __contains__(self, cls: type) -> bool:
        return cls.class_identity.registry_key in self._app

    # ------------------------------------------------------------------
    # Public lookup API — used by SessionDataNamespace
    # ------------------------------------------------------------------

    def get_session(self, cls: type[S], session_id: str) -> S:
        try:
            bag = self._sessions[cls.class_identity.registry_key]
        except KeyError:
            raise KeyError(
                f"No SessionState class {cls.__name__} is registered. "
                f"Either the owning library is not enabled, or the class is not "
                f"a registered SessionState subclass."
            ) from None
        try:
            return bag[session_id]  # type: ignore[return-value]
        except KeyError:
            raise KeyError(
                f"SessionState {cls.__name__} has no instance for session {session_id!r}. "
                f"The session may not be attached, or it has been detached."
            ) from None

    def get_session_optional(self, cls: type[S], session_id: str) -> S | None:
        bag = self._sessions.get(cls.class_identity.registry_key)
        if bag is None:
            return None
        return bag.get(session_id)  # type: ignore[return-value]

    def has_session(self, cls: type[S], session_id: str) -> bool:
        bag = self._sessions.get(cls.class_identity.registry_key)
        if bag is None:
            return False
        return session_id in bag

    # ------------------------------------------------------------------
    # Session lifecycle — called by SessionManager
    # ------------------------------------------------------------------

    def attach_session(self, session_id: str) -> None:
        """Instantiate one of every registered SessionState class for this session."""
        if session_id in self._known_session_ids:
            return  # idempotent
        self._known_session_ids.add(session_id)
        for registry_key, bag in self._sessions.items():
            cls = self._class_by_registry_key.get(registry_key)
            if cls is None or not issubclass(cls, SessionState):
                continue
            self._instantiate_session_state(cls, bag, session_id)

    def detach_session(self, session_id: str) -> None:
        """Tear down every per-session instance for this session."""
        if session_id not in self._known_session_ids:
            return
        self._known_session_ids.discard(session_id)
        for bag in self._sessions.values():
            inst = bag.pop(session_id, None)
            if inst is not None:
                self._call_on_disable(inst)

    # ------------------------------------------------------------------
    # Lifecycle event handler — registered with LibraryStateRegistry
    # ------------------------------------------------------------------

    def on_lifecycle_events(self, events: list[LifeCycleEvent]) -> None:
        for event in events:
            try:
                self._dispatch(event)
            except Exception as exc:
                logger.error("LibraryStateContainer error handling %s: %s", event, exc, exc_info=True)

    def _dispatch(self, event: LifeCycleEvent) -> None:
        et = event.event_type
        if et is LifeCycleEventType.CLASS_ADDED:
            self._add(event)
        elif et is LifeCycleEventType.CLASS_REMOVED:
            self._remove(event)
        elif et is LifeCycleEventType.CLASS_RELOADED:
            self._reload(event)

    # ------------------------------------------------------------------
    # Scope-dispatched lifecycle handlers
    # ------------------------------------------------------------------

    def _add(self, event: LifeCycleEvent) -> None:
        cls = event.affected_class
        if cls is None:
            return
        if issubclass(cls, SessionState):
            self._add_session_class(cls, event.registry_key)
        elif issubclass(cls, AppState):
            self._add_app_class(cls, event.registry_key)
        else:
            logger.warning(
                "LibraryStateContainer ignored class %s for %s: not a subclass of "
                "AppState or SessionState — direct LibraryState subclasses are not "
                "supported. Pick AppState (app-global) or SessionState (per-session).",
                cls.__name__,
                event.registry_key,
            )

    def _remove(self, event: LifeCycleEvent) -> None:
        old_cls = self._class_by_registry_key.pop(event.registry_key, None)
        if old_cls is None:
            # No reverse-map entry. Either the registry_key was never added,
            # or the class went through the bypass branch in _add (direct
            # LibraryState subclass) which already logged a warning and never
            # populated _class_by_registry_key. Either way nothing to do.
            return
        if issubclass(old_cls, SessionState):
            self._remove_session_class(event.registry_key)
        elif issubclass(old_cls, AppState):
            self._remove_app_class(event.registry_key)
        else:
            # Defensive: a class admitted via the bypass branch never lands in
            # _class_by_registry_key, so this branch is not reachable in
            # practice. Log if it ever does, to surface unexpected state.
            logger.warning(
                "LibraryStateContainer ignored class %s for %s: not a subclass of "
                "AppState or SessionState — direct LibraryState subclasses are not "
                "supported. Pick AppState (app-global) or SessionState (per-session).",
                old_cls.__name__,
                event.registry_key,
            )

    def _reload(self, event: LifeCycleEvent) -> None:
        # Drop the OLD class first (whichever scope), then add the NEW one.
        old_cls = self._class_by_registry_key.pop(event.registry_key, None)
        if old_cls is not None:
            if issubclass(old_cls, SessionState):
                self._remove_session_class(event.registry_key)
            elif issubclass(old_cls, AppState):
                self._remove_app_class(event.registry_key)
            else:
                # Same defensive note as in _remove: bypass classes never reach
                # _class_by_registry_key, but log if state ever drifts here.
                logger.warning(
                    "LibraryStateContainer ignored class %s for %s: not a subclass of "
                    "AppState or SessionState — direct LibraryState subclasses are not "
                    "supported. Pick AppState (app-global) or SessionState (per-session).",
                    old_cls.__name__,
                    event.registry_key,
                )

        new_cls = event.affected_class
        if new_cls is None:
            return
        if issubclass(new_cls, SessionState):
            self._add_session_class(new_cls, event.registry_key)
        elif issubclass(new_cls, AppState):
            self._add_app_class(new_cls, event.registry_key)
        else:
            logger.warning(
                "LibraryStateContainer ignored class %s for %s: not a subclass of "
                "AppState or SessionState — direct LibraryState subclasses are not "
                "supported. Pick AppState (app-global) or SessionState (per-session).",
                new_cls.__name__,
                event.registry_key,
            )

    # ------------------------------------------------------------------
    # AppState scope helpers
    # ------------------------------------------------------------------

    def _add_app_class(self, cls: type[AppState], registry_key: str) -> None:
        if registry_key in self._app:
            return  # idempotent
        instance = cls()
        self._app[registry_key] = instance
        self._class_by_registry_key[registry_key] = cls
        self._call_on_enable(instance)

    def _remove_app_class(self, registry_key: str) -> None:
        instance = self._app.pop(registry_key, None)
        if instance is not None:
            self._call_on_disable(instance)

    # ------------------------------------------------------------------
    # SessionState scope helpers
    # ------------------------------------------------------------------

    def _add_session_class(self, cls: type[SessionState], registry_key: str) -> None:
        if registry_key in self._sessions:
            return  # idempotent
        bag: dict[str, SessionState] = {}
        self._sessions[registry_key] = bag
        self._class_by_registry_key[registry_key] = cls
        # Fan out across known sessions.
        for sid in self._known_session_ids:
            self._instantiate_session_state(cls, bag, sid)

    def _remove_session_class(self, registry_key: str) -> None:
        bag = self._sessions.pop(registry_key, {})
        for inst in bag.values():
            self._call_on_disable(inst)

    def _instantiate_session_state(
        self,
        cls: type[SessionState],
        bag: dict[str, SessionState],
        session_id: str,
    ) -> None:
        try:
            instance = cls()
        except Exception as exc:
            logger.error(
                "Failed to instantiate SessionState %s for session %s: %s",
                cls.__name__,
                session_id,
                exc,
                exc_info=True,
            )
            return
        instance.session_id = session_id  # stamp before on_enable
        bag[session_id] = instance
        self._call_on_enable(instance)

    # ------------------------------------------------------------------
    # Hook callers — duck-typed, exception-tolerant
    # ------------------------------------------------------------------

    @staticmethod
    def _call_on_enable(instance: LibraryState) -> None:
        hook = getattr(instance, "on_enable", None)
        if callable(hook):
            try:
                hook()
            except Exception as exc:
                logger.error("%s.on_enable raised: %s", type(instance).__name__, exc, exc_info=True)

    @staticmethod
    def _call_on_disable(instance: LibraryState) -> None:
        hook = getattr(instance, "on_disable", None)
        if callable(hook):
            try:
                hook()
            except Exception as exc:
                logger.error("%s.on_disable raised: %s", type(instance).__name__, exc, exc_info=True)
