# Signal-field unification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify reactive fields with the session event bus under a single "signal" vocabulary. Field writes emit signals; the field reference is the subscription key. Delete the four dead `ActiveXxxMoved` event classes, the unused `Reactive[T]` / `ReactivePath` types, and rename the bus surface (`Event`→`Signal`, `EventBus`→`SignalBus`, `LifecycleCommand`→`CommandSignal`).

**Architecture:** A new data descriptor `_SignalFieldDescriptor` lives on each host class. At `__set_name__` it synthesizes a `Signal` subclass per (host_class, attr_name) pair and verifies the host inherits `SignalSource(ABC)`. On `__set__` it short-circuits on identity (`is`), writes per-instance storage, and calls `host._signal_emit(signal_class())`. The three host bases (`SessionContext`, `SessionState`, `AppState`) implement `_signal_emit` differently per scope — session-local publish vs. cross-session broadcast. Container stamps weakrefs (`self.session` on SessionState, `self._session_manager` on AppState) before `on_enable()`.

**Tech Stack:** Python 3.12, `abc.ABC`/`abstractmethod`, `weakref.ref`, dataclass-based signal classes, pytest, ruff, mypy, NiceGUI.

**Spec:** [internals/speculatives/reactive_bus_unification.md](../../speculatives/reactive_bus_unification.md). Decisions Q1–Q15 and V1–V6 captured there.

**Pre-flight (run once, before Task 1):**

```sh
uv run ruff check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ \
            barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ \
            barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ \
            barn/haybale-visiongraph/haybale_visiongraph/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest
```

Expected: all green. If anything fails before edits begin, **stop and report to user** — establish a baseline first (per CLAUDE.md).

---

## File structure (created/modified across the whole plan)

**New files:**

- `packages/haywire-core/src/haywire/core/session/signals/__init__.py` — public surface
- `packages/haywire-core/src/haywire/core/session/signals/signal.py` — `Signal` (replaces `Event`), `CommandSignal` (replaces `LifecycleCommand`)
- `packages/haywire-core/src/haywire/core/session/signals/bus.py` — `SignalBus`, `SignalHandler` (replaces `EventBus`/`EventHandler`)
- `packages/haywire-core/src/haywire/core/session/signals/host.py` — `SignalSource(ABC)` with `@abstractmethod _signal_emit`
- `packages/haywire-core/src/haywire/core/session/signals/descriptor.py` — `_SignalFieldDescriptor`, `signal_field()`, `iter_signal_fields()`, `_seed_signal_fields()`

**Files deleted (after migration):**

- `packages/haywire-core/src/haywire/core/session/reactive/reactive.py` (the `Reactive[T]` class)
- `packages/haywire-core/src/haywire/core/session/reactive/path.py` (`ReactivePath`)
- `packages/haywire-core/src/haywire/core/session/reactive/descriptor.py` (old descriptor; replaced)
- `packages/haywire-core/src/haywire/core/session/reactive/__init__.py`
- `packages/haywire-core/src/haywire/core/session/bus.py` (old `EventBus`)
- `packages/haywire-core/src/haywire/core/session/events.py` (old `Event`, `ContextSignal`, `LifecycleCommand`)

**Files modified:**

- `packages/haywire-core/src/haywire/core/session/context.py` — inherit `SignalSource`, implement `_signal_emit`, drop `.value` from field declarations
- `packages/haywire-core/src/haywire/core/session/session.py` — rename `_bus: EventBus` → `_bus: SignalBus`; `Event` → `Signal`
- `packages/haywire-core/src/haywire/core/session/session_manager.py` — rename `Event` → `Signal`
- `packages/haywire-core/src/haywire/core/session/handlers.py` — rename `validate_event_types` → `validate_signal_types`; `ContextSignal` → `Signal`
- `packages/haywire-core/src/haywire/core/state/base.py` — `LibraryState(SignalSource, ABC)`; concrete `_signal_emit` on `AppState`/`SessionState`; add `session` weakref attr on `SessionState`, `_session_manager` weakref attr on `AppState`
- `packages/haywire-core/src/haywire/core/state/container.py` — stamp `session` weakref on SessionState instantiation; stamp `_session_manager` weakref on AppState instantiation
- All barn `EditState`, `FileBrowserState`, `haybale-testing` fixture state — drop `Reactive[T]` annotations; replace `reactive_field` → `signal_field`
- ~50 `.value` read/write sites across haywire-core, haywire-studio, barn — bare attribute access
- `validate_event_types` callers (~5)
- `@redraw_on(ActiveFileMoved)` / `@redraw_on(ActiveLibraryMoved)` etc. → `@redraw_on(SessionContext.active_file)` etc.
- Subscriber `Type[Event]` → `Type[Signal]` parameters

**Test files:**

- New: `tests/core/test_signals/test_signal_field_descriptor.py`
- New: `tests/core/test_signals/test_signal_source_abc.py`
- New: `tests/core/test_signals/test_signal_field_seed.py`
- New: `tests/core/test_signals/test_app_state_broadcast.py`
- New: `tests/core/test_signals/test_session_state_post_cleanup.py`
- New: `tests/core/test_signals/test_hot_reload_roundtrip.py`
- Existing: rename `tests/core/test_session/test_event_bus*.py` → `test_signal_bus*.py`; update `Event`→`Signal`, etc.
- Existing: `tests/studio/test_edit_state.py:80` — rewrite `.value.add(...)` pattern (see Task 4)

---

## Task 1: Land the new signals module (descriptor + bus + ABC + Signal root)

**Files:**

- Create: `packages/haywire-core/src/haywire/core/session/signals/__init__.py`
- Create: `packages/haywire-core/src/haywire/core/session/signals/signal.py`
- Create: `packages/haywire-core/src/haywire/core/session/signals/bus.py`
- Create: `packages/haywire-core/src/haywire/core/session/signals/host.py`
- Create: `packages/haywire-core/src/haywire/core/session/signals/descriptor.py`
- Test: `tests/core/test_signals/test_signal_field_descriptor.py`
- Test: `tests/core/test_signals/test_signal_source_abc.py`
- Test: `tests/core/test_signals/test_signal_field_seed.py`

The new module co-exists with the old `session/reactive/`, `session/bus.py`, `session/events.py` for now. Nothing is wired yet. Old code keeps working.

- [ ] **Step 1.1: Write the failing test for `Signal` root and `CommandSignal`**

Create `tests/core/test_signals/test_signal_field_descriptor.py`:

```python
"""Tests for the Signal root class hierarchy."""
from haywire.core.session.signals import Signal, CommandSignal


def test_signal_is_abstract_root():
    """Signal is a frozen-dataclass base; concrete subclasses are instantiable."""
    class Concrete(Signal):
        pass
    inst = Concrete()
    assert isinstance(inst, Signal)


def test_command_signal_is_signal_subclass():
    assert issubclass(CommandSignal, Signal)


def test_cross_session_default_false():
    class Concrete(Signal):
        pass
    assert Concrete.cross_session is False


def test_cross_session_can_be_overridden():
    from typing import ClassVar
    class Broadcasting(Signal):
        cross_session: ClassVar[bool] = True
    assert Broadcasting.cross_session is True
```

- [ ] **Step 1.2: Run test to verify it fails**

```sh
uv run pytest tests/core/test_signals/test_signal_field_descriptor.py::test_signal_is_abstract_root -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'haywire.core.session.signals'`.

- [ ] **Step 1.3: Create the signals module skeleton**

Create `packages/haywire-core/src/haywire/core/session/signals/signal.py`:

```python
"""Signal — base class for everything dispatched through SignalBus.

Replaces the old `Event` root. Concrete signal classes (`SelectionMoved`,
`GraphDataMutated`, etc.) inherit directly. `CommandSignal` is the
imperative-flavored sub-base (replaces `LifecycleCommand`).

Synthetic signal classes generated by `signal_field()` also inherit
`Signal` directly — they participate as first-class subclasses with no
special routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class Signal:
    """Base class for everything dispatched through SignalBus.

    Subscribers filter with `isinstance(signal, SignalType)` — there is
    no framework-side identity machinery beyond `type(signal)` matching.

    `cross_session: ClassVar[bool] = False` opts a signal into
    SessionManager.broadcast routing when True.
    """

    cross_session: ClassVar[bool] = False


@dataclass(frozen=True, kw_only=True)
class CommandSignal(Signal):
    """Imperative signal — 'do Y'.

    Conventionally one subscriber per command type (the AppShell), but
    the bus does not enforce that. Travels through the same bus as every
    other signal; the split is vocabulary for authors.
    """
```

Create `packages/haywire-core/src/haywire/core/session/signals/__init__.py`:

```python
"""Signal-field unification: signals, the bus, the host ABC, the descriptor.

Public surface:
- Signal, CommandSignal — base classes
- SignalBus, SignalHandler — the transport
- SignalSource — the host ABC
- signal_field — the descriptor factory
"""

from .signal import Signal, CommandSignal
from .bus import SignalBus, SignalHandler
from .host import SignalSource
from .descriptor import signal_field

__all__ = [
    "Signal",
    "CommandSignal",
    "SignalBus",
    "SignalHandler",
    "SignalSource",
    "signal_field",
]
```

