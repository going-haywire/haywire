# LibraryState v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new extension point — `LibraryState` — that lets library plugins declare app-global runtime data structures, with class-keyed access (`ctx.data[MyState]`) on both `SessionContext` (UI) and `ExecutionContext` (node execution).

**Architecture:** Two-component split following the existing `NodeRegistry`/`NodeFactory` pattern. `LibraryStateRegistry` (BaseRegistry subclass) holds the *classes*, discovered via folder-scan with the existing hot-reload + dependency-graph machinery. `LibraryStateContainer` holds the *instances* — a flat `dict[type, LibraryState]` — and subscribes to the registry's batch lifecycle events to instantiate/destroy and call `on_enable`/`on_disable`. A typed proxy `_DataNamespace` exposes the container via `__getitem__[T]` on both context objects. The VM holds a container reference and populates `ExecutionContext.data` per execution.

**Tech Stack:** Python 3.10+, `injector` DI library, existing haywire BaseRegistry framework, pytest.

**Source spec:** [`internals/speculative/spec_library_state.md`](../../speculative/spec_library_state.md). v1 only — Phase 2 observable container is bound to the broader `spec_panel_reactivity.md` work and is out of scope.

---

## File structure

### New files

| File | Responsibility |
|------|----------------|
| `packages/haywire-core/src/haywire/core/state/__init__.py` | Public exports — `LibraryState`, `LibraryStateRegistry`, `LibraryStateContainer` |
| `packages/haywire-core/src/haywire/core/state/base.py` | `LibraryState` base class with optional `on_enable`/`on_disable` |
| `packages/haywire-core/src/haywire/core/state/identity.py` | `LibraryStateClassIdentity` dataclass — created at registration time so BaseRegistry's `class_identity` requirement is met |
| `packages/haywire-core/src/haywire/core/state/registry.py` | `LibraryStateRegistry(BaseRegistry)` — class registry, no instance management |
| `packages/haywire-core/src/haywire/core/state/container.py` | `LibraryStateContainer` — owns the instance pool, subscribes to registry batch events |
| `packages/haywire-core/src/haywire/core/state/data_namespace.py` | `_DataNamespace` — typed proxy with `__getitem__[T]` and `get[T]` |
| `tests/core/test_state/__init__.py` | (empty) |
| `tests/core/test_state/test_library_state.py` | Unit tests — base class lifecycle hook duck-typing |
| `tests/core/test_state/test_registry.py` | Unit tests — class filter, register/unregister |
| `tests/core/test_state/test_container.py` | Unit tests — instance creation, on_enable/on_disable, dropping on unregister |
| `tests/core/test_state/test_data_namespace.py` | Unit tests — `[Cls]` lookup, `.get()`, KeyError, type generics |
| `tests/core/test_state/test_integration.py` | Integration test — full library enable→state→access cycle |

### Modified files

| File | Change |
|------|--------|
| `packages/haywire-core/src/haywire/core/di/config.py:39-225` | Add `provide_library_state_registry`, `provide_library_state_container` providers + container subscription wiring in `LibrarySystemService.initialize()` |
| `packages/haywire-core/src/haywire/ui/context.py:36-79` | Delete `metadata` field; add `data: _DataNamespace` field |
| `packages/haywire-core/src/haywire/ui/session.py:62-63` | Pass container into `SessionContext` constructor (sourced from app) |
| `packages/haywire-core/src/haywire/core/execution/execution_context.py:10-62` | Add `data: _DataNamespace` field |
| `packages/haywire-core/src/haywire/core/execution/vm.py:42-88` | Accept optional `library_state_container` in `__init__`; populate `ExecutionContext.data` in `_create_execution_context()` |
| `packages/haywire-core/src/haywire/core/execution/interpreter.py:65-79` | Forward `library_state_container` to `HaywireVM` |
| `packages/haywire-studio/src/haywire_studio/haystack.py:108` | Pass app's container into `Interpreter()` constructor |

---

## Task 1: `LibraryState` base class

**Files:**
- Create: `packages/haywire-core/src/haywire/core/state/__init__.py`
- Create: `packages/haywire-core/src/haywire/core/state/base.py`
- Test: `tests/core/test_state/__init__.py`
- Test: `tests/core/test_state/test_library_state.py`

- [ ] **Step 1: Create the test file with one failing test**

Write to `tests/core/test_state/__init__.py`:

```python
```

(empty file — just makes the package importable)

Write to `tests/core/test_state/test_library_state.py`:

