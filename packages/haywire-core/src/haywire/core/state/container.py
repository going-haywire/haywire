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
See docs/architecture/session-and-state/session-and-state-arch.md §3.
"""

from __future__ import annotations

import logging
import weakref
from typing import TYPE_CHECKING, TypeVar

from haywire.core.errors import HaywireException
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state.base import AppState, LibraryState, SessionState
from haywire.core.state.registry import LibraryStateRegistry

if TYPE_CHECKING:
    from haywire.core.library.base import BaseLibrary
    from haywire.core.library.registry import LibraryRegistry
    from haywire.core.session.session import Session
    from haywire.core.session.session_manager import SessionManager

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
      - attach_session_with_ref(sid, session) → like attach_session, but also stamps
        ``instance.session = weakref.ref(session)`` on each SessionState before on_enable
      - detach_session(sid) → for each registered SessionState class, on_disable + drop
      - bind_session_manager(manager) → stamps ``instance._session_manager = weakref.ref(manager)``
        on every AppState (existing + future); called once by SessionManager.__init__
    """

    def __init__(self, state_registry: LibraryStateRegistry) -> None:
        # Held-by-construction so on_library_enabled doesn't need to be called
        # with the registry every time. Container queries it during catch-up.
        self._state_registry = state_registry
        # App-scoped: one instance per registered class, keyed by registry_key.
        self._app: dict[str, AppState] = {}
        # Session-scoped: one instance per (class, session_id), keyed by registry_key.
        self._sessions: dict[str, dict[str, SessionState]] = {}
        # Active sessions tracked for fanout on CLASS_ADDED for SessionState classes.
        self._known_session_ids: set[str] = set()
        # registry_key → class. Lets us find the class behind a key for
        # instantiation (attach_session) and lifecycle (CLASS_RELOADED).
        self._class_by_registry_key: dict[str, type[LibraryState]] = {}
        # Library ids the container has been told about via on_library_enabled.
        # Events whose library_identity.id is NOT in this set are dropped by
        # on_lifecycle_events — they belong to a library whose enable() is still
        # in progress, and acting on them now risks calling on_enable before the
        # rest of the library's components (types, nodes, …) are registered.
        self._enabled_library_ids: set[str] = set()
        # Set by bind_session_manager (called once by SessionManager.__init__).
        # Stays None until then; _add_app_class only stamps AppStates when
        # this is non-None. See bind_session_manager docstring.
        self._manager_ref: "weakref.ReferenceType[SessionManager] | None" = None

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

    def __contains__(self, cls: type[LibraryState]) -> bool:
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

    def attach_session_with_ref(self, session_id: str, session: "Session") -> None:
        """Same as `attach_session`, but also stamps `self.session = weakref.ref(session)`
        on every SessionState instance before `on_enable` runs.

        Called by `SessionManager.create_session`.
        """
        if session_id in self._known_session_ids:
            return
        self._known_session_ids.add(session_id)
        for registry_key, bag in self._sessions.items():
            cls = self._class_by_registry_key.get(registry_key)
            if cls is None or not issubclass(cls, SessionState):
                continue
            self._instantiate_session_state(cls, bag, session_id, session)

    def bind_session_manager(self, manager: "SessionManager") -> None:
        """Stamp `_session_manager` weakref on every present and future AppState.

        Called once by SessionManager.__init__ right after constructing the
        container. A second call is permitted and idempotent in effect — it
        replaces `self._manager_ref` and re-stamps every existing AppState
        with the new ref. This is intentional: a test or a hot-restart path
        that rebuilds the SessionManager can re-bind without churn.

        After this call, `_add_app_class` stamps newly-added AppStates with
        the same ref.
        """
        self._manager_ref = weakref.ref(manager)
        for app_state in self._app.values():
            app_state._session_manager = self._manager_ref

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
            # Drop events for libraries we haven't been told about yet
            # (see _enabled_library_ids docstring on __init__). During startup,
            # CLASS_ADDED events for every library fire before any library is
            # marked enabled; the container would otherwise instantiate state
            # mid-library-load. The catch-up in on_library_enabled replays
            # those classes once the library is fully enabled.
            if event.library_identity.id not in self._enabled_library_ids:
                continue
            try:
                self._dispatch(event)
            except Exception as exc:
                logger.error("LibraryStateContainer error handling %s: %s", event, exc, exc_info=True)

    # ------------------------------------------------------------------
    # Lifecycle wiring — called once by LibrarySystemService.initialize
    # AFTER enable_all_libraries() has returned.
    # ------------------------------------------------------------------

    def bind_to_lifecycle(self, library_registry: "LibraryRegistry") -> None:
        """Subscribe to the three channels the container reacts to.

        Called by the orchestrator (``LibrarySystemService.initialize``)
        once at startup, AFTER ``enable_all_libraries()`` has returned —
        timing matters: subscribing before would cause the container to
        process CLASS_ADDED events fired during each library's enable(),
        which is the load-order race this whole machinery exists to fix.

        Subscribes to:
          1. State registry batch events — for future hot-reload of
             classes within already-enabled libraries.
          2. Library-enabled callback — for the startup catch-up loop
             and for future hot-installed libraries.
          3. Library-disabled callback — to drop the library id from
             ``_enabled_library_ids`` so subsequent events for it are
             filtered out.
        """
        self._state_registry.add_batch_event_subscriber(self.on_lifecycle_events)
        library_registry.add_library_enabled_callback(self.on_library_enabled)
        library_registry.add_library_disabled_callback(self.on_library_disabled)

    # ------------------------------------------------------------------
    # Per-library catch-up — called by LibraryRegistry after library.enable()
    # ------------------------------------------------------------------

    def on_library_enabled(self, library: "BaseLibrary") -> None:
        """Catch up after *library* finished enabling.

        Queries the held state registry for every state class belonging to
        this library and instantiates / wires each as if a ``CLASS_ADDED``
        event had fired. Then records the library id so future hot-reload
        events for its classes pass the filter in ``on_lifecycle_events``.

        Synthesizes ``CLASS_ADDED`` events and routes through ``_dispatch``
        so AppState vs SessionState branching reuses the existing path.

        Idempotent: a second call with the same library is a no-op for
        already-instantiated classes (``_add_app_class`` /
        ``_add_session_class`` early-return when the registry_key is
        already present).

        Re-enable: when a library is disabled and then enabled again, the
        previous disable has cleared the library id from
        ``_enabled_library_ids`` (via ``on_library_disabled``), so the
        CLASS_ADDED events fired during the new ``enable()``'s
        ``_attach_to_registries`` are dropped by the filter. This catch-up
        then re-instantiates the state classes — mirroring first-time
        enable behaviour exactly.
        """
        # Mark BEFORE dispatching so the synthetic events pass the filter.
        self._mark_library_enabled(library.identity.id)
        classes = self._state_registry.get_classes_for_library(library.identity)
        for registry_key, cls in classes.items():
            event = LifeCycleEvent(
                registry_key=registry_key,
                event_type=LifeCycleEventType.CLASS_ADDED,
                affected_class=cls,
                library_identity=library.identity,
            )
            try:
                self._dispatch(event)
            except Exception as exc:
                logger.error(
                    "LibraryStateContainer catch-up failed for %s in library %s: %s",
                    cls.__name__,
                    library.identity.label,
                    exc,
                    exc_info=True,
                )

    def on_library_disabled(self, library: "BaseLibrary") -> None:
        """Drop *library*'s id from ``_enabled_library_ids`` after its
        ``disable()`` completes.

        Timing: the CLASS_REMOVED events fired during ``library.disable()``
        have already drained through ``on_lifecycle_events`` by the time
        ``LibraryRegistry`` fires the disabled callback (callback runs as
        the last step of ``disable_library`` AFTER ``library.disable()``
        returns). At that point the container's ``_app`` / ``_sessions``
        dicts no longer hold any of the library's instances, so dropping
        the id is the only remaining bookkeeping.

        After this call, any further events carrying this library's id
        are dropped by the filter — including the CLASS_ADDED events
        that fire when the library is re-enabled later. The re-enable
        catch-up via ``on_library_enabled`` is what re-instantiates the
        state classes, mirroring first-time enable.
        """
        self._mark_library_disabled(library.identity.id)

    def _mark_library_enabled(self, library_id: str) -> None:
        """Record that *library_id* is enabled so events for it pass the filter.

        Called by ``on_library_enabled`` for production use. Tests that drive
        ``on_lifecycle_events`` directly without going through a real
        ``BaseLibrary`` / ``LibraryRegistry`` use this lower-level marker.
        """
        self._enabled_library_ids.add(library_id)

    def _mark_library_disabled(self, library_id: str) -> None:
        """Mirror of ``_mark_library_enabled``. Removes *library_id* from the
        set so subsequent events for that library are dropped.

        Called by ``on_library_disabled`` for production use. Tests use this
        lower-level marker when bypassing ``BaseLibrary`` / ``LibraryRegistry``.
        Idempotent — ``set.discard`` silently no-ops if the id isn't present.
        """
        self._enabled_library_ids.discard(library_id)

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
        if self._manager_ref is not None:
            instance._session_manager = self._manager_ref
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
        session: "Session | None" = None,
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
        if session is not None:
            instance.session = weakref.ref(session)
        bag[session_id] = instance
        self._call_on_enable(instance)

    # ------------------------------------------------------------------
    # Hook callers — fault-isolated via HaywireException wrapping
    # ------------------------------------------------------------------

    @staticmethod
    def _call_on_enable(instance: LibraryState) -> None:
        try:
            instance.on_enable()
        except Exception as exc:
            LibraryStateContainer._wrap_hook_failure(instance, exc, "on_enable")

    @staticmethod
    def _call_on_disable(instance: LibraryState) -> None:
        try:
            instance.on_disable()
        except Exception as exc:
            LibraryStateContainer._wrap_hook_failure(instance, exc, "on_disable")

    @staticmethod
    def _wrap_hook_failure(instance: LibraryState, exc: Exception, hook: str) -> None:
        """Wrap a raising LibraryState lifecycle hook into a HaywireException."""
        error = HaywireException.from_exception(
            exception=exc,
            operation=f"LibraryState.{hook}",
            message=f"{type(instance).__name__}.{hook} raised",
        ).enrich(
            registry_key=instance.class_identity.registry_key,
            library_identity=instance.class_library,
        )
        error.log(logger)