Add empty placeholders for `bus.py`, `host.py`, `descriptor.py` so the imports resolve:

Create `packages/haywire-core/src/haywire/core/session/signals/bus.py` (placeholder):

```python
"""SignalBus — typed pub/sub. Implementation in step 1.5."""
from typing import Callable
from .signal import Signal
SignalHandler = Callable[[Signal], None]
class SignalBus: ...
```

Create `packages/haywire-core/src/haywire/core/session/signals/host.py` (placeholder):

```python
"""SignalSource — host ABC. Implementation in step 1.7."""
from abc import ABC
class SignalSource(ABC): ...
```

Create `packages/haywire-core/src/haywire/core/session/signals/descriptor.py` (placeholder):

```python
"""signal_field descriptor. Implementation in step 1.9."""
def signal_field(initial): ...
```

- [ ] **Step 1.4: Run Signal tests to verify they pass**

```sh
uv run pytest tests/core/test_signals/test_signal_field_descriptor.py -v -k "test_signal or test_command or test_cross_session"
```

Expected: 4 PASS.

- [ ] **Step 1.5: Write SignalBus tests**

Append to `tests/core/test_signals/test_signal_field_descriptor.py`:

```python
import pytest
from haywire.core.session.signals import SignalBus, Signal


def test_signal_bus_subscribe_and_publish():
    bus = SignalBus()
    received = []
    class Tick(Signal): pass
    bus.subscribe(Tick, lambda s: received.append(s))
    sig = Tick()
    bus.publish(sig)
    assert received == [sig]


def test_signal_bus_exact_type_match_no_subclass_routing():
    """Subscribers to Parent do NOT receive Child events."""
    bus = SignalBus()
    parent_received = []
    class Parent(Signal): pass
    class Child(Parent): pass
    bus.subscribe(Parent, lambda s: parent_received.append(s))
    bus.publish(Child())
    assert parent_received == []


def test_signal_bus_unsubscribe():
    bus = SignalBus()
    received = []
    class Tick(Signal): pass
    handler = lambda s: received.append(s)
    unsub = bus.subscribe(Tick, handler)
    unsub()
    bus.publish(Tick())
    assert received == []


def test_signal_bus_handler_error_isolated():
    bus = SignalBus()
    received = []
    class Tick(Signal): pass
    def boom(s): raise RuntimeError("boom")
    bus.subscribe(Tick, boom)
    bus.subscribe(Tick, lambda s: received.append(s))
    bus.publish(Tick())  # must not raise
    assert len(received) == 1


def test_signal_bus_subscribe_rejects_non_signal():
    bus = SignalBus()
    with pytest.raises(TypeError):
        bus.subscribe(int, lambda x: None)  # type: ignore[arg-type]
```

- [ ] **Step 1.6: Run bus tests, verify they fail**

```sh
uv run pytest tests/core/test_signals/test_signal_field_descriptor.py -v -k "test_signal_bus"
```

Expected: FAIL — `SignalBus` is a stub.

- [ ] **Step 1.7: Implement SignalBus**

Overwrite `packages/haywire-core/src/haywire/core/session/signals/bus.py`:

```python
"""SignalBus — typed pub/sub, session-scoped.

Direct rename of the prior EventBus. Same semantics: defaultdict of
handler lists keyed by exact Signal subclass, error-isolated per
handler, registration-order dispatch, snapshot-on-iterate so mid-
dispatch subscribe/unsubscribe is safe.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, Dict, List, Tuple, Type, TypeVar

from .signal import Signal

logger = logging.getLogger(__name__)

SignalHandler = Callable[[Signal], None]
S = TypeVar("S", bound=Signal)


class SignalBus:
    """Typed pub/sub bus, session-scoped.

    One instance per Session. Subscribers register a handler for an exact
    Signal class; publishes fan out only to handlers registered for
    `type(signal)`. Not thread-safe by design (NiceGUI single-threaded).
    """

    def __init__(self) -> None:
        self._handlers: Dict[Type[Signal], List[SignalHandler]] = defaultdict(list)

    def subscribe(
        self,
        signal_type: Type[S],
        handler: Callable[[S], None],
    ) -> Callable[[], None]:
        if not isinstance(signal_type, type) or not issubclass(signal_type, Signal):
            raise TypeError(
                f"SignalBus.subscribe: signal_type must be a Signal subclass; got {signal_type!r}"
            )
        self._handlers[signal_type].append(handler)  # type: ignore[arg-type]

        def _unsubscribe() -> None:
            handlers = self._handlers.get(signal_type)
            if handlers is None:
                return
            try:
                handlers.remove(handler)  # type: ignore[arg-type]
            except ValueError:
                return
            if not handlers:
                self._handlers.pop(signal_type, None)

        return _unsubscribe

    def publish(self, signal: Signal) -> None:
        handlers = tuple(self._handlers.get(type(signal), ()))
        for handler in handlers:
            try:
                handler(signal)
            except Exception:
                logger.exception(
                    "SignalBus: handler %r raised during publish of %s; continuing",
                    handler,
                    type(signal).__name__,
                )

    def subscriber_count(self, signal_type: Type[Signal]) -> int:
        return len(self._handlers.get(signal_type, ()))

    def subscribed_types(self) -> Tuple[Type[Signal], ...]:
        return tuple(self._handlers.keys())

    def clear(self) -> None:
        self._handlers.clear()


__all__ = ["SignalBus", "SignalHandler"]
```

- [ ] **Step 1.8: Verify SignalBus tests pass**

```sh
uv run pytest tests/core/test_signals/test_signal_field_descriptor.py -v -k "test_signal_bus"
```

Expected: 5 PASS.

- [ ] **Step 1.9: Write SignalSource ABC tests**

Create `tests/core/test_signals/test_signal_source_abc.py`:

```python
"""Tests for SignalSource — the ABC contract for hosts that emit signals."""
import pytest
from haywire.core.session.signals import SignalSource, Signal


def test_signal_source_is_abstract():
    """A class inheriting SignalSource without implementing _signal_emit
    cannot be instantiated."""
    class Incomplete(SignalSource):
        pass
    with pytest.raises(TypeError) as ei:
        Incomplete()  # type: ignore[abstract]
    assert "abstract" in str(ei.value).lower()


def test_signal_source_concrete_implementation_works():
    """An implementor with _signal_emit is instantiable."""
    received = []

    class Concrete(SignalSource):
        def _signal_emit(self, signal: Signal) -> None:
            received.append(signal)

    inst = Concrete()
    class Tick(Signal): pass
    sig = Tick()
    inst._signal_emit(sig)
    assert received == [sig]
```

- [ ] **Step 1.10: Run, verify failing**

```sh
uv run pytest tests/core/test_signals/test_signal_source_abc.py -v
```

Expected: FAIL (placeholder `SignalSource` has no `@abstractmethod`).

- [ ] **Step 1.11: Implement SignalSource**

Overwrite `packages/haywire-core/src/haywire/core/session/signals/host.py`:

```python
"""SignalSource — ABC for hosts that emit signal-field signals.

Concrete implementors: SessionContext, SessionState, AppState. Authors
do not subclass this directly — they subclass one of the three concrete
bases.

Enforcement: Python's ABC machinery refuses to instantiate any concrete
class that omits `_signal_emit`. The signal_field descriptor's
`issubclass(owner, SignalSource)` check at class-definition time
catches the "wrong base class" mistake earlier with a clearer error.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .signal import Signal


class SignalSource(ABC):
    """Anything that can emit signal-field signals."""

    @abstractmethod
    def _signal_emit(self, signal: Signal) -> None:
        """Emit `signal` to whatever subscribers this host fans out to.

        SessionContext / SessionState: forward to `Session.publish`.
        AppState: forward to `SessionManager.broadcast`.
        """
        raise NotImplementedError


__all__ = ["SignalSource"]
```

- [ ] **Step 1.12: Verify SignalSource tests pass**

```sh
uv run pytest tests/core/test_signals/test_signal_source_abc.py -v
```

Expected: 2 PASS.

- [ ] **Step 1.13: Write descriptor tests (the core machinery)**

Create `tests/core/test_signals/test_signal_field_seed.py`:

```python
"""Tests for _SignalFieldDescriptor, signal_field(), iter_signal_fields,
_seed_signal_fields. Exercises identity short-circuit, class-level
synthetic class access, shadowing rejection, host validation, mutable-
default deep-copy seeding."""
import pytest
from haywire.core.session.signals import Signal, SignalSource, signal_field
from haywire.core.session.signals.descriptor import (
    iter_signal_fields,
    _seed_signal_fields,
)


class _Recorder(SignalSource):
    def __init__(self) -> None:
        self.emitted: list[Signal] = []
        _seed_signal_fields(self)

    def _signal_emit(self, signal: Signal) -> None:
        self.emitted.append(signal)


def test_class_level_access_returns_synthetic_signal_class():
    class H(_Recorder):
        x: int = signal_field(0)
    # Class-level access returns the synthetic class.
    assert isinstance(H.x, type)
    assert issubclass(H.x, Signal)


def test_instance_level_access_returns_value():
    class H(_Recorder):
        x: int = signal_field(7)
    h = H()
    assert h.x == 7


def test_write_emits_signal():
    class H(_Recorder):
        x: int = signal_field(0)
    h = H()
    h.x = 5
    assert len(h.emitted) == 1
    assert isinstance(h.emitted[0], H.x)


def test_identity_short_circuit():
    """Same object reassigned is a no-op."""
    class H(_Recorder):
        x: object = signal_field(None)
    h = H()
    sentinel = object()
    h.x = sentinel
    h.emitted.clear()
    h.x = sentinel  # identity-equal — must NOT emit
    assert h.emitted == []


def test_value_equal_but_identity_distinct_fires():
    """Two distinct equal-but-not-identical objects emit on second write."""
    from dataclasses import dataclass

    @dataclass
    class Wrap:
        v: int

    class H(_Recorder):
        x: object = signal_field(None)

    h = H()
    h.x = Wrap(1)
    h.emitted.clear()
    h.x = Wrap(1)  # == True, is False — must emit
    assert len(h.emitted) == 1


def test_non_signal_source_host_rejected_at_class_definition():
    """Using signal_field on a non-SignalSource class raises TypeError."""
    with pytest.raises(TypeError) as ei:
        class Wrong:
            x: int = signal_field(0)
    assert "SignalSource" in str(ei.value)


def test_shadowing_rejected_at_class_definition():
    """Redeclaring a signal field in a subclass raises TypeError."""
    class Base(_Recorder):
        x: int = signal_field(0)
    with pytest.raises(TypeError) as ei:
        class Sub(Base):
            x: int = signal_field(99)  # type: ignore[assignment]
    assert "shadow" in str(ei.value).lower() or "redeclare" in str(ei.value).lower()


def test_mutable_default_deepcopied_per_instance():
    """Mutable defaults like set() are not shared across instances."""
    class H(_Recorder):
        items: set[str] = signal_field(set())
    h1 = H()
    h2 = H()
    h1.items.add("a")
    assert "a" not in h2.items


def test_iter_signal_fields_walks_mro():
    """iter_signal_fields yields (name, initial) for every signal field
    on the class and its bases."""
    class Base(_Recorder):
        a: int = signal_field(1)
    class Sub(Base):
        b: int = signal_field(2)
    fields = dict(iter_signal_fields(Sub))
    assert fields == {"a": 1, "b": 2}


def test_synthetic_signal_class_has_readable_qualname():
    class HostClass(_Recorder):
        field_name: int = signal_field(0)
    assert HostClass.field_name.__qualname__ == "HostClass.field_name"
    assert HostClass.field_name.__name__ == "field_name"
```

- [ ] **Step 1.14: Run, verify failing**

```sh
uv run pytest tests/core/test_signals/test_signal_field_seed.py -v
```

Expected: FAIL — `signal_field` is a stub returning None.

- [ ] **Step 1.15: Implement the descriptor**

Overwrite `packages/haywire-core/src/haywire/core/session/signals/descriptor.py`:

```python
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
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, Iterator, TypeVar, TYPE_CHECKING

from .signal import Signal

if TYPE_CHECKING:
    from .host import SignalSource

T = TypeVar("T")


def _is_app_state(owner: type) -> bool:
    """True if `owner` is an AppState subclass.

    Import is lazy because AppState lives in haywire.core.state which
    imports from haywire.core.session — circular at module-load time.
    """
    try:
        from haywire.core.state.base import AppState
    except ImportError:
        return False
    return issubclass(owner, AppState)


def _needs_copy(initial: object) -> bool:
    """True if `initial` must be deep-copied per instance.

    Conservative: copy everything except known-immutables. The copy is
    cheap for immutables in CPython, but skip the call to avoid bloat.
    """
    return not isinstance(
        initial,
        (int, str, bytes, bool, float, complex, frozenset, tuple, type(None)),
    )


class _SignalFieldDescriptor(Generic[T]):
    """Data descriptor backing `signal_field()`.

    One instance per (host_class, attr_name) pair. Holds:
      - _initial: the declared initial value
      - _attr_name: populated by __set_name__
      - _signal_class: the synthetic Signal subclass for this field
    """

    def __init__(self, initial: T) -> None:
        self._initial: T = initial
        self._attr_name: str | None = None
        self._signal_class: type[Signal] | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name
        # 1. Host must inherit SignalSource (lazy import; see _is_app_state note).
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
            assert self._signal_class is not None, "__set_name__ never ran"
            return self._signal_class
        assert self._attr_name is not None
        return instance.__dict__.get(self._attr_name, self._initial)

    def __set__(self, instance: Any, value: T) -> None:
        assert self._attr_name is not None
        assert self._signal_class is not None
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
    from each host base's `__init__`. Idempotent — re-seeding overwrites
    storage with fresh copies, which callers should not rely on; this is
    one-shot init.
    """
    for name, initial in iter_signal_fields(type(instance)):
        instance.__dict__[name] = copy.deepcopy(initial) if _needs_copy(initial) else initial


__all__ = ["signal_field", "iter_signal_fields", "_seed_signal_fields"]
```

- [ ] **Step 1.16: Run descriptor tests, verify all pass**

```sh
uv run pytest tests/core/test_signals/ -v
```

Expected: all PASS (11+ tests).

- [ ] **Step 1.17: Run full pre-existing suite to confirm no regressions**

```sh
uv run pytest -x
```

Expected: green. The new module is additive; nothing imports it yet.

- [ ] **Step 1.18: Run ruff + mypy on the new files**

```sh
uv run ruff check packages/haywire-core/src/haywire/core/session/signals/ tests/core/test_signals/
uv run mypy packages/haywire-core/src/haywire/core/session/signals/
```

Expected: no errors.

- [ ] **Step 1.19: Commit**

```sh
git add packages/haywire-core/src/haywire/core/session/signals/ tests/core/test_signals/
git commit -m "feat(signals): add signal-field descriptor, SignalBus, SignalSource ABC

Lands the new session/signals/ module alongside the existing reactive/
and bus/events surface. Nothing is wired yet — this commit only adds
the new types so subsequent commits can migrate to them.

- Signal (replaces Event), CommandSignal (replaces LifecycleCommand)
- SignalBus, SignalHandler (replaces EventBus, EventHandler)
- SignalSource(ABC) with @abstractmethod _signal_emit
- _SignalFieldDescriptor, signal_field(), iter_signal_fields(),
  _seed_signal_fields()

Refs: internals/speculatives/reactive_bus_unification.md (Q1-Q15, V1-V6)"
```

---

## Task 2: Wire the host base classes (`_signal_emit` on SessionContext, SessionState, AppState; container stamping)

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/session/context.py`
- Modify: `packages/haywire-core/src/haywire/core/state/base.py`
- Modify: `packages/haywire-core/src/haywire/core/state/container.py`
- Modify: `packages/haywire-core/src/haywire/core/session/session_manager.py` (add public `broadcast`-from-state path if not already callable from outside)
- Test: `tests/core/test_signals/test_app_state_broadcast.py`
- Test: `tests/core/test_signals/test_session_state_post_cleanup.py`

After this task: each host base inherits `SignalSource` and implements `_signal_emit`, but no fields use signal_field yet. The descriptor's class-definition checks succeed because the host bases are now SignalSource subclasses.

- [ ] **Step 2.1: Write the failing test for SessionContext._signal_emit**

Create `tests/core/test_signals/test_app_state_broadcast.py`:

```python
"""Tests for _signal_emit on each of the three host bases.

Verifies routing: SessionContext/SessionState publish to the local bus;
AppState broadcasts to every session via SessionManager."""
import pytest
from unittest.mock import MagicMock
from haywire.core.session.signals import Signal, SignalSource


def test_session_context_inherits_signal_source():
    """SessionContext must be a SignalSource subclass."""
    from haywire.core.session.context import SessionContext
    assert issubclass(SessionContext, SignalSource)


def test_session_context_signal_emit_delegates_to_session_publish():
    from haywire.core.session.context import SessionContext

    class Tick(Signal): pass
    ctx = SessionContext.__new__(SessionContext)
    ctx.session = MagicMock()
    sig = Tick()
    ctx._signal_emit(sig)
    ctx.session.publish.assert_called_once_with(sig)