```python
"""Unit tests for the LibraryState base class."""

import pytest

from haywire.core.state import LibraryState


class TestLibraryStateBase:
    def test_subclass_can_be_instantiated_with_no_arguments(self):
        class MyState(LibraryState):
            pass

        instance = MyState()
        assert isinstance(instance, LibraryState)

    def test_on_enable_is_optional(self):
        """A LibraryState without on_enable can still be instantiated."""

        class NoHooks(LibraryState):
            pass

        instance = NoHooks()
        assert not hasattr(instance, "on_enable") or callable(instance.on_enable)

    def test_on_enable_when_defined_is_callable(self):
        calls: list[str] = []

        class WithHooks(LibraryState):
            def on_enable(self) -> None:
                calls.append("enable")

            def on_disable(self) -> None:
                calls.append("disable")

        instance = WithHooks()
        instance.on_enable()
        instance.on_disable()
        assert calls == ["enable", "disable"]

    def test_subclass_can_carry_arbitrary_fields(self):
        """LibraryState imposes no field-level constraints."""

        class FullOfStuff(LibraryState):
            def __init__(self) -> None:
                self.devices: list[str] = []
                self.counter: int = 0

        instance = FullOfStuff()
        instance.devices.append("dev0")
        instance.counter += 1
        assert instance.devices == ["dev0"]
        assert instance.counter == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_state/test_library_state.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'haywire.core.state'` (the package doesn't exist yet).

- [ ] **Step 3: Create the package and base class**

Write to `packages/haywire-core/src/haywire/core/state/__init__.py`:

```python
"""Library-owned runtime state — see internals/speculative/spec_library_state.md."""

from haywire.core.state.base import LibraryState

__all__ = ["LibraryState"]
```

Write to `packages/haywire-core/src/haywire/core/state/base.py`:

```python
"""LibraryState base class.

A LibraryState is a Python class that a library declares to hold its own
app-global runtime data. The framework instantiates it once when the library
is enabled, owns its lifecycle, and exposes the instance through a uniform
class-keyed access pattern on both SessionContext (UI) and ExecutionContext
(node execution).

See internals/speculative/spec_library_state.md for the full design.
"""

from __future__ import annotations


class LibraryState:
    """Base class for library-owned runtime state.

    Subclasses may define optional lifecycle hooks:
        on_enable(self) -> None   — called once after instantiation
        on_disable(self) -> None  — called once before destruction

    Both hooks are duck-typed: absence is fine, the framework checks via
    hasattr/callable before invoking.

    Subclasses are otherwise unconstrained — fields, methods, internal state
    are entirely the author's choice.
    """
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_state/test_library_state.py -v`

Expected: All four tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/state/__init__.py \
        packages/haywire-core/src/haywire/core/state/base.py \
        tests/core/test_state/__init__.py \
        tests/core/test_state/test_library_state.py
git commit -m "feat(state): add LibraryState base class

Introduces haywire.core.state.LibraryState as the base for library-owned
app-global runtime state. Optional on_enable/on_disable lifecycle hooks
are duck-typed.

See internals/speculative/spec_library_state.md."
```

---

## Task 2: `LibraryStateClassIdentity` dataclass

**Why:** `BaseRegistry._register` requires every registered class to have a `class_identity` attribute. All identity classes in the codebase inherit from `BaseIdentity` (`packages/haywire-core/src/haywire/core/registry/identity.py:9`) — see existing examples: `NodeIdentity`, `PanelIdentity`, `SettingsClassIdentity`, `ThemeClassIdentity`, `EditorIdentity`, `WidgetIdentity`, `SkinIdentity`, `AdapterIdentity`, `DataTypeIdentity`. `LibraryStateClassIdentity` follows the same pattern.

`BaseIdentity` already carries `registry_id`, `registry_key`, `label`, `description`, `deprecation_warning`, `class_name`, `module` — every field LibraryState needs. The subclass adds nothing; it exists purely as a named type so the registry knows what kind of identity it built.

**Files:**
- Create: `packages/haywire-core/src/haywire/core/state/identity.py`
- Modify: `packages/haywire-core/src/haywire/core/state/__init__.py`
- Test: `tests/core/test_state/test_identity.py` (new)

- [ ] **Step 1: Write the failing test**

Write to `tests/core/test_state/test_identity.py`:

```python
"""Unit tests for LibraryStateClassIdentity."""

from haywire.core.registry.identity import BaseIdentity
from haywire.core.state.identity import LibraryStateClassIdentity


class TestLibraryStateClassIdentity:
    def test_inherits_from_base_identity(self):
        """All identity classes in the codebase inherit from BaseIdentity."""
        assert issubclass(LibraryStateClassIdentity, BaseIdentity)

    def test_carries_required_fields(self):
        ident = LibraryStateClassIdentity(
            registry_id="MidiPool",
            registry_key="midi:state:MidiPool",
            label="MidiPool",
            class_name="MidiPool",
            module="haybale_midi.state.midi_pool",
        )
        assert ident.registry_id == "MidiPool"
        assert ident.registry_key == "midi:state:MidiPool"
        assert ident.label == "MidiPool"
        assert ident.class_name == "MidiPool"
        assert ident.module == "haybale_midi.state.midi_pool"
        # Inherited defaults from BaseIdentity:
        assert ident.description == ""
        assert ident.deprecation_warning == ""
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/core/test_state/test_identity.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'haywire.core.state.identity'`.

- [ ] **Step 3: Create the identity dataclass**

Write to `packages/haywire-core/src/haywire/core/state/identity.py`:

```python
"""Class identity for LibraryState subclasses.

BaseRegistry requires every registered class to carry a `class_identity`
attribute. For LibraryStates — which have no decorator — the registry
attaches one of these at registration time, derived from the class and
its owning library.

Mirrors the pattern of NodeIdentity, PanelIdentity, SettingsClassIdentity,
ThemeClassIdentity, etc.: a plain @dataclass inheriting from BaseIdentity.
LibraryState needs no extra fields beyond what BaseIdentity provides
(registry_id, registry_key, label, class_name, module, ...).
"""

from __future__ import annotations

from dataclasses import dataclass

from haywire.core.registry.identity import BaseIdentity


@dataclass
class LibraryStateClassIdentity(BaseIdentity):
    """Identity attached to a LibraryState subclass at registration time."""
```

Modify `packages/haywire-core/src/haywire/core/state/__init__.py` to also export the identity:

```python
"""Library-owned runtime state — see internals/speculative/spec_library_state.md."""

from haywire.core.state.base import LibraryState
from haywire.core.state.identity import LibraryStateClassIdentity

__all__ = ["LibraryState", "LibraryStateClassIdentity"]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/core/test_state/test_identity.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/state/identity.py \
        packages/haywire-core/src/haywire/core/state/__init__.py \
        tests/core/test_state/test_identity.py
git commit -m "feat(state): add LibraryStateClassIdentity dataclass

Inherits from BaseIdentity, matching every other class identity in the
codebase (NodeIdentity, PanelIdentity, SettingsClassIdentity, etc.).
LibraryState needs no extra fields beyond BaseIdentity's defaults; the
subclass exists as a named type so the registry knows what kind of
identity it built."
```

---

## Task 3: `LibraryStateRegistry` (class registry, no instances)

**Files:**
- Create: `packages/haywire-core/src/haywire/core/state/registry.py`
- Modify: `packages/haywire-core/src/haywire/core/state/__init__.py`
- Test: `tests/core/test_state/test_registry.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/core/test_state/test_registry.py`:

```python
"""Unit tests for LibraryStateRegistry."""

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.state import LibraryState
from haywire.core.state.registry import LibraryStateRegistry


def make_lib_identity(lib_id: str = "midi") -> LibraryIdentity:
    """Build a minimal LibraryIdentity for tests."""
    return LibraryIdentity(
        id=lib_id,
        label=lib_id.capitalize(),
        version="0.0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        dependencies=[],
        tags=[],
        module_name=f"haybale_{lib_id}",
        folder_path="",
    )


class TestLibraryStateRegistry:
    def test_class_filter_accepts_subclass(self):
        class MyState(LibraryState):
            pass

        reg = LibraryStateRegistry()
        assert reg._class_filter(MyState) is True

    def test_class_filter_rejects_base_class(self):
        reg = LibraryStateRegistry()
        assert reg._class_filter(LibraryState) is False

    def test_class_filter_rejects_unrelated_class(self):
        class Unrelated:
            pass

        reg = LibraryStateRegistry()
        assert reg._class_filter(Unrelated) is False

    def test_register_class_creates_identity_and_stores_class(self):
        class MyState(LibraryState):
            pass

        reg = LibraryStateRegistry()
        lib_id = make_lib_identity()
        key = reg._register_class(MyState, lib_id)

        assert key == "midi:state:MyState"
        assert reg.has(key)
        assert reg.get(key) is MyState
        assert hasattr(MyState, "class_identity")
        assert MyState.class_identity.class_name == "MyState"
        assert MyState.class_identity.registry_key == "midi:state:MyState"

    def test_register_class_is_idempotent_for_same_class(self):
        class MyState(LibraryState):
            pass

        reg = LibraryStateRegistry()
        lib_id = make_lib_identity()
        first_key = reg._register_class(MyState, lib_id)
        # Re-registering the same class returns the same key without error.
        second_key = reg._register_class(MyState, lib_id)
        assert first_key == second_key

    def test_unregister_removes_class(self):
        class MyState(LibraryState):
            pass

        reg = LibraryStateRegistry()
        lib_id = make_lib_identity()
        key = reg._register_class(MyState, lib_id)
        removed = reg._unregister_class(key)

        assert removed is MyState
        assert not reg.has(key)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/core/test_state/test_registry.py -v`

Expected: FAIL — `LibraryStateRegistry` doesn't exist yet.

- [ ] **Step 3: Implement the registry**

Write to `packages/haywire-core/src/haywire/core/state/registry.py`:

```python
"""LibraryStateRegistry — class registry for LibraryState subclasses.

Holds *classes*, not instances. The companion LibraryStateContainer subscribes
to this registry's batch lifecycle events and manages instance lifecycle.

Same shape as NodeRegistry, PanelRegistry, etc.: inherits hot-reload,
dependency-graph, and folder-scan machinery from BaseRegistry.
"""

from __future__ import annotations

import inspect
import logging

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry
from haywire.core.state.base import LibraryState
from haywire.core.state.identity import LibraryStateClassIdentity

logger = logging.getLogger(__name__)


class LibraryStateRegistry(BaseRegistry):
    """Registry for LibraryState classes.

    Registry key format: '{library_id}:state:{class_name}'.
    """

    def _class_filter(self, cls: type) -> bool:
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, LibraryState)
                and cls is not LibraryState
            )
        except TypeError:
            return False

    def _register_class(
        self, cls: type, library_identity: LibraryIdentity
    ) -> str | None:
        """Attach a class_identity if missing, then delegate to BaseRegistry._register."""
        if not hasattr(cls, "class_identity"):
            registry_key = f"{library_identity.id}:state:{cls.__name__}"
            cls.class_identity = LibraryStateClassIdentity(
                registry_id=cls.__name__,
                registry_key=registry_key,
                label=cls.__name__,
                class_name=cls.__name__,
                module=cls.__module__,
            )

        registry_key = cls.class_identity.registry_key

        # Idempotency: if already registered, return the existing key.
        if self.has(registry_key) and self.get(registry_key) is cls:
            return registry_key

        return super()._register(registry_key, cls, library_identity)

    def _unregister_class(self, registry_key: str) -> type | None:
        return super()._unregister(registry_key)
```

Update `packages/haywire-core/src/haywire/core/state/__init__.py`:

```python
"""Library-owned runtime state — see internals/speculative/spec_library_state.md."""

from haywire.core.state.base import LibraryState
from haywire.core.state.identity import LibraryStateClassIdentity
from haywire.core.state.registry import LibraryStateRegistry

__all__ = ["LibraryState", "LibraryStateClassIdentity", "LibraryStateRegistry"]
```

- [ ] **Step 4: Run all state tests**

Run: `uv run pytest tests/core/test_state/ -v`

Expected: All tests in the directory PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/state/registry.py \
        packages/haywire-core/src/haywire/core/state/__init__.py \
        tests/core/test_state/test_registry.py
git commit -m "feat(state): add LibraryStateRegistry

Class registry for LibraryState subclasses. Inherits hot-reload, folder-scan,
and dependency-graph machinery from BaseRegistry. Registry key format:
'{library_id}:state:{class_name}'. Holds classes only — instance management
lives in LibraryStateContainer (next task)."
```

---

## Task 4: `LibraryStateContainer` (instance pool)

