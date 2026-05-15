"""LibraryState taxonomy — abstract marker + concrete scope bases.

A library author **never directly subclasses `LibraryState`**. They pick
one of the concrete scope bases:

  - `AppState`     — one instance, shared across all sessions and execution.
  - `SessionState` — one instance per UI session.

The mental rule is one line: *scope = base class*. Inheritance picks
multiplicity. See docs/architecture/session-and-state/session-and-state-arch.md.
"""

from __future__ import annotations

import weakref
from abc import abstractmethod
from typing import TYPE_CHECKING

from haywire.core.library.identity import LibraryIdentity
from haywire.core.session.signals import Signal, SignalSource
from haywire.core.session.signals.descriptor import _seed_signal_fields
from haywire.core.state.identity import LibraryStateClassIdentity

if TYPE_CHECKING:
    from haywire.core.session.session_manager import SessionManager


class LibraryState(SignalSource):
    """Abstract marker base. Never directly subclassed by users.

    Exists as a type-system hierarchy root and as the registry-filter
    target for `issubclass(cls, LibraryState)`. Concrete bases are
    `AppState` (app-global) and `SessionState` (per-session).

    Defines no-op `on_enable` / `on_disable` hooks so the container can
    invoke them unconditionally. Subclasses override either hook when
    they have real setup / teardown work; trivial subclasses inherit the
    no-ops and add nothing.
    """

    class_identity: LibraryStateClassIdentity
    class_library: LibraryIdentity

    def on_enable(self) -> None:
        """Lifecycle hook: called by the container after instantiation.

        Default: no-op. Override on subclasses that need to wire up
        callbacks, rehydrate persisted state, or otherwise initialise.
        """

    def on_disable(self) -> None:
        """Lifecycle hook: called by the container before teardown.

        Default: no-op. Override on subclasses that need to release
        resources, persist state, or otherwise tear down.
        """

    @abstractmethod
    def _signal_emit(self, signal: Signal) -> None:
        """Emit `signal` per the host's scope.

        AppState: broadcast across every session. SessionState: publish to
        the owning Session's bus.
        """
        raise NotImplementedError


class AppState(LibraryState):
    """Concrete base for app-global library state.

    One instance is created when the owning library is enabled and
    shared across every browser session and the execution VM. The
    framework calls `on_enable()` after instantiation and `on_disable()`
    before teardown; both default to no-op on the base class.

    See docs/architecture/session-and-state/session-and-state-arch.md.
    """

    # Set by LibraryStateContainer.bind_session_manager (and re-stamped by
    # _add_app_class for AppStates added after binding). Weakref so AppState
    # lifetime doesn't extend the SessionManager. May be None-resolving if
    # the manager has been torn down.
    _session_manager: "weakref.ReferenceType[SessionManager]"

    def __init__(self) -> None:
        """Seed per-instance storage for every `signal_field` descriptor.

        Subclasses with their own `__init__` MUST call `super().__init__()`
        — otherwise signal fields silently lose their seeded defaults
        (mutable defaults would be shared across instances).
        """
        _seed_signal_fields(self)

    def _signal_emit(self, signal: Signal) -> None:
        """Broadcast a signal across every active session.

        If the SessionManager has been torn down (e.g. app shutdown), the
        weakref returns None and we silently drop the signal. This is
        correct, not a swallowed error: there are no sessions left to
        notify. Outside shutdown, ``_session_manager`` is always set by
        ``LibraryStateContainer.bind_session_manager``.
        """
        manager = self._session_manager()
        if manager is None:
            return
        manager.broadcast(signal)


class SessionState(LibraryState):
    """Concrete base for per-UI-session library state.

    One instance is created per active session × per registered SessionState
    class. The container stamps ``self.session_id`` between ``cls()`` and
    ``on_enable()`` — read it in ``on_enable`` or any later method, never
    in ``__init__``.

    A SessionState **must not** compose ``LibrarySettings`` as a field —
    settings are app-global, sessions are per-session. The
    ``__init_subclass__`` check below catches this at class-definition time.

    See docs/architecture/session-and-state/session-and-state-arch.md.
    """

    session_id: str  # set by the container before on_enable runs
    # `session` is set by the container as a weakref.ref(Session) before on_enable runs.
    # Annotation uses bare weakref.ref to avoid an unresolvable forward ref to
    # Session (TYPE_CHECKING-only) breaking get_type_hints in __init_subclass__.
    session: "weakref.ref"

    def __init__(self) -> None:
        """Seed per-instance storage for every `signal_field` descriptor.

        Subclasses with their own `__init__` MUST call `super().__init__()`
        — otherwise signal fields silently lose their seeded defaults
        (mutable defaults would be shared across instances).
        """
        _seed_signal_fields(self)

    def _signal_emit(self, signal: Signal) -> None:
        """Emit a signal to the owning Session's bus.

        If the Session has been torn down, the weakref returns None and we
        silently drop the signal. This is correct, not a swallowed error:
        the receiving Session is gone, so there is nothing to notify. This
        race happens during shutdown when a SessionState's ``on_disable``
        runs after ``Session.cleanup`` has zeroed the bus.

        NOTE: ``AttributeError`` on a missing ``session`` attribute is
        intentional (NOT silent). The container ALWAYS stamps ``session``
        before ``on_enable``; a missing attribute means a wiring bug, not
        a race. Tests that build SessionStates directly without going
        through SessionManager must stamp a stub session — see
        ``tests/conftest.py::attach_stub_session``.
        """
        sess = self.session()
        if sess is None:
            return
        sess.publish(signal)

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        _reject_library_settings_fields(cls)


def _reject_library_settings_fields(cls: type) -> None:
    """Walk class type annotations and raise TypeError for any LibrarySettings field.

    Catches `field: MyLibSettings`, `field: MyLibSettings | None`,
    `field: Optional[MyLibSettings]`, and Union variants.
    """
    from typing import get_type_hints

    from haywire.core.settings.schema import LibrarySettings

    try:
        hints = get_type_hints(cls, include_extras=False)
    except Exception:
        # Forward references that don't resolve at class-creation time are
        # skipped — best-effort check, not a guaranteed catch-all.
        return

    for name, ann in hints.items():
        if name == "session_id":
            continue
        for resolved in _flatten_annotation(ann):
            if isinstance(resolved, type) and issubclass(resolved, LibrarySettings):
                raise TypeError(
                    f"SessionState '{cls.__name__}' has field "
                    f"'{name}: {resolved.__name__}' — LibrarySettings cannot be "
                    f"composed inside SessionState (settings are app-global; "
                    f"sessions are per-session). Read settings values inside "
                    f"methods/hooks instead, never hold a LibrarySettings instance."
                )


def _flatten_annotation(ann: object) -> list[object]:
    """Return all concrete types referenced by an annotation.

    Handles ``X``, ``Optional[X]`` (= ``X | None``), and ``Union[A, B, ...]``.
    """
    import types
    import typing

    origin = typing.get_origin(ann)
    if origin is None:
        return [ann]
    if origin is typing.Union or origin is types.UnionType:
        out: list[object] = []
        for arg in typing.get_args(ann):
            out.extend(_flatten_annotation(arg))
        return out
    return [ann]