```

- [ ] **Step 2.2: Run, verify fails**

```sh
uv run pytest tests/core/test_signals/test_app_state_broadcast.py::test_session_context_inherits_signal_source -v
```

Expected: FAIL — `SessionContext` does not inherit `SignalSource`.

- [ ] **Step 2.3: Make SessionContext inherit SignalSource and implement _signal_emit**

Modify `packages/haywire-core/src/haywire/core/session/context.py` — locate the class declaration (around line 27, where `SessionContext` is defined) and update:

- Add import at top:
  ```python
  from haywire.core.session.signals import Signal, SignalSource
  ```
- Change `class SessionContext:` → `class SessionContext(SignalSource):`
- Add this method (placement: with other instance methods, near the end of the class body):
  ```python
  def _signal_emit(self, signal: Signal) -> None:
      """Forward signal to the owning Session's bus.

      Implements SignalSource for SessionContext. self.session is set
      by Session.__init__ before SessionContext is used.
      """
      self.session.publish(signal)
  ```

Do NOT remove the existing `reactive_field` declarations on SessionContext yet — that's Task 3. After this step `SessionContext` is a `SignalSource` with `_signal_emit` but still uses the old `reactive_field`/`Reactive[T]` for its fields.

- [ ] **Step 2.4: Verify the SessionContext test passes**

```sh
uv run pytest tests/core/test_signals/test_app_state_broadcast.py::test_session_context_inherits_signal_source tests/core/test_signals/test_app_state_broadcast.py::test_session_context_signal_emit_delegates_to_session_publish -v
```

Expected: 2 PASS.

- [ ] **Step 2.5: Write failing tests for SessionState and AppState _signal_emit + weakref stamping**

Append to `tests/core/test_signals/test_app_state_broadcast.py`:

```python
import weakref
from haywire.core.state.base import AppState, SessionState


def test_session_state_inherits_signal_source():
    assert issubclass(SessionState, SignalSource)


def test_app_state_inherits_signal_source():
    assert issubclass(AppState, SignalSource)


def test_session_state_signal_emit_via_weakref_session():
    """SessionState._signal_emit derefs self.session weakref and calls publish."""
    class Tick(Signal): pass

    class MyState(SessionState):
        pass

    mock_session = MagicMock()
    state = MyState()
    state.session = weakref.ref(mock_session)
    state._signal_emit(Tick())
    mock_session.publish.assert_called_once()


def test_session_state_signal_emit_silent_when_session_gone():
    """If the Session has been garbage-collected, _signal_emit is a silent no-op."""
    class Tick(Signal): pass

    class MyState(SessionState):
        pass

    class _Disposable:
        pass

    sess = _Disposable()
    state = MyState()
    state.session = weakref.ref(sess)
    del sess  # weakref now dead
    # Must not raise; must not call anything.
    state._signal_emit(Tick())


def test_app_state_signal_emit_via_weakref_manager():
    class Tick(Signal): pass

    class MyAppState(AppState):
        pass

    mock_mgr = MagicMock()
    state = MyAppState()
    state._session_manager = weakref.ref(mock_mgr)
    state._signal_emit(Tick())
    mock_mgr.broadcast.assert_called_once()


def test_app_state_signal_emit_silent_when_manager_gone():
    class Tick(Signal): pass

    class MyAppState(AppState):
        pass

    class _Disposable:
        pass

    mgr = _Disposable()
    state = MyAppState()
    state._session_manager = weakref.ref(mgr)
    del mgr
    state._signal_emit(Tick())  # must not raise
```

- [ ] **Step 2.6: Run, verify fails**

```sh
uv run pytest tests/core/test_signals/test_app_state_broadcast.py -v -k "session_state or app_state"
```

Expected: FAIL — base classes don't inherit `SignalSource` and don't implement `_signal_emit`.

- [ ] **Step 2.7: Update state/base.py to inherit SignalSource and implement _signal_emit**

Modify `packages/haywire-core/src/haywire/core/state/base.py`:

- Add imports at top:
  ```python
  import weakref
  from typing import TYPE_CHECKING
  from haywire.core.session.signals import Signal, SignalSource
  if TYPE_CHECKING:
      from haywire.core.session.session import Session
      from haywire.core.session.session_manager import SessionManager
  ```
- Change `class LibraryState:` → `class LibraryState(SignalSource):`
- Add `@abstractmethod` on `LibraryState` for `_signal_emit` so the two concrete subclasses must implement it (LibraryState itself stays abstract):
  ```python
  from abc import abstractmethod
  # Inside LibraryState body, after on_disable:
  @abstractmethod
  def _signal_emit(self, signal: Signal) -> None:
      """Emit `signal` per the host's scope.

      AppState: broadcast across every session. SessionState: publish to
      the owning Session's bus.
      """
      raise NotImplementedError
  ```
- On `AppState`, add:
  ```python
  _session_manager: "weakref.ReferenceType[SessionManager]"

  def _signal_emit(self, signal: Signal) -> None:
      manager = self._session_manager()
      if manager is None:
          return
      manager.broadcast(signal)
  ```
- On `SessionState`, add `session` weakref attribute and concrete `_signal_emit`:
  ```python
  session: "weakref.ReferenceType[Session]"

  def _signal_emit(self, signal: Signal) -> None:
      sess = self.session()
      if sess is None:
          return
      sess.publish(signal)
  ```

(The existing `session_id: str` annotation and `__init_subclass__` stay.)

- [ ] **Step 2.8: Verify state/base.py tests pass**

```sh
uv run pytest tests/core/test_signals/test_app_state_broadcast.py -v
```

Expected: all PASS.

- [ ] **Step 2.9: Write failing test for container stamping (SessionState gets `session` weakref)**

Create `tests/core/test_signals/test_session_state_post_cleanup.py`:

```python
"""Container stamps `session` weakref on SessionState instances before on_enable."""
import weakref
from unittest.mock import MagicMock
from haywire.core.state.base import SessionState


def test_container_stamps_session_weakref_on_session_state():
    """When the container instantiates a SessionState for a session, it must
    stamp `self.session = weakref.ref(session)` before on_enable runs."""
    from haywire.core.state.container import LibraryStateContainer
    from haywire.core.state.registry import LibraryStateRegistry

    seen_session = []

    class MyState(SessionState):
        # Stable class identity so the registry can track it
        from haywire.core.library.identity import LibraryIdentity
        from haywire.core.state.identity import LibraryStateClassIdentity
        class_identity = LibraryStateClassIdentity(
            registry_key="test:lib:MyState",
            class_qualname="MyState",
        )
        class_library = LibraryIdentity(id="test:lib", label="test", version="0", dependencies=[])

        def on_enable(self) -> None:
            # The weakref must be set by now.
            seen_session.append(self.session())

    container = LibraryStateContainer(LibraryStateRegistry())
    container._mark_library_enabled("test:lib")
    container._class_by_registry_key["test:lib:MyState"] = MyState
    container._sessions["test:lib:MyState"] = {}

    fake_session = MagicMock()
    container.attach_session_with_ref("session-1", fake_session)

    assert seen_session == [fake_session]
```

Note: the test calls `attach_session_with_ref(session_id, session)` — a new API on the container. We'll add that in the next step.

- [ ] **Step 2.10: Run, verify fails**

```sh
uv run pytest tests/core/test_signals/test_session_state_post_cleanup.py -v
```

Expected: FAIL — `attach_session_with_ref` does not exist.

- [ ] **Step 2.11: Add `attach_session_with_ref` to LibraryStateContainer**

Modify `packages/haywire-core/src/haywire/core/state/container.py`:

- Add new method (place near existing `attach_session`):
  ```python
  def attach_session_with_ref(self, session_id: str, session: "Session") -> None:
      """Same as `attach_session`, but also stamps `self.session = weakref.ref(session)`
      on every SessionState instance before `on_enable` runs.

      Called by `SessionManager.create_session`.
      """
      import weakref
      if session_id in self._known_session_ids:
          return
      self._known_session_ids.add(session_id)
      for registry_key, bag in self._sessions.items():
          cls = self._class_by_registry_key.get(registry_key)
          if cls is None or not issubclass(cls, SessionState):
              continue
          self._instantiate_session_state_with_ref(cls, bag, session_id, session)

  def _instantiate_session_state_with_ref(
      self,
      cls: type[SessionState],
      bag: dict[str, SessionState],
      session_id: str,
      session: "Session",
  ) -> None:
      import weakref
      try:
          instance = cls()
      except Exception as exc:
          logger.error(
              "Failed to instantiate SessionState %s for session %s: %s",
              cls.__name__, session_id, exc, exc_info=True,
          )
          return
      instance.session_id = session_id
      instance.session = weakref.ref(session)  # NEW: stamp session weakref
      bag[session_id] = instance
      self._call_on_enable(instance)
  ```
- Add `TYPE_CHECKING` import for `Session`:
  ```python
  if TYPE_CHECKING:
      from haywire.core.session.session import Session
      # existing imports preserved
  ```

Keep the original `attach_session` and `_instantiate_session_state` — `SessionManager` will be updated in step 2.13 to call the new variant.

- [ ] **Step 2.12: Verify container stamping test passes**

```sh
uv run pytest tests/core/test_signals/test_session_state_post_cleanup.py -v
```

Expected: PASS.

- [ ] **Step 2.13: Update SessionManager to pass Session through**

Modify `packages/haywire-core/src/haywire/core/session/session_manager.py`:

- Locate `create_session` (find the call to `self._container.attach_session(...)`).
- Change it to `self._container.attach_session_with_ref(session_id, session)`, passing the freshly created `Session` instance.
- Also add AppState manager stamping. After `LibraryStateContainer` is bound (likely in `__init__` or `bind_to_lifecycle`), stamp `_session_manager` on every existing AppState instance and ensure newly added AppStates also get stamped.

Add to `LibraryStateContainer` in `container.py`:

```python
def bind_session_manager(self, manager: "SessionManager") -> None:
    """Stamp `_session_manager` weakref on every present and future AppState.

    Called once by SessionManager.__init__ right after constructing the container.
    """
    import weakref
    self._manager_ref: "weakref.ReferenceType[SessionManager]" = weakref.ref(manager)
    for app_state in self._app.values():
        app_state._session_manager = self._manager_ref