**Files:**
- Create: `packages/haywire-core/src/haywire/core/state/container.py`
- Modify: `packages/haywire-core/src/haywire/core/state/__init__.py`
- Test: `tests/core/test_state/test_container.py`

- [ ] **Step 1: Write the failing tests**

Write to `tests/core/test_state/test_container.py`:

```python
"""Unit tests for LibraryStateContainer."""

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state import LibraryState
from haywire.core.state.container import LibraryStateContainer
from haywire.core.state.registry import LibraryStateRegistry


def make_lib_identity(lib_id: str = "midi") -> LibraryIdentity:
    return LibraryIdentity(
        id=lib_id,
        label=lib_id.capitalize(),
        version="0.0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        dependencies=[],
        tags=[],
        module_name=f"haybale_{lib_id}",
        folder_path="",
    )


def make_added_event(cls: type, lib_id: LibraryIdentity) -> LifeCycleEvent:
    return LifeCycleEvent(
        registry_key=cls.class_identity.registry_key,
        event_type=LifeCycleEventType.CLASS_ADDED,
        affected_class=cls,
        library_identity=lib_id,
    )


def make_removed_event(cls: type, lib_id: LibraryIdentity) -> LifeCycleEvent:
    return LifeCycleEvent(
        registry_key=cls.class_identity.registry_key,
        event_type=LifeCycleEventType.CLASS_REMOVED,
        affected_class=cls,
        library_identity=lib_id,
    )


class TestLibraryStateContainer:
    def test_class_added_event_creates_instance_and_calls_on_enable(self):
        calls: list[str] = []

        class MyState(LibraryState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()

        # Subscribe container to registry events.
        reg.add_batch_event_subscriber(container.on_lifecycle_events)

        # Register the class — this would normally trigger event emission, but
        # _register_class doesn't emit by itself. Drive the container directly.
        reg._register_class(MyState, lib_id)
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])

        assert MyState in container
        assert isinstance(container[MyState], MyState)
        assert calls == ["enable"]

    def test_class_removed_event_calls_on_disable_and_drops_instance(self):
        calls: list[str] = []

        class MyState(LibraryState):
            def on_enable(self) -> None:
                calls.append("enable")

            def on_disable(self) -> None:
                calls.append("disable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()

        reg._register_class(MyState, lib_id)
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])

        assert MyState not in container
        assert calls == ["enable", "disable"]

    def test_missing_on_enable_is_fine(self):
        """LibraryStates without on_enable are still instantiated."""

        class NoHooks(LibraryState):
            pass

        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg = LibraryStateRegistry()
        reg._register_class(NoHooks, lib_id)

        # Should not raise.
        container.on_lifecycle_events([make_added_event(NoHooks, lib_id)])
        assert NoHooks in container

    def test_getitem_raises_keyerror_when_not_registered(self):
        class Missing(LibraryState):
            pass

        container = LibraryStateContainer()
        with pytest.raises(KeyError):
            _ = container[Missing]

    def test_get_returns_none_when_not_registered(self):
        class Missing(LibraryState):
            pass

        container = LibraryStateContainer()
        assert container.get(Missing) is None

    def test_class_reloaded_event_swaps_instance_with_disable_then_enable(self):
        """Hot-reload = disable old + enable new. Old class's on_disable fires
        before the new class is instantiated."""
        calls: list[str] = []

        class V1(LibraryState):
            def on_enable(self) -> None:
                calls.append("v1-enable")

            def on_disable(self) -> None:
                calls.append("v1-disable")

        # Simulate the registry's behaviour: emit a CLASS_RELOADED event whose
        # affected_class is the NEW version.
        class V2(LibraryState):
            def on_enable(self) -> None:
                calls.append("v2-enable")

            def on_disable(self) -> None:
                calls.append("v2-disable")

        # Hand-build matching identities so the same registry_key lands on both
        # — that's the hot-reload contract (same key, new class object).
        from haywire.core.state.identity import LibraryStateClassIdentity

        ident = LibraryStateClassIdentity(
            class_name="V",
            module=__name__,
            registry_id="V",
            registry_key="midi:state:V",
            label="V",
        )
        V1.class_identity = ident
        V2.class_identity = ident

        container = LibraryStateContainer()
        lib_id = make_lib_identity()

        # Initial enable.
        container.on_lifecycle_events([make_added_event(V1, lib_id)])
        assert calls == ["v1-enable"]

        # Hot-reload event: registry_key matches, affected_class is now V2.
        reload_event = LifeCycleEvent(
            registry_key="midi:state:V",
            event_type=LifeCycleEventType.CLASS_RELOADED,
            affected_class=V2,
            library_identity=lib_id,
        )
        container.on_lifecycle_events([reload_event])

        assert calls == ["v1-enable", "v1-disable", "v2-enable"]
        # The instance is now of the new class.
        assert isinstance(container[V2], V2)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/core/test_state/test_container.py -v`

Expected: FAIL — `LibraryStateContainer` doesn't exist yet.

- [ ] **Step 3: Implement the container**

Write to `packages/haywire-core/src/haywire/core/state/container.py`:

```python
"""LibraryStateContainer — owns the LibraryState instance pool.

Subscribes to LibraryStateRegistry batch lifecycle events. Mirrors the
NodeRegistry → NodeFactory pattern: registry holds classes, container holds
instances.

See internals/speculative/spec_library_state.md §3.
"""

from __future__ import annotations

import logging
from typing import TypeVar

from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state.base import LibraryState

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=LibraryState)


class LibraryStateContainer:
    """Holds live LibraryState instances, keyed by class.

    Wired to a LibraryStateRegistry via add_batch_event_subscriber:

        registry.add_batch_event_subscriber(container.on_lifecycle_events)

    The container reacts to:
      - CLASS_ADDED       → instantiate, store, call on_enable
      - CLASS_REMOVED     → call on_disable, drop instance
      - CLASS_RELOADED    → call on_disable on old, replace, call on_enable on new
    Failure events are logged and ignored.
    """

    def __init__(self) -> None:
        # Keyed by registry_key for events; instance map keyed by class for
        # ergonomic ctx.data[Cls] lookup. Both are kept in sync.
        self._instances_by_class: dict[type[LibraryState], LibraryState] = {}
        self._class_by_registry_key: dict[str, type[LibraryState]] = {}

    # ------------------------------------------------------------------
    # Public lookup API — used by _DataNamespace
    # ------------------------------------------------------------------

    def __getitem__(self, cls: type[T]) -> T:
        try:
            return self._instances_by_class[cls]  # type: ignore[return-value]
        except KeyError:
            raise KeyError(
                f"No LibraryState instance registered for class {cls.__name__}. "
                f"Either the owning library is not enabled, or the class is not "
                f"a registered LibraryState subclass."
            ) from None

    def get(self, cls: type[T]) -> T | None:
        return self._instances_by_class.get(cls)  # type: ignore[return-value]

    def __contains__(self, cls: type) -> bool:
        return cls in self._instances_by_class

    # ------------------------------------------------------------------
    # Lifecycle event handler — registered with LibraryStateRegistry
    # ------------------------------------------------------------------

    def on_lifecycle_events(self, events: list[LifeCycleEvent]) -> None:
        """Process a batch of lifecycle events from LibraryStateRegistry."""
        for event in events:
            try:
                self._dispatch(event)
            except Exception as exc:
                logger.error(
                    "LibraryStateContainer error handling %s: %s",
                    event,
                    exc,
                    exc_info=True,
                )

    def _dispatch(self, event: LifeCycleEvent) -> None:
        et = event.event_type
        if et is LifeCycleEventType.CLASS_ADDED:
            self._add(event)
        elif et is LifeCycleEventType.CLASS_REMOVED:
            self._remove(event)
        elif et is LifeCycleEventType.CLASS_RELOADED:
            self._reload(event)
        # Other event types (NOT_FOUND, FAILED, INSTANTIATED, etc.) are
        # ignored — they don't change the instance pool.

    def _add(self, event: LifeCycleEvent) -> None:
        cls = event.affected_class
        if cls is None:
            return
        if cls in self._instances_by_class:
            return  # Idempotent.
        instance = cls()
        self._instances_by_class[cls] = instance
        self._class_by_registry_key[event.registry_key] = cls
        self._call_on_enable(instance)

    def _remove(self, event: LifeCycleEvent) -> None:
        cls = self._class_by_registry_key.pop(event.registry_key, None)
        if cls is None:
            return
        instance = self._instances_by_class.pop(cls, None)
        if instance is not None:
            self._call_on_disable(instance)

    def _reload(self, event: LifeCycleEvent) -> None:
        # Drop the OLD instance (whatever class is currently mapped to this
        # registry_key), then add the new one.
        old_cls = self._class_by_registry_key.pop(event.registry_key, None)
        if old_cls is not None:
            old_instance = self._instances_by_class.pop(old_cls, None)
            if old_instance is not None:
                self._call_on_disable(old_instance)

        new_cls = event.affected_class
        if new_cls is None:
            return
        new_instance = new_cls()
        self._instances_by_class[new_cls] = new_instance
        self._class_by_registry_key[event.registry_key] = new_cls
        self._call_on_enable(new_instance)

    @staticmethod
    def _call_on_enable(instance: LibraryState) -> None:
        hook = getattr(instance, "on_enable", None)
        if callable(hook):
            try:
                hook()
            except Exception as exc:
                logger.error(
                    "%s.on_enable raised: %s", type(instance).__name__, exc, exc_info=True
                )

    @staticmethod
    def _call_on_disable(instance: LibraryState) -> None:
        hook = getattr(instance, "on_disable", None)
        if callable(hook):
            try:
                hook()
            except Exception as exc:
                logger.error(
                    "%s.on_disable raised: %s", type(instance).__name__, exc, exc_info=True
                )
```

