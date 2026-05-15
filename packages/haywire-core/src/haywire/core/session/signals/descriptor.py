"""signal_field — descriptor that turns a class attribute into a signal source.

At class-definition time, the descriptor:
  - Verifies the owner inherits SignalSource (otherwise TypeError).
  - Rejects shadowing (a base class already declares a field of this name).
  - Synthesizes a Signal subclass named after the field, cached on the
    descriptor as `self._signal_class`. cross_session is derived from
    host scope (True iff owner is an AppState subclass).

At runtime:
  - Class-level access returns the synthetic Signal class.
  - Instance-level access returns the stored value.
  - Writes short-circuit on identity (`is`), else store and emit.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import Any, Iterator, TypeVar, TYPE_CHECKING

from .signal import Signal

if TYPE_CHECKING:
    from .host import SignalSource

T = TypeVar("T")

logger = logging.getLogger(__name__)


def _is_app_state(owner: type) -> bool:
    """True if `owner` is an AppState subclass.

    Lazy import: state.base imports session.signals (for SignalSource),
    so a top-of-file import here would form a cycle.

    Tolerance for in-flight imports: when SessionContext (defined in
    session.context, transitively imported from state.base) is being
    constructed, state.base is still mid-import and AppState is not yet
    bound. SessionContext is not an AppState, so returning False is
    correct in that race. We swallow the ImportError rather than
    propagating it because the caller (signal_field's __set_name__) only
    uses this flag to choose the synthesized signal's cross_session
    attribute — getting it wrong for SessionContext-like in-flight
    classes is not possible (they are not AppState by construction).
    """
    try:
        from haywire.core.state.base import AppState
    except ImportError:
        # state.base is mid-import; owner can't be AppState by construction.
        # Log at debug for observability if a future cycle introduces a real
        # AppState subclass that hits this race.
        logger.debug(
            "_is_app_state: AppState import not yet resolved for owner %s; treating as not-AppState.",
            owner.__qualname__,
        )
        return False
    return issubclass(owner, AppState)


def _needs_copy(initial: object) -> bool:
    """True if `initial` must be deep-copied per instance.

    The tuple below lists common immutables for which deepcopy is a no-op
    and can be skipped as a perf optimization. Anything else falls through
    to deepcopy, which is correct for all values (just unnecessary for
    immutables not in the list). Conservative — false-negatives produce
    redundant copies, not bugs.
    """
    return not isinstance(
        initial,
        (int, str, bytes, bool, float, complex, frozenset, tuple, type(None)),
    )


class _SignalFieldDescriptor:
    """Data descriptor backing `signal_field()`.

    One instance per (host_class, attr_name) pair. Holds:
      - _initial: the declared initial value
      - _attr_name: populated by __set_name__
      - _signal_class: the synthetic Signal subclass for this field
    """

    def __init__(self, initial: object) -> None:
        self._initial: object = initial
        self._attr_name: str | None = None
        self._signal_class: type[Signal] | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name
        # 1. Host must inherit SignalSource (lazy import: SignalSource
        #    lives in a sibling module that imports this one, so a
        #    top-of-file import would be circular).
        from .host import SignalSource

        if not issubclass(owner, SignalSource):
            raise TypeError(
                f"signal_field on {owner.__qualname__}.{name}: host class must "
                f"inherit from SignalSource. The three concrete bases are "
                f"SessionContext, SessionState, AppState."
            )
        # 2. Forbid shadowing: any ancestor (strict) with a _SignalFieldDescriptor
        #    of the same name is a conflict.
        for ancestor in owner.__mro__[1:]:
            if name in getattr(ancestor, "__dict__", {}):
                attr = ancestor.__dict__[name]
                if isinstance(attr, _SignalFieldDescriptor):
                    raise TypeError(
                        f"signal_field on {owner.__qualname__}.{name}: shadows a "
                        f"signal field declared on {ancestor.__qualname__}. "
                        f"Shadowing signal fields is forbidden because each "
                        f"declaration synthesizes a distinct Signal subclass — "
                        f"subscribers to the base would silently miss writes "
                        f"through the subclass."
                    )
        # 3. Synthesize the signal class.
        cross = _is_app_state(owner)
        signal_class: type[Signal] = type(  # type: ignore[assignment]
            name,
            (Signal,),
            {
                "__qualname__": f"{owner.__qualname__}.{name}",
                "__module__": owner.__module__,
                "cross_session": cross,
            },
        )
        # Make it a frozen dataclass for parity with hand-authored signals.
        signal_class = dataclass(frozen=True, kw_only=True)(signal_class)
        self._signal_class = signal_class

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            if self._signal_class is None:
                raise RuntimeError(
                    "_SignalFieldDescriptor: __set_name__ never ran (host class definition incomplete)"
                )
            return self._signal_class
        if self._attr_name is None:
            raise RuntimeError(
                "_SignalFieldDescriptor: __set_name__ never ran (host class definition incomplete)"
            )
        return instance.__dict__.get(self._attr_name, self._initial)

    def __set__(self, instance: Any, value: object) -> None:
        if self._attr_name is None:
            raise RuntimeError(
                "_SignalFieldDescriptor: __set_name__ never ran (host class definition incomplete)"
            )
        if self._signal_class is None:
            raise RuntimeError(
                "_SignalFieldDescriptor: __set_name__ never ran (host class definition incomplete)"
            )
        current = instance.__dict__.get(self._attr_name, self._initial)
        if value is current:
            return
        instance.__dict__[self._attr_name] = value
        instance._signal_emit(self._signal_class())


def signal_field(initial: T) -> T:
    """Declare a signal field on a SignalSource subclass.

    Usage:
        class EditState(SessionState):
            active_node: Optional[NodeWrapper] = signal_field(None)

    The annotation `Optional[NodeWrapper]` describes instance-level
    access — bare attribute reads/writes. The framework synthesizes a
    `Signal` subclass per field; class-level access (`EditState.active_node`)
    returns that synthetic class for use as a subscription key.

    Note: the `-> T` return annotation is a static-typing convenience. At
    runtime this returns a `_SignalFieldDescriptor`; the `T` matches the
    class-body annotation type so `x: int = signal_field(0)` reads as `x: int`
    to type-checkers and IDEs.
    """
    return _SignalFieldDescriptor(initial)  # type: ignore[return-value]


def iter_signal_fields(cls: type) -> Iterator[tuple[str, Any]]:
    """Yield (name, initial) for every signal field on cls.

    Walks the MRO so subclasses inherit. Shadowing is forbidden at
    class-definition time, so each name appears at most once across
    the MRO at runtime.
    """
    seen: set[str] = set()
    for klass in cls.__mro__:
        for name, attr in klass.__dict__.items():
            if isinstance(attr, _SignalFieldDescriptor) and name not in seen:
                seen.add(name)
                yield name, attr._initial


def _seed_signal_fields(instance: "SignalSource") -> None:
    """Seed per-instance storage for every signal field on type(instance).

    Mutable defaults are deep-copied; immutables stored as-is. Called
    from each host base's `__init__` exactly once. NOT idempotent —
    re-running clobbers any in-place mutations to mutable defaults.
    Intended as one-shot init only.
    """
    for name, initial in iter_signal_fields(type(instance)):
        instance.__dict__[name] = copy.deepcopy(initial) if _needs_copy(initial) else initial


# _seed_signal_fields and iter_signal_fields are framework-internal: only
# host bases' __init__ and tests reach for them via the full module path
# (`from haywire.core.session.signals.descriptor import _seed_signal_fields`).
# Keep them out of __all__ so `from ... import *` consumers see only the
# author-facing surface.
__all__ = ["signal_field"]