def _add_app_class(self, cls: type[AppState], registry_key: str) -> None:
    """Existing method — modify to stamp manager weakref before on_enable."""
    if registry_key in self._app:
        return
    instance = cls()
    if hasattr(self, "_manager_ref"):
        instance._session_manager = self._manager_ref
    self._app[registry_key] = instance
    self._class_by_registry_key[registry_key] = cls
    self._call_on_enable(instance)
```

In `session_manager.py`, after the container is created (look in `SessionManager.__init__` — find where `self._container = ...` is set), add:

```python
self._container.bind_session_manager(self)
```

- [ ] **Step 2.14: Run the full test suite to catch regressions**

```sh
uv run pytest -x
```

Expected: green. (Existing tests use `attach_session` without ref; that path still works for legacy callers; the new path is used by `SessionManager`.)

- [ ] **Step 2.15: Run ruff + mypy on modified files**

```sh
uv run ruff check packages/haywire-core/src/haywire/core/session/context.py packages/haywire-core/src/haywire/core/state/base.py packages/haywire-core/src/haywire/core/state/container.py packages/haywire-core/src/haywire/core/session/session_manager.py
uv run mypy packages/haywire-core/src/
```

Expected: no new errors. (Pre-edit baseline is the comparison.)

- [ ] **Step 2.16: Commit**

```sh
git add packages/haywire-core/src/haywire/core/session/context.py \
        packages/haywire-core/src/haywire/core/state/base.py \
        packages/haywire-core/src/haywire/core/state/container.py \
        packages/haywire-core/src/haywire/core/session/session_manager.py \
        tests/core/test_signals/test_app_state_broadcast.py \
        tests/core/test_signals/test_session_state_post_cleanup.py
git commit -m "feat(signals): wire SignalSource into host bases

SessionContext, SessionState, AppState now inherit SignalSource and
implement _signal_emit per scope:
  - SessionContext._signal_emit → self.session.publish(signal)
  - SessionState._signal_emit → self.session().publish(signal) via weakref
  - AppState._signal_emit → self._session_manager().broadcast(signal)

LibraryStateContainer.attach_session_with_ref stamps `self.session`
weakref on SessionState instances before on_enable. bind_session_manager
stamps `self._session_manager` weakref on every present and future AppState.

No fields use signal_field yet; this commit only adds the publish glue."
```

---

## Task 3: Migrate SessionContext fields; delete the four dead Active*Moved classes

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/session/context.py` (5 field declarations + ~15 `.value` read/write sites)
- Modify: `packages/haywire-core/src/haywire/core/session/events.py` (delete `ActiveFileMoved`, `ActiveLibraryMoved`, `ActiveComponentMoved`, `ThemeMoved`)
- Modify: `packages/haywire-core/src/haywire/core/session/__init__.py` (drop deleted names from `__all__`)
- Modify: `packages/haywire-studio/src/haywire_studio/app.py:233-234` (`.value =` → bare assignment)
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py:93,94,101,114` (read/write `.value` sites)
- Migrate: every `@redraw_on(ActiveFileMoved)` etc. → `@redraw_on(SessionContext.active_file)` etc.

After this task: SessionContext is fully migrated; the four dead event classes are gone; all subscribers point at synthetic signal classes.

- [ ] **Step 3.1: Establish the audit grep baseline**

Run and save outputs (these surface every site needing rewrite):

```sh
grep -rn "ActiveFileMoved\|ActiveLibraryMoved\|ActiveComponentMoved\|ThemeMoved" --include="*.py" packages barn tests > /tmp/active_moved_sites.txt
grep -rn "ctx\.active_file\.value\|ctx\.active_library\.value\|ctx\.active_component\.value\|active_workbench_theme_key\.value\|active_node_theme_key\.value" --include="*.py" packages barn tests > /tmp/context_value_sites.txt
```

Read both files. The plan steps below assume these are the only sites — if more appear in your grep, rewrite them following the same patterns.

- [ ] **Step 3.2: Rewrite SessionContext field declarations**

Modify `packages/haywire-core/src/haywire/core/session/context.py`:

- Update imports near the top — replace the line `from haywire.core.session.reactive import Reactive, iter_reactive_fields, reactive_field` with:
  ```python
  from haywire.core.session.signals import signal_field
  from haywire.core.session.signals.descriptor import _seed_signal_fields
  ```
- Update the field declarations (around line 65). Old:
  ```python
  active_file: Reactive[Optional[Any]] = reactive_field(None)
  active_library: Reactive[Optional["LibraryInfo"]] = reactive_field(None)
  active_component: Reactive[Optional[str]] = reactive_field(None)
  active_workbench_theme_key: Reactive[Optional[str]] = reactive_field(None)
  active_node_theme_key: Reactive[Optional[str]] = reactive_field(None)
  ```
  New:
  ```python
  active_file: Optional[Any] = signal_field(None)
  active_library: Optional["LibraryInfo"] = signal_field(None)
  active_component: Optional[str] = signal_field(None)
  active_workbench_theme_key: Optional[str] = signal_field(None)
  active_node_theme_key: Optional[str] = signal_field(None)
  ```
- In `__init__`, replace the `iter_reactive_fields(...)` init loop with:
  ```python
  _seed_signal_fields(self)
  ```

- [ ] **Step 3.3: Rewrite `.value` read/write sites on SessionContext fields**

For each site found in `/tmp/context_value_sites.txt`, rewrite:

- `ctx.active_file.value` (read) → `ctx.active_file`
- `ctx.active_file.value = x` (write) → `ctx.active_file = x`

Known sites to fix:

`packages/haywire-studio/src/haywire_studio/app.py:233-234`:

```python
# before
haywire_session.context.active_workbench_theme_key.value = "core:theme:workbench:haywire-dark"
haywire_session.context.active_node_theme_key.value = "core:theme:node:default"
# after
haywire_session.context.active_workbench_theme_key = "core:theme:workbench:haywire-dark"
haywire_session.context.active_node_theme_key = "core:theme:node:default"
```

`packages/haywire-core/src/haywire/ui/app/shell.py:93-94`:

```python
# before
context.active_workbench_theme_key.value = wb_theme_key
theme = theme_registry.get_workbench(context.active_workbench_theme_key.value)
# after
context.active_workbench_theme_key = wb_theme_key
theme = theme_registry.get_workbench(context.active_workbench_theme_key)
```

`packages/haywire-core/src/haywire/ui/app/shell.py:100-101`:

```python
# Inspect context: this looks like a setting-name dispatch, not a ctx.active_* read.
# Look at the surrounding 10 lines. If `value` here is a Reactive[...] for a
# SessionContext field, rewrite as above. If it's a settings descriptor's
# value (separate system), leave it alone.
```

`packages/haywire-core/src/haywire/ui/app/shell.py:114`:

```python
# before
context.active_workbench_theme_key.value = registry_key
# after
context.active_workbench_theme_key = registry_key
```

For any other hit in `/tmp/context_value_sites.txt`, apply the same pattern. Read each surrounding context first; do not blindly s/.value//.

- [ ] **Step 3.4: Rewrite subscribers in /tmp/active_moved_sites.txt**

For each `@redraw_on(ActiveFileMoved)` or `@react_on(ActiveFileMoved)` etc., rewrite to use the synthetic signal class:

- `ActiveFileMoved` → `SessionContext.active_file`
- `ActiveLibraryMoved` → `SessionContext.active_library`
- `ActiveComponentMoved` → `SessionContext.active_component`
- `ThemeMoved` → `SessionContext.active_workbench_theme_key` (and/or `active_node_theme_key` — read each subscriber's intent; if the subscriber wants both, list both signals in the decorator)

Each subscriber file gets a new import:

```python
from haywire.core.session.context import SessionContext
```

And drops `ActiveFileMoved` (etc.) from its existing imports.

- [ ] **Step 3.5: Delete the four event classes**

Modify `packages/haywire-core/src/haywire/core/session/events.py`:

- Find each of `ActiveFileMoved`, `ActiveLibraryMoved`, `ActiveComponentMoved`, `ThemeMoved` class definitions and delete them.
- Remove them from any `__all__` list in the file.

Modify `packages/haywire-core/src/haywire/core/session/__init__.py`:

- Remove them from the re-export `__all__`.
- Remove `from .events import ActiveFileMoved, ...` if present.

- [ ] **Step 3.6: Run the full test suite**

```sh
uv run pytest -x
```

Expected: green. Any failure here is either:

- (a) An import error pointing at a missed subscriber — rewrite that subscriber per step 3.4.
- (b) A `.value` read/write that the grep missed — rewrite per step 3.3.
- (c) A genuine regression — investigate.

- [ ] **Step 3.7: Run ruff + mypy**

```sh
uv run ruff check packages/haywire-core/src/haywire/core/session/ packages/haywire-studio/src/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/
```

Expected: no new errors.

- [ ] **Step 3.8: Manual smoke test — launch the app**

```sh
uv run haywire
```

Open the app in a browser. Verify:

- Workbench loads without console errors.
- Theme dropdown still applies a theme (writes `active_workbench_theme_key`).
- Opening a file in the file browser still works (writes `active_file`).

If anything is broken, find the symptom in the dev console and rewrite the relevant `.value` site.

Kill the dev server.

- [ ] **Step 3.9: Commit**

```sh
git add packages/haywire-core/src/haywire/core/session/context.py \
        packages/haywire-core/src/haywire/core/session/events.py \
        packages/haywire-core/src/haywire/core/session/__init__.py \
        packages/haywire-studio/src/haywire_studio/app.py \
        packages/haywire-core/src/haywire/ui/app/shell.py