Update `packages/haywire-core/src/haywire/core/state/__init__.py`:

```python
"""Library-owned runtime state — see internals/speculative/spec_library_state.md."""

from haywire.core.state.base import LibraryState
from haywire.core.state.container import LibraryStateContainer
from haywire.core.state.identity import LibraryStateClassIdentity
from haywire.core.state.registry import LibraryStateRegistry

__all__ = [
    "LibraryState",
    "LibraryStateClassIdentity",
    "LibraryStateContainer",
    "LibraryStateRegistry",
]
```

- [ ] **Step 4: Run all state tests**

Run: `uv run pytest tests/core/test_state/ -v`

Expected: All container + previously-passing tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/state/container.py \
        packages/haywire-core/src/haywire/core/state/__init__.py \
        tests/core/test_state/test_container.py
git commit -m "feat(state): add LibraryStateContainer

Holds the live LibraryState instance pool, keyed by class. Subscribes to
LibraryStateRegistry batch lifecycle events to instantiate (CLASS_ADDED),
swap (CLASS_RELOADED), and destroy (CLASS_REMOVED) instances. Calls
on_enable/on_disable hooks; both are duck-typed.

Mirrors the NodeRegistry → NodeFactory pattern."
```

---

## Task 5: `_DataNamespace` typed proxy

**Files:**
- Create: `packages/haywire-core/src/haywire/core/state/data_namespace.py`
- Modify: `packages/haywire-core/src/haywire/core/state/__init__.py`
- Test: `tests/core/test_state/test_data_namespace.py`

- [ ] **Step 1: Write the failing tests**

Write to `tests/core/test_state/test_data_namespace.py`:

```python
"""Unit tests for the _DataNamespace proxy."""

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state import (
    LibraryState,
    LibraryStateContainer,
    LibraryStateRegistry,
)
from haywire.core.state.data_namespace import DataNamespace


def make_lib_identity() -> LibraryIdentity:
    return LibraryIdentity(
        id="midi",
        label="Midi",
        version="0.0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        dependencies=[],
        tags=[],
        module_name="haybale_midi",
        folder_path="",
    )


class TestDataNamespace:
    def test_getitem_returns_instance(self):
        class MidiPool(LibraryState):
            def __init__(self) -> None:
                self.devices: list[str] = ["dev0"]

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg._register_class(MidiPool, lib_id)
        container.on_lifecycle_events(
            [
                LifeCycleEvent(
                    registry_key=MidiPool.class_identity.registry_key,
                    event_type=LifeCycleEventType.CLASS_ADDED,
                    affected_class=MidiPool,
                    library_identity=lib_id,
                )
            ]
        )

        ns = DataNamespace(container)
        result = ns[MidiPool]
        assert isinstance(result, MidiPool)
        assert result.devices == ["dev0"]

    def test_getitem_raises_for_unregistered_class(self):
        class NotRegistered(LibraryState):
            pass

        ns = DataNamespace(LibraryStateContainer())
        with pytest.raises(KeyError):
            _ = ns[NotRegistered]

    def test_get_returns_none_for_unregistered_class(self):
        class NotRegistered(LibraryState):
            pass

        ns = DataNamespace(LibraryStateContainer())
        assert ns.get(NotRegistered) is None

    def test_live_lookup_after_swap(self):
        """Each access reads the current container state — no caching."""
        from haywire.core.state.identity import LibraryStateClassIdentity

        class V1(LibraryState):
            tag = "v1"

        class V2(LibraryState):
            tag = "v2"

        ident = LibraryStateClassIdentity(
            class_name="V",
            module=__name__,
            registry_id="V",
            registry_key="midi:state:V",
            label="V",
        )
        V1.class_identity = ident
        V2.class_identity = ident

        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        ns = DataNamespace(container)

        container.on_lifecycle_events(
            [
                LifeCycleEvent(
                    registry_key="midi:state:V",
                    event_type=LifeCycleEventType.CLASS_ADDED,
                    affected_class=V1,
                    library_identity=lib_id,
                )
            ]
        )
        assert ns[V1].tag == "v1"

        # Hot-reload: V2 replaces V1 under the same registry_key.
        container.on_lifecycle_events(
            [
                LifeCycleEvent(
                    registry_key="midi:state:V",
                    event_type=LifeCycleEventType.CLASS_RELOADED,
                    affected_class=V2,
                    library_identity=lib_id,
                )
            ]
        )
        # V1 is no longer in the container.
        assert ns.get(V1) is None
        # New access via V2 returns the new instance.
        assert ns[V2].tag == "v2"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/core/test_state/test_data_namespace.py -v`

Expected: FAIL — `DataNamespace` doesn't exist.

- [ ] **Step 3: Implement the proxy**

Write to `packages/haywire-core/src/haywire/core/state/data_namespace.py`:

```python
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
```

Update `packages/haywire-core/src/haywire/core/state/__init__.py`:

```python
"""Library-owned runtime state — see internals/speculative/spec_library_state.md."""

from haywire.core.state.base import LibraryState
from haywire.core.state.container import LibraryStateContainer
from haywire.core.state.data_namespace import DataNamespace
from haywire.core.state.identity import LibraryStateClassIdentity
from haywire.core.state.registry import LibraryStateRegistry

__all__ = [
    "DataNamespace",
    "LibraryState",
    "LibraryStateClassIdentity",
    "LibraryStateContainer",
    "LibraryStateRegistry",
]
```

- [ ] **Step 4: Run all state tests**

Run: `uv run pytest tests/core/test_state/ -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/state/data_namespace.py \
        packages/haywire-core/src/haywire/core/state/__init__.py \
        tests/core/test_state/test_data_namespace.py
git commit -m "feat(state): add DataNamespace typed proxy

Class-keyed proxy over LibraryStateContainer, used as the .data attribute
on SessionContext and ExecutionContext. __getitem__ is generic over the
LibraryState class so type-checkers infer return types automatically.

Each access does a live container lookup — no caching."
```

---

## Task 6: DI wiring — register the registry and container

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/di/config.py:39-340` (add providers + initialize wiring)

- [ ] **Step 1: Write the failing test**

Write to `tests/core/test_state/test_di_wiring.py` (new):

