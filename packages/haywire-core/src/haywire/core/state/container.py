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

Two-phase lifecycle
-------------------
CLASS_ADDED events from ``on_lifecycle_events`` only **instantiate** the
state class (storing the instance in ``_app`` / session bags). ``on_enable``
is deferred until ``on_library_enabled`` fires, which happens after the
owning library's ``enable()`` has fully returned and all its components
(settings, types, nodes, panels, editors) are registered.

This means a state instance is reachable via ``ctx.app_data[Cls]`` as
soon as its class is scanned — even before ``on_enable`` has resolved its
DI dependencies — so editors and panels that draw during the same
``_attach_to_registries`` pass see a valid (default-initialised) object
rather than a KeyError.

CLASS_RELOADED events (hot-reload of an already-enabled library) still
do the full disable-old / instantiate-new / enable-new cycle atomically
inside ``on_lifecycle_events``, because by that point ``on_library_enabled``
has already run for the library and the full environment is available.

``_enabled_library_ids`` now gates only ``on_enable`` calls, not
instantiation.

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
      - CLASS_ADDED       → instantiate + store (on_enable deferred to on_library_enabled)
      - CLASS_REMOVED     → call on_disable, drop instance
      - CLASS_RELOADED    → on_disable on old, new instance, on_enable on new

    SessionState reactions (fanned out across `_known_session_ids`):
      - CLASS_ADDED       → for each session, instantiate + stamp session_id
                            (on_enable deferred to on_library_enabled)
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
        # session_id → Session ref for sessions attached via attach_session_with_ref.
        # Used to stamp instance.session when a new SessionState class is added
        # after the session is already alive (re-enable of a library).
        self._session_refs: "dict[str, weakref.ReferenceType[Session]]" = {}
        # registry_key → class. Lets us find the class behind a key for
        # instantiation (attach_session) and lifecycle (CLASS_RELOADED).
        self._class_by_registry_key: dict[str, type[LibraryState]] = {}
        # Library ids for which on_library_enabled has fired. CLASS_ADDED
        # events from on_lifecycle_events check this: if the library is already
        # enabled (hot-install / re-scan), on_enable fires immediately;
        # otherwise it is deferred to on_library_enabled.
        # CLASS_RELOADED always does the full cycle regardless of this set.
        self._enabled_library_ids: set[str] = set()
        # registry_keys for which on_enable has already been called. Guards
        # on_library_enabled against double-firing on_enable when it is
        # called more than once for the same library (idempotency).
        self._enabled_registry_keys: set[str] = set()
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

        Called by `SessionManager.create_session`. Also stores the weakref so
        that SessionState classes added later (e.g. library re-enable) can have
        their instances stamped with the session ref.
        """
        if session_id in self._known_session_ids:
            return
        self._known_session_ids.add(session_id)
        self._session_refs[session_id] = weakref.ref(session)
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
        self._session_refs.pop(session_id, None)
        for bag in self._sessions.values():
            inst = bag.pop(session_id, None)
            if inst is not None:
                self._call_on_disable(inst)

    # ------------------------------------------------------------------
    # Lifecycle event handler — registered with LibraryStateRegistry
    # ------------------------------------------------------------------

    def on_lifecycle_events(self, events: list[LifeCycleEvent]) -> None:
        for event in events:
            # CLASS_ADDED: instantiate unconditionally — the instance must be
            # reachable via ctx.app_data as soon as the class is scanned, even
            # while the owning library's enable() is still in progress.
            # on_enable is deferred to on_library_enabled (see two-phase note
            # in the module docstring).
            #
            # CLASS_REMOVED / CLASS_RELOADED: only process for libraries that
            # are fully enabled. Hot-reload of a mid-enable library is not a
            # meaningful state; CLASS_REMOVED during disable() is handled
            # correctly because the library is still in _enabled_library_ids
            # at that point (it is removed by on_library_disabled afterward).
            if event.event_type is not LifeCycleEventType.CLASS_ADDED:
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
        before ``enable_all_libraries()``. This lets ``on_library_enabled``
        fire naturally for each library as it enables, driving phase 2
        (``on_enable``) right after each library's ``enable()`` returns.
        CLASS_ADDED events received during ``enable()`` only instantiate
        state (phase 1); ``on_enable`` is deferred to ``on_library_enabled``.

        Subscribes to:
          1. State registry batch events — for hot-reload of classes
             within already-enabled libraries.
          2. Library-enabled callback — triggers on_enable for each
             library's state instances once all components are registered.
          3. Library-disabled callback — drops the library id from
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
        """Call on_enable on all state instances belonging to *library*.

        By the time this fires, ``library.enable()`` has fully returned —
        all settings, types, nodes, panels, and editors are registered.
        CLASS_ADDED events fired during ``_attach_to_registries`` have
        already instantiated the state classes (two-phase model); this
        method is the second phase: activating them.

        Marks the library id so future CLASS_RELOADED / CLASS_REMOVED
        events for it pass the filter in ``on_lifecycle_events``.

        Idempotent: classes already enabled (registry_key already in
        ``_enabled_library_ids`` from a prior call) are skipped.
        """
        self._mark_library_enabled(library.identity.id)
        classes = self._state_registry.get_classes_for_library(library.identity)
        for registry_key, cls in classes.items():
            try:
                self._enable_library_instances(registry_key, cls)
            except Exception as exc:
                logger.error(
                    "LibraryStateContainer on_enable failed for %s in library %s: %s",
                    cls.__name__,
                    library.identity.label,
                    exc,
                    exc_info=True,
                )

    def _enable_library_instances(self, registry_key: str, cls: type[LibraryState]) -> None:
        """Ensure *registry_key* is instantiated and on_enable has been called.

        Handles two cases:
        - Startup / first enable: CLASS_ADDED events were not received (the
          container was not yet subscribed). Instance does not exist yet —
          instantiate first, then enable.
        - Re-enable: CLASS_ADDED already instantiated the instance during
          library.enable(). Just call on_enable.

        Idempotent: skips registry_keys already in _enabled_registry_keys,
        preventing double-fire when on_library_enabled is called more than once.
        """
        if registry_key in self._enabled_registry_keys:
            return
        self._enabled_registry_keys.add(registry_key)
        if issubclass(cls, SessionState):
            if registry_key not in self._sessions:
                # Startup path: CLASS_ADDED was not received; instantiate now.
                self._add_session_class(cls, registry_key, call_on_enable=False)
            bag = self._sessions.get(registry_key, {})
            for instance in bag.values():
                self._call_on_enable(instance)
        elif issubclass(cls, AppState):
            if registry_key not in self._app:
                # Startup path: CLASS_ADDED was not received; instantiate now.
                self._add_app_class(cls, registry_key, call_on_enable=False)
            app_instance: AppState | None = self._app.get(registry_key)
            if app_instance is not None:
                self._call_on_enable(app_instance)

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
        # If the library is already fully enabled (its id is in
        # _enabled_library_ids), this CLASS_ADDED comes from a hot-install
        # or a re-scan of an already-running library — call on_enable
        # immediately. Otherwise defer to on_library_enabled.
        already_enabled = event.library_identity.id in self._enabled_library_ids
        if issubclass(cls, SessionState):
            self._add_session_class(cls, event.registry_key, call_on_enable=already_enabled)
        elif issubclass(cls, AppState):
            self._add_app_class(cls, event.registry_key, call_on_enable=already_enabled)
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
        # Unlike CLASS_ADDED (which defers on_enable to on_library_enabled),
        # CLASS_RELOADED only fires for already-enabled libraries, so we call
        # on_enable immediately after instantiation.
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
            # on_enable immediately — library is already fully enabled.
            bag = self._sessions.get(event.registry_key, {})
            for instance in bag.values():
                self._call_on_enable(instance)
        elif issubclass(new_cls, AppState):
            self._add_app_class(new_cls, event.registry_key)
            # on_enable immediately — library is already fully enabled.
            reloaded_app_instance: AppState | None = self._app.get(event.registry_key)
            if reloaded_app_instance is not None:
                self._call_on_enable(reloaded_app_instance)
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

    def _add_app_class(self, cls: type[AppState], registry_key: str, call_on_enable: bool = False) -> None:
        """Instantiate and store an AppState.

        call_on_enable=False (default) — deferred to on_library_enabled.
        call_on_enable=True  — library already enabled; call on_enable now
                               (hot-install / re-scan of running library).
        """
        if registry_key in self._app:
            return  # idempotent
        instance = cls()
        if self._manager_ref is not None:
            instance._session_manager = self._manager_ref
        self._app[registry_key] = instance
        self._class_by_registry_key[registry_key] = cls
        if call_on_enable:
            self._enabled_registry_keys.add(registry_key)
            self._call_on_enable(instance)

    def _remove_app_class(self, registry_key: str) -> None:
        self._enabled_registry_keys.discard(registry_key)
        instance = self._app.pop(registry_key, None)
        if instance is not None:
            self._call_on_disable(instance)

    # ------------------------------------------------------------------
    # SessionState scope helpers
    # ------------------------------------------------------------------

    def _add_session_class(
        self, cls: type[SessionState], registry_key: str, call_on_enable: bool = False
    ) -> None:
        """Instantiate session instances for all known sessions.

        call_on_enable=False (default) — deferred to on_library_enabled.
        call_on_enable=True  — library already enabled; call on_enable now.
        """
        if registry_key in self._sessions:
            return  # idempotent
        bag: dict[str, SessionState] = {}
        self._sessions[registry_key] = bag
        self._class_by_registry_key[registry_key] = cls
        for sid in self._known_session_ids:
            session_ref = self._session_refs.get(sid)
            session = session_ref() if session_ref is not None else None
            self._instantiate_session_state(cls, bag, sid, session=session, call_on_enable=call_on_enable)
        if call_on_enable:
            self._enabled_registry_keys.add(registry_key)

    def _remove_session_class(self, registry_key: str) -> None:
        self._enabled_registry_keys.discard(registry_key)
        bag = self._sessions.pop(registry_key, {})
        for inst in bag.values():
            self._call_on_disable(inst)

    def _instantiate_session_state(
        self,
        cls: type[SessionState],
        bag: dict[str, SessionState],
        session_id: str,
        session: "Session | None" = None,
        call_on_enable: bool = True,
    ) -> None:
        """Instantiate a SessionState, stamp session_id/session, store in bag.

        call_on_enable=True  — used by attach_session (session joins after
                               library is fully enabled) and by the hot-reload
                               path (CLASS_RELOADED).
        call_on_enable=False — used by CLASS_ADDED during library enable()
                               (_add_session_class); on_enable is deferred to
                               on_library_enabled.
        """
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
        instance.session_id = session_id
        if session is not None:
            instance.session = weakref.ref(session)
        bag[session_id] = instance
        if call_on_enable:
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