# Plus any subscriber files modified in step 3.4 — list them explicitly.
git commit -m "refactor(signals): migrate SessionContext fields to signal_field

Five fields on SessionContext (active_file, active_library,
active_component, active_workbench_theme_key, active_node_theme_key)
now use signal_field. Writes emit on the session's bus; subscribers
reference the field directly:

  @redraw_on(SessionContext.active_file)
  def _on(self, ctx, signal): ...

Delete the four field-mirroring event classes that nothing published:
ActiveFileMoved, ActiveLibraryMoved, ActiveComponentMoved, ThemeMoved.

Subscribers wired to the deleted classes were dead (no emitter); this
commit converts them to live subscriptions for the first time."
```

---

## Task 4: Migrate `EditState`, `FileBrowserState`, and the `haybale-testing` fixture

**Files:**

- Modify: barn `EditState` source — `barn/haybale-core/haybale_core/state.py` (or wherever `EditState` is defined; locate with `grep -rn "class EditState" barn`)
- Modify: barn `FileBrowserState` source — locate with `grep -rn "class FileBrowserState" barn`
- Modify: `barn/haybale-testing/haybale_testing/...` fixture state — locate with `grep -rn "reactive_field\|Reactive\[" barn/haybale-testing`
- Modify: `tests/studio/test_edit_state.py:80` — rewrite `.value.add(...)` pattern
- Modify: every `.value` read/write site for these states (~35 sites — survey with grep)

After this task: every reactive_field in the codebase has become signal_field; no `.value` access remains on EditState/FileBrowserState fields.

- [ ] **Step 4.1: Locate the state classes**

```sh
grep -rn "class EditState\|class FileBrowserState" barn --include="*.py"
grep -rn "reactive_field\|Reactive\[" barn --include="*.py" > /tmp/barn_reactive_sites.txt
```

Read the locations. The plan steps below refer to "EditState file" generically — substitute the actual path.

- [ ] **Step 4.2: Migrate EditState declarations**

In the EditState file:

- Replace the import:
  ```python
  # before
  from haywire.core.session.reactive import Reactive, reactive_field, iter_reactive_fields
  # after
  from haywire.core.session.signals import signal_field
  from haywire.core.session.signals.descriptor import _seed_signal_fields
  ```
- Rewrite each field. `EditState` (per spec) has 8 fields: `active_graph`, `active_graph_path`, `active_node`, `active_edge`, `active_port`, `selected_nodes`, `selected_edges`, `clipboard`.

  Pattern:
  ```python
  # before
  active_node: Reactive[Optional[NodeWrapper]] = reactive_field(None)
  selected_nodes: Reactive[set[str]] = reactive_field(set())
  # after
  active_node: Optional[NodeWrapper] = signal_field(None)
  selected_nodes: set[str] = signal_field(set())
  ```
- Replace any hand-written `__init__` init loop that calls `iter_reactive_fields(...)` with:
  ```python
  def __init__(self) -> None:
      _seed_signal_fields(self)
  ```
  Or, if `EditState` previously did **not** declare `__init__` (relying on inherited behavior from a base), remove the loop entirely — the new `SessionState.__init__` (or wherever `_seed_signal_fields` lands) does it. If the spec's "SessionState base class implements __init__ that calls _seed_signal_fields" hasn't yet been added, add it now:

  In `packages/haywire-core/src/haywire/core/state/base.py`, on the `SessionState` class:
  ```python
  def __init__(self) -> None:
      from haywire.core.session.signals.descriptor import _seed_signal_fields
      _seed_signal_fields(self)
  ```
  And on `AppState`:
  ```python
  def __init__(self) -> None:
      from haywire.core.session.signals.descriptor import _seed_signal_fields
      _seed_signal_fields(self)
  ```

- [ ] **Step 4.3: Rewrite `.value` read/write sites for EditState fields**

For each line in `/tmp/barn_reactive_sites.txt` and any matching site under `packages/`, rewrite `.value` access:

- `edit.active_node.value` → `edit.active_node`
- `edit.active_node.value = x` → `edit.active_node = x`
- `edit.selected_nodes.value.add("x")` (in-place mutation, SILENT — flag in the audit) → see step 4.4

- [ ] **Step 4.4: Rewrite the in-place mutation site at `tests/studio/test_edit_state.py:80`**

Read [tests/studio/test_edit_state.py:75-90](../../../tests/studio/test_edit_state.py#L75-L90). The line:

```python
a.selected_nodes.value.add("node-1")
```

Rewrite to reassignment (so the signal emits):

```python
a.selected_nodes = a.selected_nodes | {"node-1"}
```

Confirm the test still asserts what it intended — if the test was about "the set contains node-1", that's still true.

Audit for other in-place-mutation patterns:

```sh
grep -rn "\.value\.\(add\|remove\|clear\|append\|update\|pop\|extend\|discard\)" packages barn tests --include="*.py"
```

For each hit on an EditState/FileBrowserState/SessionContext field: decide if the emit matters. If it does, rewrite as reassignment. If it doesn't (it's a debug helper that nobody reads), leave it and add a `# silent: deliberate in-place mutation` comment.

- [ ] **Step 4.5: Migrate FileBrowserState (1 field: `right_clicked_file`)**

Same pattern as EditState. Locate the file via grep, change `Reactive[Optional[Path]] = reactive_field(None)` → `Optional[Path] = signal_field(None)`, rewrite read/write sites.

- [ ] **Step 4.6: Migrate `haybale-testing` fixture (1 field: `counter`)**

```sh
grep -rn "counter" barn/haybale-testing --include="*.py" | head -10
```

Locate the fixture state class. Rewrite the same way.

- [ ] **Step 4.7: Run the full test suite**

```sh
uv run pytest -x
```

Expected: green. Likely failures:

- Tests that asserted on the old `.value` interface — rewrite them to bare attribute access.
- Tests that relied on the missing `.add()`-style silent behavior to set up state — those tests now also produce a signal; if any handler is wired during the test setup and counts emits, the count is now off.

For each, look at what the test was actually trying to verify. Update accordingly.

- [ ] **Step 4.8: Run ruff + mypy**

```sh
uv run ruff check packages barn tests
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ \
            barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ \
            barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ \
            barn/haybale-visiongraph/haybale_visiongraph/ barn/haybale-TEST_A/haybale_test_a/
```

Expected: no new errors.

- [ ] **Step 4.9: Manual smoke test in the app**

```sh
uv run haywire
```

In the browser:

- Open a graph file.
- Select a node — verify the inspector panel updates (`active_node` write should emit; inspector subscribes to it).
- Multi-select with shift+click — verify the selection panel updates (`selected_nodes` write should emit).
- Right-click a file in the file browser — verify the context menu appears (`right_clicked_file` write should emit).

If anything regresses, the symptom is almost certainly a missed `.value` site or a missed subscriber. Find via grep.

Kill the dev server.

- [ ] **Step 4.10: Commit**

```sh
git add barn packages tests
git commit -m "refactor(signals): migrate EditState, FileBrowserState, haybale-testing

Ten signal fields on EditState (8), FileBrowserState (1), and the
haybale-testing fixture (1) now use signal_field. All ~35 .value
read/write sites rewritten to bare attribute access.

Notable: tests/studio/test_edit_state.py:80 had a silent in-place
mutation (selected_nodes.value.add(...)) that did not emit under
the old Reactive[T]; rewritten to reassignment so the signal fires.

SessionState.__init__ and AppState.__init__ now seed signal-field
storage via _seed_signal_fields; subclasses no longer hand-roll
the init loop."
```

---

## Task 5: Delete the old surface (`Reactive`, `ReactivePath`, `Event`, `ContextSignal`, `EventBus`, `LifecycleCommand`); rename remaining bus imports

**Files:**