```python
"""Tests verifying DI wiring of LibraryStateRegistry + LibraryStateContainer."""

from haywire.core.di.config import create_haywire_injector
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry


class TestDIWiring:
    def test_state_registry_is_provided_as_singleton(self):
        injector = create_haywire_injector()
        reg1 = injector.get(LibraryStateRegistry)
        reg2 = injector.get(LibraryStateRegistry)
        assert isinstance(reg1, LibraryStateRegistry)
        assert reg1 is reg2

    def test_state_container_is_provided_as_singleton(self):
        injector = create_haywire_injector()
        c1 = injector.get(LibraryStateContainer)
        c2 = injector.get(LibraryStateContainer)
        assert isinstance(c1, LibraryStateContainer)
        assert c1 is c2

    def test_container_is_subscribed_to_registry_after_initialize(self):
        """After LibrarySystemService.initialize(), the container must be in
        the registry's batch event subscriber list so lifecycle events flow."""
        from haywire.core.di.config import LibrarySystemService

        injector = create_haywire_injector()
        service = LibrarySystemService(injector)
        service.initialize()

        registry = injector.get(LibraryStateRegistry)
        container = injector.get(LibraryStateContainer)
        assert container.on_lifecycle_events in registry._batch_event_subscribers

    def test_settings_propagates_reload_to_state_registry(self):
        """settings_registry → state_registry: settings reloads cascade to state."""
        from haywire.core.di.config import LibrarySystemService
        from haywire.core.settings.registry import SettingsRegistry

        injector = create_haywire_injector()
        service = LibrarySystemService(injector)
        service.initialize()

        settings_registry = injector.get(SettingsRegistry)
        state_registry = injector.get(LibraryStateRegistry)
        assert state_registry in settings_registry._registry_subscribers

    def test_state_propagates_reload_to_node_panel_editor(self):
        """state_registry → node/panel/editor: state file changes cascade to
        consumer classes that may hold a stale class reference."""
        from haywire.core.di.config import LibrarySystemService
        from haywire.core.node.registry import NodeRegistry
        from haywire.ui.editor.registry import EditorTypeRegistry
        from haywire.ui.panel.registry import PanelRegistry

        injector = create_haywire_injector()
        service = LibrarySystemService(injector)
        service.initialize()

        state_registry = injector.get(LibraryStateRegistry)
        node_registry = injector.get(NodeRegistry)
        panel_registry = injector.get(PanelRegistry)
        editor_registry = injector.get(EditorTypeRegistry)

        assert node_registry in state_registry._registry_subscribers
        assert panel_registry in state_registry._registry_subscribers
        assert editor_registry in state_registry._registry_subscribers
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/core/test_state/test_di_wiring.py -v`

Expected: FAIL — providers don't exist yet, and the subscription wiring isn't done.

- [ ] **Step 3: Add providers to `HaywireModule`**

Open `packages/haywire-core/src/haywire/core/di/config.py`. Find the existing imports block near the top of the file (around lines 1-38). Add to the existing `from haywire.core...` imports:

```python
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
```

Find the existing `provide_panel_registry` provider (around line 168-172). Immediately after it, add two new providers:

```python
    @provider
    @singleton
    def provide_library_state_registry(self) -> LibraryStateRegistry:
        """Provide singleton LibraryStateRegistry — class registry for LibraryState subclasses."""
        return LibraryStateRegistry()

    @provider
    @singleton
    def provide_library_state_container(self) -> LibraryStateContainer:
        """Provide singleton LibraryStateContainer — instance pool for LibraryStates.

        Subscription to LibraryStateRegistry events is wired in
        LibrarySystemService.initialize().
        """
        return LibraryStateContainer()
```

- [ ] **Step 4: Wire the container subscription in `LibrarySystemService.initialize()`**

Locate `LibrarySystemService.initialize()` (around line 246). Find the block that resolves registries (around lines 266-280), the block that calls `library_registry.add_class_registry(...)` (around lines 283-291), and the existing **registry subscriber chain** that wires settings → node/skin/panel/editor (around lines 304-307). You'll insert into all three.

**a) Resolve the new registry + container** — insert after the existing `editor_registry = self.injector.get(EditorTypeRegistry)` line:

```python
        library_state_registry = self.injector.get(LibraryStateRegistry)
        library_state_container = self.injector.get(LibraryStateContainer)
        library_state_registry.add_batch_event_subscriber(
            library_state_container.on_lifecycle_events
        )
```

**b) Register the new class-registry with `LibraryRegistry`** — after the existing `library_registry.add_class_registry(EditorTypeRegistry, editor_registry)` line:

```python
        library_registry.add_class_registry(LibraryStateRegistry, library_state_registry)
```

**c) Add the hot-reload propagation chain** — find the existing block that wires settings to its consumers, currently around lines 304-307:

```python
        settings_registry.add_registry_subscriber(node_registry)
        settings_registry.add_registry_subscriber(skin_registry)
        settings_registry.add_registry_subscriber(panel_registry)
        settings_registry.add_registry_subscriber(editor_registry)
```

Insert **state_registry into the chain** so that:

- settings reload also reloads state files (a `LibraryState` may compose a `LibrarySettings`, per spec §5.1, so a settings schema change must propagate).
- state reload also reloads node/panel/editor files (consumer code that imports a `LibraryState` class for use as a `ctx.data[Cls]` key holds a stale class object after hot-reload unless its module re-imports).

Modify the block to:

```python
        settings_registry.add_registry_subscriber(node_registry)
        settings_registry.add_registry_subscriber(skin_registry)
        settings_registry.add_registry_subscriber(panel_registry)
        settings_registry.add_registry_subscriber(editor_registry)
        settings_registry.add_registry_subscriber(library_state_registry)
        library_state_registry.add_registry_subscriber(node_registry)
        library_state_registry.add_registry_subscriber(panel_registry)
        library_state_registry.add_registry_subscriber(editor_registry)
```

Note: `library_state_registry` is **not** subscribed to skin/adapter/widget/type — those don't typically reference LibraryState classes. If a real need appears later, the subscription can be added in a follow-up.

- [ ] **Step 5: Run the DI tests**

Run: `uv run pytest tests/core/test_state/test_di_wiring.py -v`

Expected: All three tests PASS.

- [ ] **Step 6: Run the full state test directory + DI smoke tests**

Run: `uv run pytest tests/core/test_state/ tests/core/test_di/ -v`

Expected: All tests PASS, including pre-existing DI tests (no regressions).

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/di/config.py \
        tests/core/test_state/test_di_wiring.py
git commit -m "feat(state): wire LibraryStateRegistry + Container into DI

Adds two singleton providers to HaywireModule and wires the container as
a batch event subscriber of the registry inside LibrarySystemService.
Registers the new registry with LibraryRegistry.add_class_registry so
the existing enable_all_libraries / hot-reload pipeline drives state
lifecycle automatically.

Also extends the registry-subscriber chain so hot-reload propagates
correctly:
  settings → state    (state may compose LibrarySettings)
  state → node/panel/editor   (consumers may import LibraryState classes
                               for use as ctx.data[Cls] keys)"
```

---

## Task 7: `SessionContext` — delete `metadata`, add `data`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/context.py:36-79`
- Modify: `packages/haywire-core/src/haywire/ui/session.py:50-65` (pass container in)
- Test: `tests/ui/test_session_context_data.py` (new)

- [ ] **Step 1: Write the failing test**

Write to `tests/ui/test_session_context_data.py` (create directory if missing):

```python
"""Tests for SessionContext.data — the LibraryState access path."""

import pytest

from haywire.core.state import (
    LibraryState,
    LibraryStateContainer,
)
from haywire.core.state.data_namespace import DataNamespace
from haywire.ui.context import SessionContext


class FakeApp:
    """Minimal IProjectState stub for SessionContext construction."""

    def __init__(self, container: LibraryStateContainer) -> None:
        self.library_state_container = container


class TestSessionContextData:
    def test_session_context_exposes_data_namespace(self):
        container = LibraryStateContainer()
        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert isinstance(ctx.data, DataNamespace)

    def test_session_context_data_resolves_to_container(self):
        class Pool(LibraryState):
            value: int = 42

        container = LibraryStateContainer()
        # Manually plant an instance so we don't need full registry wiring here.
        instance = Pool()
        container._instances_by_class[Pool] = instance

        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert ctx.data[Pool] is instance

    def test_session_context_no_longer_has_metadata(self):
        """metadata field was removed in favour of LibraryState."""
        container = LibraryStateContainer()
        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert not hasattr(ctx, "metadata")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/ui/test_session_context_data.py -v`

Expected: FAIL — `ctx.data` doesn't exist; `ctx.metadata` still does.

- [ ] **Step 3: Modify `SessionContext` — drop `metadata`, add `data`**

Open `packages/haywire-core/src/haywire/ui/context.py`. Make these edits:

a) **Update imports** at the top of the file. Find:

```python
from typing import TYPE_CHECKING, Any, Dict, Optional, Set
```

Replace with:

```python
from typing import TYPE_CHECKING, Any, Optional, Set
```

(`Dict` is no longer needed once `metadata` is removed.)

Add to the existing imports below the typing line:

```python
from haywire.core.state.data_namespace import DataNamespace
```

b) **Update the docstring** (around line 38-46). Replace:

```python
    """
    Per-session context carrying current UI state.

    Reactive fields are accessed as `ctx.<field>.value` (read) or
    `ctx.<field>.value = ...` (write). Plain fields (`session_id`,
    `app`, `session`, `metadata`) are non-reactive.
    """
```

with:

```python
    """
    Per-session context carrying current UI state.

    Reactive fields are accessed as `ctx.<field>.value` (read) or
    `ctx.<field>.value = ...` (write). Plain fields (`session_id`,
    `app`, `session`, `data`) are non-reactive.

    `data` is a typed proxy over the app's LibraryStateContainer — see
    internals/speculative/spec_library_state.md.
    """
```

c) **Replace the `metadata` field declaration** (line 49). Replace:

```python
    metadata: Dict[str, Any]
```

with:

```python
    data: DataNamespace
```

d) **Replace the `metadata` assignment in `__init__`** (line 69). Replace:

```python
        self.metadata = {}
```

with:

```python
        self.data = DataNamespace(app.library_state_container)
```

e) **Update the docstring inside `__init__` if it mentions metadata** (the existing docstring around lines 14-16 says "The `metadata` dict remains a plain dict in Phase 1; Phase 1.5 lifts context-menu gesture state to typed fields on the host"). Find this comment block at the top of the file:

```python
The `metadata` dict remains a plain dict in Phase 1; Phase 1.5 lifts
context-menu gesture state to typed fields on the host (see
spec_panel_migration.md §4).
```

Replace with:

```python
The `data` attribute is a typed DataNamespace proxy over the app's
LibraryStateContainer — class-keyed access to library-owned runtime
state. See spec_library_state.md.
```

- [ ] **Step 4: Update the `IProjectState` protocol to include `library_state_container`**

The fake app in the tests reads `app.library_state_container`. Look in `packages/haywire-core/src/haywire/ui/protocols.py` for the `IProjectState` Protocol.

Run this command first to find the relevant lines:

```bash
grep -n "class IProjectState\|library_service\|library_state" packages/haywire-core/src/haywire/ui/protocols.py
```

Once you've found the `IProjectState` Protocol definition, add a `library_state_container` attribute. After the existing `library_service` attribute declaration, add:

```python
    library_state_container: "LibraryStateContainer"
    """Pool of live LibraryState instances. See spec_library_state.md."""
```

Add the import at the top of `protocols.py`, inside the existing `TYPE_CHECKING` block:

```python
    from haywire.core.state import LibraryStateContainer
```

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/ui/test_session_context_data.py -v`

Expected: All three tests PASS.

- [ ] **Step 6: Run the full UI test directory to check for regressions**

Run: `uv run pytest tests/ui/ -v`

Expected: All tests PASS. If any test references `ctx.metadata`, those tests need updating — but the prior code search showed zero such references; this should be clean.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/context.py \
        packages/haywire-core/src/haywire/ui/protocols.py \
        tests/ui/test_session_context_data.py
git commit -m "feat(state): add SessionContext.data, remove unused metadata

SessionContext gains a `data: DataNamespace` field exposing class-keyed
access to LibraryState instances (ctx.data[MyState]). The unused
`metadata: Dict[str, Any]` field is deleted (verified zero call sites).

IProjectState protocol gains library_state_container so SessionContext
can construct its DataNamespace at session creation."
```

---

## Task 8: `HaywireApp` — provide `library_state_container` to sessions

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/app.py:100-160` (resolve container, expose as attribute)

- [ ] **Step 1: Write the failing test**

Write to `tests/studio/test_app_library_state_container.py` (create directory if missing):

```python
"""Tests verifying HaywireApp exposes the LibraryStateContainer."""

from haywire.core.state import LibraryStateContainer


class TestAppLibraryStateContainer:
    def test_app_exposes_library_state_container(self):
        from haywire_studio.app import HaywireApp

        app = HaywireApp()
        assert hasattr(app, "library_state_container")
        assert isinstance(app.library_state_container, LibraryStateContainer)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/studio/test_app_library_state_container.py -v`

Expected: FAIL — `library_state_container` attribute does not exist on HaywireApp.

- [ ] **Step 3: Inspect HaywireApp's existing attribute pattern**

Run:

```bash
grep -n "self\.\(node\|panel\|skin\|adapter\)_\(registry\|factory\)\s*=" packages/haywire-studio/src/haywire_studio/app.py
```

Note the lines 127-131 where existing attributes are wired (`self.node_registry = self.library_service.get_node_registry()` etc.).

- [ ] **Step 4: Wire the container as a HaywireApp attribute**

Open `packages/haywire-studio/src/haywire_studio/app.py`. Find the block around lines 127-131:

```python
        self.node_registry = self.library_service.get_node_registry()
        self.node_factory = self.library_service.get_node_factory()
        self.skin_factory = self.library_service.get_skin_factory()
        self.adapter_factory = self.library_service.get_adapter_factory()
        self.panel_registry = self.library_service.get_panel_registry()
```

Immediately after the `self.panel_registry = ...` line, add:

```python
        from haywire.core.state import LibraryStateContainer
        self.library_state_container = self.library_service.injector.get(LibraryStateContainer)
```

(Direct injector lookup — no `library_service.get_library_state_container()` helper is needed unless the existing `get_*` pattern is preferred for consistency. If the reviewer wants such a helper, add it to `LibrarySystemService`; for v1 the inline lookup matches several other call sites in this file.)

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/studio/test_app_library_state_container.py -v`

Expected: PASS.

- [ ] **Step 6: Run the haywire-studio test suite for regressions**

Run: `uv run pytest tests/studio/ -v`

Expected: No regressions. Some tests may fail due to test-fixture changes from Task 7 (Sessions need a `library_state_container` on app); fix those by ensuring `HaywireApp` is fully constructed in fixtures.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/app.py \
        tests/studio/test_app_library_state_container.py
git commit -m "feat(state): expose LibraryStateContainer on HaywireApp

HaywireApp now reads the container from its DI injector and exposes it
as self.library_state_container. SessionContext reads this attribute
when constructing its DataNamespace."
```

---

## Task 9: `ExecutionContext` — add `data` field

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/execution/execution_context.py:10-62`
- Test: `tests/core/test_execution/test_execution_context_data.py` (new)

- [ ] **Step 1: Write the failing test**

Write to `tests/core/test_execution/test_execution_context_data.py`:

```python
"""Tests for ExecutionContext.data — class-keyed LibraryState access."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.state import LibraryState, LibraryStateContainer
from haywire.core.state.data_namespace import DataNamespace


class TestExecutionContextData:
    def test_data_field_default_none(self):
        """If no data namespace is provided, the field is None."""
        ctx = ExecutionContext(global_ctx={}, local_ctx={})
        assert ctx.data is None

    def test_data_field_can_be_set(self):
        class Pool(LibraryState):
            pass

        container = LibraryStateContainer()
        instance = Pool()
        container._instances_by_class[Pool] = instance

        ns = DataNamespace(container)
        ctx = ExecutionContext(global_ctx={}, local_ctx={}, data=ns)
        assert ctx.data is ns
        assert ctx.data[Pool] is instance
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/core/test_execution/test_execution_context_data.py -v`

Expected: FAIL — `ExecutionContext` does not accept a `data` keyword argument.

- [ ] **Step 3: Add the field**

Open `packages/haywire-core/src/haywire/core/execution/execution_context.py`. Find the `ExecutionContext` dataclass (lines 10-62).

Add to the imports at the top of the file:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.state.data_namespace import DataNamespace
```

(If a `TYPE_CHECKING` block already exists, add only the `DataNamespace` import inside it.)

Find the field declarations inside the dataclass. After the existing `exec_count: Optional[int] = 0` field (around line 39), add:

```python
    data: Optional["DataNamespace"] = None
    """Class-keyed proxy to the app's LibraryStateContainer. None if the VM
    was constructed without a container reference (test contexts only)."""
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/core/test_execution/test_execution_context_data.py -v`

Expected: Both tests PASS.

- [ ] **Step 5: Run the wider execution tests**

Run: `uv run pytest tests/core/test_execution/ -v`

Expected: No regressions — the new field is additive with a default of None.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/execution/execution_context.py \
        tests/core/test_execution/test_execution_context_data.py
git commit -m "feat(state): add ExecutionContext.data field

Optional DataNamespace field (default None) on ExecutionContext, populated
by HaywireVM._create_execution_context when the VM has a container
reference. Worker functions access library state via exec_ctx.data[Cls]."
```

---

## Task 10: `HaywireVM` — accept and use the container

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/execution/vm.py:42-88`
- Test: `tests/core/test_execution/test_vm_library_state.py` (new)

- [ ] **Step 1: Write the failing test**

Write to `tests/core/test_execution/test_vm_library_state.py`:

```python
"""Tests verifying HaywireVM populates ExecutionContext.data from its container."""

from unittest.mock import MagicMock

from haywire.core.execution.vm import HaywireVM
from haywire.core.state import LibraryState, LibraryStateContainer
from haywire.core.state.data_namespace import DataNamespace