- Delete: `packages/haywire-core/src/haywire/core/session/reactive/` (entire directory: `reactive.py`, `path.py`, `descriptor.py`, `__init__.py`)
- Modify: `packages/haywire-core/src/haywire/core/session/__init__.py` (drop old imports/exports)
- Delete: `packages/haywire-core/src/haywire/core/session/bus.py` (the old `EventBus` — replaced by `signals/bus.py`)
- Delete: `packages/haywire-core/src/haywire/core/session/events.py` (the old `Event`, `ContextSignal`, `LifecycleCommand`)
- Modify: `packages/haywire-core/src/haywire/core/session/session.py` — `Event` → `Signal`, `EventBus` → `SignalBus`
- Modify: `packages/haywire-core/src/haywire/core/session/session_manager.py` — `Event` → `Signal`
- Modify: `packages/haywire-core/src/haywire/core/session/handlers.py` — `validate_event_types` → `validate_signal_types`, `ContextSignal` → `Signal`, `Event` → `Signal` (parameter types)
- Modify: `packages/haywire-core/src/haywire/ui/panel/decorator.py` — `validate_event_types` import rename
- Modify: every concrete hand-authored event/signal class — `class SelectionMoved(ContextSignal):` → `class SelectionMoved(Signal):`
- Modify: every `Type[Event]` parameter annotation → `Type[Signal]`

After this task: no `Event`, `ContextSignal`, `EventBus`, `LifecycleCommand`, `Reactive`, `ReactivePath` symbols remain in the codebase. Only the Signal vocabulary exists.

- [ ] **Step 5.1: Audit grep — list every site referencing the old names**

```sh
grep -rn "from haywire.core.session.events\|from haywire.core.session.bus\|from haywire.core.session.reactive\|\\bEvent\\b\|\\bEventBus\\b\|\\bEventHandler\\b\|\\bContextSignal\\b\|\\bLifecycleCommand\\b\|\\bReactive\\b\|\\bReactivePath\\b\|validate_event_types" --include="*.py" packages barn tests > /tmp/old_names_sites.txt
wc -l /tmp/old_names_sites.txt
```

This is your full migration checklist. Many hits will be false positives (`Event` appears in `LifeCycleEvent`, which is a different name) — read each before changing.

- [ ] **Step 5.2: Rename concrete `ContextSignal` subclasses → direct `Signal` subclasses**

Find every hand-authored event/signal class:

```sh
grep -rn "class .*(ContextSignal)" --include="*.py" packages barn
grep -rn "class .*(Event)" --include="*.py" packages barn
grep -rn "class .*(LifecycleCommand)" --include="*.py" packages barn
```

For each:

- `class SelectionMoved(ContextSignal):` → `class SelectionMoved(Signal):`
- `class GraphDataMutated(ContextSignal):` → `class GraphDataMutated(Signal):`
- `class Reveal(LifecycleCommand):` → `class Reveal(CommandSignal):`
- etc.

Update each file's imports accordingly:

- `from haywire.core.session.events import ContextSignal` → `from haywire.core.session.signals import Signal`
- `from haywire.core.session.events import LifecycleCommand` → `from haywire.core.session.signals import CommandSignal`

- [ ] **Step 5.3: Rewrite the bus consumer surface in Session, SessionManager, handlers**

`packages/haywire-core/src/haywire/core/session/session.py`:

- `from haywire.core.session.bus import EventBus` → `from haywire.core.session.signals import SignalBus`
- `from haywire.core.session.events import Event` → `from haywire.core.session.signals import Signal`
- `E = TypeVar("E", bound=Event)` → `E = TypeVar("E", bound=Signal)`
- `self._bus: EventBus = EventBus()` → `self._bus: SignalBus = SignalBus()`
- Every `event: Event` parameter / `event_type: Type[E]` → `signal: Signal` / `signal_type: Type[E]`
- Method names: `publish(event: Event)` keeps the name `publish`; only types rename. (The decorator names `@redraw_on` / `@react_on` are unchanged per Q12-D / V6.)
- The legacy alias `signal = publish` is deleted (the name is now ambiguous — Signal is a type, not a verb). Update any callers of `session.signal(...)` to `session.publish(...)`.

`packages/haywire-core/src/haywire/core/session/session_manager.py`:

- `Event` → `Signal` throughout.
- Same parameter renames.

`packages/haywire-core/src/haywire/core/session/handlers.py`:

- `from haywire.core.session.events import ContextSignal` → `from haywire.core.session.signals import Signal`
- `validate_event_types` → `validate_signal_types` (rename function + every call site)
- `event_types: Tuple[Any, ...]` → `signal_types: Tuple[Any, ...]`
- `type[ContextSignal]` → `type[Signal]`
- Any `Type[Event]` → `Type[Signal]`

`packages/haywire-core/src/haywire/ui/panel/decorator.py:22`:

- `from haywire.core.session.handlers import validate_event_types` → `from haywire.core.session.handlers import validate_signal_types`
- Update the call site at line 94.

- [ ] **Step 5.4: Delete the old source files**

```sh
rm packages/haywire-core/src/haywire/core/session/reactive/reactive.py
rm packages/haywire-core/src/haywire/core/session/reactive/path.py
rm packages/haywire-core/src/haywire/core/session/reactive/descriptor.py
rm packages/haywire-core/src/haywire/core/session/reactive/__init__.py
rmdir packages/haywire-core/src/haywire/core/session/reactive
rm packages/haywire-core/src/haywire/core/session/bus.py
rm packages/haywire-core/src/haywire/core/session/events.py
```

- [ ] **Step 5.5: Update `session/__init__.py`**

Modify `packages/haywire-core/src/haywire/core/session/__init__.py`:

- Remove imports: `Reactive`, `reactive_field`, `iter_reactive_fields`, `ReactivePath`, `Event`, `EventBus`, `EventHandler`, `ContextSignal`, `LifecycleCommand`, `ActiveFileMoved` (already gone), etc.
- Add imports from the new module:
  ```python
  from .signals import Signal, CommandSignal, SignalBus, SignalHandler, SignalSource, signal_field
  ```
- Update `__all__` to drop deleted names and add the new ones.

- [ ] **Step 5.6: Rename existing bus test files**

```sh
git mv tests/core/test_session/test_event_bus.py tests/core/test_session/test_signal_bus.py
# (Adjust if the actual filename differs — locate with `find tests -name "*event_bus*"`)
```

Inside the renamed file, rewrite `Event` → `Signal`, `EventBus` → `SignalBus`, `ContextSignal` → `Signal`, etc.

- [ ] **Step 5.7: Run the full test suite**

```sh
uv run pytest -x
```

Expected: green. Failures here are almost all import errors pointing at a missed site from `/tmp/old_names_sites.txt`. Walk the failure trace to the file, rewrite, re-run.

- [ ] **Step 5.8: Run ruff + mypy across the full surface**

```sh
uv run ruff check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ \
            barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ \
            barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ \
            barn/haybale-visiongraph/haybale_visiongraph/ barn/haybale-TEST_A/haybale_test_a/
```

Expected: zero errors. (Matches pre-edit baseline.)

- [ ] **Step 5.9: Manual smoke test — full app walk**

```sh
uv run haywire
```

Exercise the golden path:

- Launch → workbench loads.
- Open a graph file → file shows in editor.
- Connect two nodes → connection wires up; graph state mutates.
- Select / multi-select / clear selection → inspector updates each time.
- Switch themes → both workbench and node themes update.
- Right-click a file → context menu appears.
- Close the file → editor unmounts.

If any step regresses, find the broken signal handler — most likely a stale `Type[Event]` annotation that didn't get caught by mypy because it was behind a string literal.

Kill the dev server.

- [ ] **Step 5.10: Commit**

```sh
git add -A
git commit -m "refactor(signals): delete old Event/Reactive surface; rename bus

Delete:
- session/reactive/ (Reactive[T], ReactivePath, old descriptor)
- session/bus.py (EventBus, EventHandler)
- session/events.py (Event, ContextSignal, LifecycleCommand)

Rename across the codebase:
- Event → Signal
- ContextSignal → (deleted; concrete signals inherit Signal directly)
- LifecycleCommand → CommandSignal
- EventBus → SignalBus
- EventHandler → SignalHandler
- validate_event_types → validate_signal_types
- Session.signal alias deleted (the verb 'signal' now collides with
  the noun 'Signal'; callers use Session.publish directly)

No behavior change beyond the rename and the deletion of unused
Reactive[T]/ReactivePath shims. Hand-authored signal classes
(SelectionMoved, GraphDataMutated, etc.) keep their names; they
just inherit Signal directly."
```

---

## Task 6: Hot-reload round-trip test; docs rewrite

**Files:**

- Create: `tests/core/test_signals/test_hot_reload_roundtrip.py`
- Modify: `docs/architecture/session-and-state/session-and-state-arch.md`
- Modify: `packages/haywire-core/src/haywire/core/session/context.py` (`SessionContext` docstring)
- Modify: EditState docstring (in its file)
- Modify: `packages/haywire-core/src/haywire/core/session/signals/__init__.py` docstring
- Modify: `packages/haywire-core/src/haywire/core/session/signals/descriptor.py` docstring
- Modify: `packages/haywire-core/src/haywire/core/session/signals/host.py` docstring
- Modify: `internals/speculatives/reactive_bus_unification.md` — mark as **Done**; optionally move to `internals/decisions/`
- Modify: `internals/speculatives/event_bus_redesign.md` — strike or update the paragraph that references Reactive/Phase-2