class TestVMLibraryStateWiring:
    def test_vm_without_container_creates_context_with_data_none(self):
        vm = HaywireVM()
        flow = MagicMock()
        flow.graph_ref.variables = {}

        ctx = vm._create_execution_context(flow=flow)
        assert ctx.data is None

    def test_vm_with_container_populates_data_namespace(self):
        class Pool(LibraryState):
            pass

        container = LibraryStateContainer()
        instance = Pool()
        container._instances_by_class[Pool] = instance

        vm = HaywireVM(library_state_container=container)
        flow = MagicMock()
        flow.graph_ref.variables = {}

        ctx = vm._create_execution_context(flow=flow)
        assert isinstance(ctx.data, DataNamespace)
        assert ctx.data[Pool] is instance
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/core/test_execution/test_vm_library_state.py -v`

Expected: FAIL — `HaywireVM` does not accept `library_state_container`.

- [ ] **Step 3: Update `HaywireVM.__init__`**

Open `packages/haywire-core/src/haywire/core/execution/vm.py`. Find the imports block (lines 12-25). Add to the `TYPE_CHECKING` block:

```python
    from haywire.core.state import LibraryStateContainer
```

If the `TYPE_CHECKING` block doesn't already exist or doesn't have `from haywire.core...`, ensure `from typing import TYPE_CHECKING` is at the top and the block is structured like the existing one shown in lines 22-25.

Find the constructor signature (line 42):

```python
    def __init__(self, global_context: Optional[Dict[str, Any]] = None, max_stack_depth: int = 1000):
```

Replace with:

```python
    def __init__(
        self,
        global_context: Optional[Dict[str, Any]] = None,
        max_stack_depth: int = 1000,
        library_state_container: Optional["LibraryStateContainer"] = None,
    ):
```

Update the constructor docstring (lines 43-49). Replace:

```python
        """
        Initialize VM.

        Args:
            global_context: Global execution context
            max_stack_depth: Maximum loopback stack depth before error
        """
```

with:

```python
        """
        Initialize VM.

        Args:
            global_context: Global execution context
            max_stack_depth: Maximum loopback stack depth before error
            library_state_container: Container exposing app-global LibraryState
                instances to worker functions via exec_ctx.data[Cls]. Optional —
                when None, exec_ctx.data is None.
        """
```

After the existing `self.callback_manager: Optional[CallbackManager] = None` line (line 55), add:

```python
        self._library_state_container = library_state_container
```

- [ ] **Step 4: Update `_create_execution_context` to populate `data`**

Find `_create_execution_context` (lines 59-88). Find the return statement (lines 82-88):

```python
        return ExecutionContext(
            global_ctx=self.global_context,
            local_ctx=local_ctx,
            trigger=trigger,
            vm=self,
            frame_number=frame_number,
        )
```

Just before the `return`, add:

```python
        from haywire.core.state.data_namespace import DataNamespace

        data_namespace: Optional[DataNamespace] = (
            DataNamespace(self._library_state_container)
            if self._library_state_container is not None
            else None
        )
```

Then update the return to pass the data namespace:

```python
        return ExecutionContext(
            global_ctx=self.global_context,
            local_ctx=local_ctx,
            trigger=trigger,
            vm=self,
            frame_number=frame_number,
            data=data_namespace,
        )
```

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/core/test_execution/test_vm_library_state.py -v`

Expected: Both tests PASS.

- [ ] **Step 6: Run the full execution suite**

Run: `uv run pytest tests/core/test_execution/ -v`

Expected: No regressions.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/execution/vm.py \
        tests/core/test_execution/test_vm_library_state.py
git commit -m "feat(state): HaywireVM accepts LibraryStateContainer

VM gains an optional library_state_container constructor argument.
_create_execution_context wraps it in a DataNamespace and assigns it
to ExecutionContext.data so worker functions can access library state
via exec_ctx.data[Cls]. When the VM is constructed without a container
(test contexts), exec_ctx.data is None — preserving backward compatibility."
```

---

## Task 11: `Interpreter` — forward container to VM

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/execution/interpreter.py:65-79`

- [ ] **Step 1: Write the failing test**

Write to `tests/core/test_execution/test_interpreter_library_state.py`:

```python
"""Tests verifying Interpreter forwards LibraryStateContainer to its VM."""

from haywire.core.execution.interpreter import Interpreter
from haywire.core.state import LibraryStateContainer


class TestInterpreterLibraryState:
    def test_interpreter_without_container_has_vm_with_no_container(self):
        interpreter = Interpreter()
        assert interpreter.vm._library_state_container is None

    def test_interpreter_forwards_container_to_vm(self):
        container = LibraryStateContainer()
        interpreter = Interpreter(library_state_container=container)
        assert interpreter.vm._library_state_container is container
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/core/test_execution/test_interpreter_library_state.py -v`

Expected: FAIL — `Interpreter` doesn't accept `library_state_container`.

- [ ] **Step 3: Update `Interpreter.__init__`**

Open `packages/haywire-core/src/haywire/core/execution/interpreter.py`. Find the imports block. Add to the `TYPE_CHECKING` block (or create one if missing — model it on `vm.py`):

```python
    from haywire.core.state import LibraryStateContainer
```

Find the constructor signature (line 65):

```python
    def __init__(self, global_context: Optional[Dict[str, Any]] = None, max_stack_depth: int = 1000):
```

Replace with:

```python
    def __init__(
        self,
        global_context: Optional[Dict[str, Any]] = None,
        max_stack_depth: int = 1000,
        library_state_container: Optional["LibraryStateContainer"] = None,
    ):
```

Update the docstring to mention the new arg:

```python
        """
        Initialize interpreter.

        Args:
            global_context: Global execution context passed to all flows
            max_stack_depth: Maximum VM stack depth
            library_state_container: Optional pool of LibraryState instances.
                Forwarded to the VM so worker functions get exec_ctx.data.
        """
```

Find the line that constructs the VM (line 75):

```python
        self.vm = HaywireVM(global_context=global_context, max_stack_depth=max_stack_depth)
```

Replace with:

```python
        self.vm = HaywireVM(
            global_context=global_context,
            max_stack_depth=max_stack_depth,
            library_state_container=library_state_container,
        )
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/core/test_execution/test_interpreter_library_state.py -v`

Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/execution/interpreter.py \
        tests/core/test_execution/test_interpreter_library_state.py
git commit -m "feat(state): Interpreter forwards LibraryStateContainer to VM

Adds optional library_state_container kwarg to Interpreter.__init__,
forwarded to HaywireVM. The studio's haystack will pass the app-owned
container so worker functions in production graphs see live library state."
```

---

## Task 12: `Haystack` — pass container into Interpreter

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/haystack.py:108`

- [ ] **Step 1: Inspect the construction site**

Run:

```bash
grep -n "Interpreter()\|self\.interpreter\s*=" packages/haywire-studio/src/haywire_studio/haystack.py
```

Note line 108: `self.interpreter = Interpreter()`.

Run also:

```bash
grep -n "self\.app\|library_state_container\|app:\s*.*App" packages/haywire-studio/src/haywire_studio/haystack.py | head -10
```

You need to confirm Haystack has access to the app instance. Read the `Haystack.__init__` to see what it already takes.

- [ ] **Step 2: Locate where Haystack receives the app reference**

Run:

```bash
grep -n "class Haystack\|def __init__" packages/haywire-studio/src/haywire_studio/haystack.py | head -10
```

Read the relevant lines of `__init__` to see if `app` is already a constructor arg. If yes, proceed. If not, this becomes a wider plumbing change — but per the Repository state grep above, the haystack is constructed by the app itself, so it likely already has the app reference. Confirm by reading.

- [ ] **Step 3: Update the Interpreter construction**

Open `packages/haywire-studio/src/haywire_studio/haystack.py`. Find line 108:

```python
        self.interpreter = Interpreter()
```

Replace with:

```python
        self.interpreter = Interpreter(
            library_state_container=self.app.library_state_container,
        )
```

(If the `app` reference uses a different attribute name in this file, e.g. `self._app` or `self.project_state`, adapt accordingly. Read 5 lines of context around line 108 to find the right reference.)

- [ ] **Step 4: Run the studio test suite**

Run: `uv run pytest tests/studio/ -v`

Expected: No regressions.

- [ ] **Step 5: Run the integration smoke test by launching the app briefly**

Run:

```bash
timeout 10 uv run haywire || true
```