After this task: docs are aligned with what the code does; the spec is marked done; the hot-reload contract has a regression test.

- [ ] **Step 6.1: Write the hot-reload round-trip test**

Create `tests/core/test_signals/test_hot_reload_roundtrip.py`:

```python
"""Hot-reload round-trip: a SessionState class is reloaded; subscriptions
to the old class's synthetic signal must be cleaned up via editor
teardown, and new subscriptions to the reloaded class's synthetic
signal must receive emits.

This codifies the Q15 decision: synthetic signal classes participate as
first-class Signal subclasses with no special reload handling. The
existing editor teardown/recreate path is the recovery mechanism."""
import importlib
import pytest


def test_hot_reload_creates_fresh_signal_class():
    """Reloading the module that defines a SessionState produces a new
    class object and a new synthetic signal class. Subscribers to the
    old class's signal do NOT receive emits through the new class."""
    # Use a dedicated module for this test (added in step 6.2).
    import tests.core.test_signals._hot_reload_target as target

    OldState = target.MyState
    OldSignal = OldState.x  # synthetic Signal subclass

    # Reload.
    importlib.reload(target)
    NewState = target.MyState
    NewSignal = NewState.x

    # Different class objects.
    assert OldState is not NewState
    assert OldSignal is not NewSignal
    # Both still inherit Signal.
    from haywire.core.session.signals import Signal
    assert issubclass(OldSignal, Signal)
    assert issubclass(NewSignal, Signal)


def test_old_class_subscribers_do_not_receive_new_class_emits():
    """A handler subscribed via the bus to OldSignal does NOT fire when
    a NewState instance writes its field."""
    import tests.core.test_signals._hot_reload_target as target
    from haywire.core.session.signals import SignalBus

    OldState = target.MyState
    OldSignal = OldState.x

    importlib.reload(target)
    NewState = target.MyState

    bus = SignalBus()
    received = []
    bus.subscribe(OldSignal, lambda s: received.append(s))

    new_instance = NewState(bus)
    new_instance.x = 99  # writes the new class's field; emits NewSignal

    assert received == []
```

- [ ] **Step 6.2: Create the hot-reload target module**

Create `tests/core/test_signals/_hot_reload_target.py`:

```python
"""Module reloaded by test_hot_reload_roundtrip.py.

Holds a minimal SignalSource so the test can exercise the reload path
without setting up a full Session/Container."""
from haywire.core.session.signals import Signal, SignalSource, signal_field
from haywire.core.session.signals.descriptor import _seed_signal_fields


class MyState(SignalSource):
    x: int = signal_field(0)

    def __init__(self, bus):
        self._bus = bus
        _seed_signal_fields(self)

    def _signal_emit(self, signal: Signal) -> None:
        self._bus.publish(signal)
```

- [ ] **Step 6.3: Run the test, verify it passes**

```sh
uv run pytest tests/core/test_signals/test_hot_reload_roundtrip.py -v
```

Expected: 2 PASS.

- [ ] **Step 6.4: Rewrite `docs/architecture/session-and-state/session-and-state-arch.md`**

Read the existing file first:

```sh
cat docs/architecture/session-and-state/session-and-state-arch.md | head -100
```

Find every reference to:

- `Reactive[T]` / `.value` → describe signal fields as bare attribute access
- `ActiveFileMoved` / `ActiveLibraryMoved` / `ActiveComponentMoved` / `ThemeMoved` → describe synthetic signals via `SessionContext.active_file` etc.
- `Event` / `EventBus` / `ContextSignal` / `LifecycleCommand` → rename to `Signal` / `SignalBus` / (direct Signal) / `CommandSignal`
- `reactive_field` → `signal_field`

Add a new section "Signal fields" explaining the model. Keep it brief — the spec is the canonical reference; the docs should describe what the system **is**, not the design rationale.

- [ ] **Step 6.5: Rewrite the SessionContext docstring**

Modify `packages/haywire-core/src/haywire/core/session/context.py` — find the `SessionContext` class docstring (around the line 27 area). Rewrite to describe the new model:

```python
class SessionContext(SignalSource):
    """Per-session context: holds five signal fields that scoped editors
    and panels subscribe to.

    Reading: bare attribute access — `ctx.active_file`.
    Writing: bare attribute access — `ctx.active_file = new_path`.
    Identity-equal writes are no-ops.

    Subscribing: reference the class-level field as the signal type:
        @redraw_on(SessionContext.active_file)
        def _on(self, ctx, signal): ...

    The framework synthesizes one Signal subclass per field at class
    definition; the field reference IS the subscription key. There is
    no separate event class to import.
    """
```

- [ ] **Step 6.6: Rewrite EditState's docstring**

Same pattern. Locate the file via `grep -rn "class EditState" barn`. Update.

- [ ] **Step 6.7: Write module-level docstrings for the new signals/ package**

Each of `signals/__init__.py`, `signals/descriptor.py`, `signals/host.py`, `signals/signal.py`, `signals/bus.py` should have a top-of-file docstring describing what's in it and the design intent. These were written as part of Task 1; review them now and tighten if needed.

- [ ] **Step 6.8: Mark the spec as done**

Modify the top of `internals/speculatives/reactive_bus_unification.md`:

```markdown
# Signal-field unification

Status: **DONE** — landed in <merge-commit-hash>. Originally:
"Reactive fields unified with the event bus" draft. Builds on
`event_bus_redesign.md`.
```

(Fill in the actual merge commit hash post-merge; for the commit, use a placeholder `<TBD-after-merge>` and update in the PR description.)

Optionally `git mv internals/speculatives/reactive_bus_unification.md internals/decisions/2026-05-15-signal-field-unification.md`. Check whether `internals/decisions/` is a convention in this repo:

```sh
ls internals/
```

If `decisions/` exists, move it. If not, leave it where it is (the status header is sufficient).

- [ ] **Step 6.9: Update the older speculative doc**

Modify `internals/speculatives/event_bus_redesign.md`. Find the paragraph that mentions `Reactive[T]` / "Phase 2" / `iter_reactive_fields`. Rewrite to point at the signal-field unification doc and note that Phase 2's planned auto-tracking was explicitly rejected.

- [ ] **Step 6.10: Run the full verification suite one more time**

```sh
uv run ruff check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ \
            barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ \
            barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ \
            barn/haybale-visiongraph/haybale_visiongraph/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest
```

Expected: green.

- [ ] **Step 6.11: Final commit**

```sh
git add docs internals tests/core/test_signals/test_hot_reload_roundtrip.py tests/core/test_signals/_hot_reload_target.py
# Plus the files modified for docstring updates:
git add packages/haywire-core/src/haywire/core/session/
git commit -m "docs(signals): rewrite session/state docs; mark spec done; hot-reload test

- docs/architecture/session-and-state-arch.md updated for the Signal
  vocabulary and signal-field semantics.
- SessionContext and EditState class docstrings rewritten.
- signals/ module docstrings tightened.
- internals/speculatives/reactive_bus_unification.md marked Done.
- internals/speculatives/event_bus_redesign.md updated to remove the
  Reactive/Phase-2 reference.
- tests/core/test_signals/test_hot_reload_roundtrip.py codifies the
  Q15 contract: synthetic signal classes get the same hot-reload
  treatment as hand-authored signals; recovery is via editor
  teardown/recreate."
```

---

## Post-merge cleanup

- [ ] Update the spec's "DONE" line with the actual merge commit hash.
- [ ] If `git mv` to `internals/decisions/` was skipped in step 6.8, decide whether to move it now.
- [ ] If any AppState reactive field landed during the PR (none planned per spec, but a follow-up library might add one), exercise the broadcast path in production once and watch logs for `_session_manager is None` warnings.

---

## Self-review checklist

Before opening the PR, verify:

- [ ] Pre-edit baseline (`ruff` + `mypy` + `pytest`) is green at HEAD~6 (the commit before Task 1).
- [ ] Post-edit suite is green at HEAD (final commit).
- [ ] No occurrence of `\\bEvent\\b` (as a class name) remains:
      `grep -rn "\\bEvent\\b" packages barn --include="*.py" | grep -v LifeCycleEvent | grep -v "comment\|docstring"`
- [ ] No occurrence of `\\bReactive\\b`, `\\bReactivePath\\b`, `\\bContextSignal\\b`, `\\bEventBus\\b`, `\\bLifecycleCommand\\b`, `\\bActiveFileMoved\\b`, `\\bActiveLibraryMoved\\b`, `\\bActiveComponentMoved\\b`, `\\bThemeMoved\\b`.
- [ ] No occurrence of `\\.value\\.\\(add\\|remove\\|clear\\)` on a signal-field instance.
- [ ] Each commit is independently buildable and tested (run `git rebase -i HEAD~6 --exec 'uv run pytest -x'` to verify).
- [ ] Manual smoke test in the browser exercised: file open, node select, multi-select, theme switch, file right-click — all golden.

---

## Execution handoff

Plan complete and saved to `internals/superpowers/plans/2026-05-15-signal-field-unification.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