Expected: The app starts without errors related to library state. (10-second timeout because we're just smoke-testing startup.)

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/haystack.py
git commit -m "feat(state): wire LibraryStateContainer into Haystack's Interpreter

The studio's per-graph Interpreter now receives the app's container so
worker functions in production graphs can access library state via
exec_ctx.data[Cls]."
```

---

## Task 13: End-to-end integration test

**Files:**
- Test: `tests/core/test_state/test_integration.py`

- [ ] **Step 1: Write the integration test**

Write to `tests/core/test_state/test_integration.py`:

```python
"""End-to-end test: full library enable → state instantiation → ctx.data access.

This test runs through the actual DI + LibrarySystemService initialization
to verify that LibraryState lifecycle is correctly driven by the existing
library enable pipeline.
"""

import pytest

from haywire.core.di.config import LibrarySystemService, create_haywire_injector
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType,
)
from haywire.core.state import (
    LibraryState,
    LibraryStateContainer,
    LibraryStateRegistry,
)


@pytest.mark.integration
class TestLibraryStateIntegration:
    def test_class_added_event_triggers_full_lifecycle(self):
        """Simulate a library registering a LibraryState class via the registry's
        public API path; verify the container picks it up and on_enable runs."""
        injector = create_haywire_injector()
        service = LibrarySystemService(injector)
        service.initialize()

        registry = injector.get(LibraryStateRegistry)
        container = injector.get(LibraryStateContainer)

        calls: list[str] = []

        class TestPool(LibraryState):
            def on_enable(self) -> None:
                calls.append("enable")

            def on_disable(self) -> None:
                calls.append("disable")

        # Build a minimal LibraryIdentity for this test "library".
        lib_id = LibraryIdentity(
            id="testlib",
            label="Test Library",
            version="0.0.1",
            description="",
            url="",
            help_url="",
            author="",
            author_url="",
            dependencies=[],
            tags=[],
            module_name="testlib",
            folder_path="",
        )

        # Register the class — that puts it in the registry's _classes dict.
        key = registry._register_class(TestPool, lib_id)
        assert key is not None

        # In real life, the BaseRegistry's hot-reload path emits CLASS_ADDED
        # events through _queue_lifecycle_event + _notify_batch_event_subscribers.
        # Simulate that here:
        added_event = LifeCycleEvent(
            registry_key=key,
            event_type=LifeCycleEventType.CLASS_ADDED,
            affected_class=TestPool,
            library_identity=lib_id,
        )
        registry._lifecycle_event_queue.append(added_event)
        registry._notify_batch_event_subscribers()

        # Container should now hold an instance with on_enable called.
        assert TestPool in container
        assert calls == ["enable"]

        # Now simulate library disable: emit CLASS_REMOVED.
        removed_event = LifeCycleEvent(
            registry_key=key,
            event_type=LifeCycleEventType.CLASS_REMOVED,
            affected_class=TestPool,
            library_identity=lib_id,
        )
        registry._lifecycle_event_queue.append(removed_event)
        registry._notify_batch_event_subscribers()

        assert TestPool not in container
        assert calls == ["enable", "disable"]
```

- [ ] **Step 2: Run the integration test**

Run: `uv run pytest tests/core/test_state/test_integration.py -v -m integration`

Expected: PASS — full pipeline (DI → registry → container → lifecycle hooks) works.

- [ ] **Step 3: Run the entire test suite once more for regressions**

Run: `uv run pytest -v`

Expected: All previously-passing tests still pass; new tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/core/test_state/test_integration.py
git commit -m "test(state): add end-to-end LibraryState integration test

Drives the full DI + LibrarySystemService pipeline and verifies that
CLASS_ADDED / CLASS_REMOVED events from LibraryStateRegistry correctly
trigger instantiation, on_enable, on_disable, and instance teardown
in LibraryStateContainer."
```

---

## Task 14: Run the full quality suite

- [ ] **Step 1: Lint**

Run: `uv run ruff check .`

Expected: No errors. Fix any new lint warnings before continuing.

- [ ] **Step 2: Format check**

Run: `uv run ruff format --check .`

Expected: All files formatted. If not, run `uv run ruff format .` and commit the formatting changes:

```bash
git add -A
git commit -m "style: apply ruff format"
```

- [ ] **Step 3: Type check**

Run: `uv run mypy packages/haywire-core/src/`

Expected: No new type errors. The existing baseline may have known errors; the LibraryState code should add zero.

- [ ] **Step 4: Full test suite**

Run: `uv run pytest --cov`

Expected: All tests pass. Coverage on the new `haywire/core/state/` module should be ≥95% — every public method has a unit test plus the integration test.

- [ ] **Step 5: Smoke test the app**

Run:

```bash
timeout 15 uv run haywire || true
```

Expected: App starts, library system initializes, no errors related to LibraryState. Look for the registry status output and confirm `LibraryStateRegistry` appears in the list.

---

## Task 15: Documentation updates

**Files:**
- Modify: `internals/speculative/spec_library_state.md` (move from speculative to documentation now that v1 is implemented)

- [ ] **Step 1: Move the spec out of speculative**

Run:

```bash
mkdir -p internals/documentation/architecture
git mv internals/speculative/spec_library_state.md internals/documentation/architecture/library_state.md
```

- [ ] **Step 2: Update the status note**

Open `internals/documentation/architecture/library_state.md`. Find the status block at the top:

```markdown
> Status: **Speculative.** Not yet implemented. Designed via inquisition
> on 2026-05-06.
```

Replace with (using today's date):

```markdown
> Status: **v1 implemented (2026-05-06).** This document is the canonical
> reference for LibraryState. Phase 2 (observable container, reactive
> auto-tracking) remains pending — see spec_panel_reactivity.md.
```

- [ ] **Step 3: Verify any internal references still resolve**

Run:

```bash
grep -rn "spec_library_state.md" internals/ packages/ --include="*.md" --include="*.py" 2>/dev/null
```

Update any references that still point at `internals/speculative/spec_library_state.md` to the new path `internals/documentation/architecture/library_state.md`. The known references are inside the spec itself (relative links to companion docs) and in source-code comments inserted by Tasks 1, 4, 5, 7, 9 referring to the spec. Update them.

- [ ] **Step 4: Commit**

```bash
git add internals/documentation/architecture/library_state.md internals/speculative/
git add packages/  # if any source comments were updated
git commit -m "docs(state): promote LibraryState spec from speculative to documentation

v1 is implemented; the spec is now the canonical reference. Phase 2
items (observable container, reactive auto-tracking) remain pending."
```

---

## Self-review checklist (already applied)

- [x] **Spec coverage**:
  - §2.1 Declaration → Task 1 (LibraryState base).
  - §2.2 Registration → Task 3 (LibraryStateRegistry) + Task 6 (DI wiring + folder-scan via existing add_class_registry path).
  - §2.3 Access → Task 5 (DataNamespace) + Task 7 (SessionContext.data) + Task 9 (ExecutionContext.data).
  - §2.4 Type-checking → Task 5 (TypeVar-based __getitem__).
  - §3.1 Two-component split → Tasks 3 + 4.
  - §3.2 Enable/disable lifecycle → Task 4 (container hook handling).
  - §3.3 Hot-reload → Task 4 (CLASS_RELOADED handling) + integration test in Task 13.
  - §3.4 Order → relies on existing library `dependencies=` mechanism; no new code (mentioned in spec).
  - §3.5 Observability → live lookup in Task 5 (DataNamespace), no observers; Phase 2 deferred.
  - §4 Reactivity → uses existing `reactive_field()`; no new code.
  - §4.1 Threading → deferred to Phase 2; documented in spec.
  - §5 Boundary → docs only; spec body unchanged.
  - §5.1 Settings composition → docs only; example exists in spec §7.3.
  - §6.1 New types → Tasks 1–5.
  - §6.2 Changes to existing types → Tasks 6 (DI), 7 (SessionContext), 8 (HaywireApp), 9 (ExecutionContext), 10 (HaywireVM), 11 (Interpreter), 12 (Haystack).
  - §6.3 Breaking changes → Task 7 (delete `metadata`), Task 10 (HaywireVM kwarg).

- [x] **Placeholder scan**: every step has concrete code or commands. No "TBD", no "similar to Task N" without code.

- [x] **Type consistency**: `LibraryState`, `LibraryStateRegistry`, `LibraryStateContainer`, `DataNamespace`, `LibraryStateClassIdentity`, `library_state_container` — names match across all tasks. Method names: `_register_class`, `_unregister_class`, `_class_filter`, `on_lifecycle_events`, `__getitem__`, `get`, `__contains__`, `on_enable`, `on_disable` — consistent throughout.
