# SessionState v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the LibraryState system with a second scope — per-UI-session — alongside the existing app-global scope. Restructure the taxonomy so both scopes are first-class siblings (`AppState`, `SessionState`) under an abstract `LibraryState` marker base.

**Architecture:** Reuse the v1 machinery (registry, container subscription, hot-reload, identity, lifecycle hooks) with one shared container handling both scopes. The container's internal storage gains a per-(class, session_id) map for SessionState; everything else dispatches by `issubclass(cls, SessionState)`. `SessionContext` exposes two namespaces (`ctx.data` for session-scoped, `ctx.app_data` for app-scoped); `ExecutionContext` exposes only `ctx.app_data` (graphs run app-globally). `SessionManager` drives session attach/detach.

**Tech Stack:** Python 3.10+, existing haywire BaseRegistry framework, pytest, mypy, ruff.

**Source spec:** [`docs/documentation/architecture/session_state.md`](../../documentation/architecture/session_state.md). v1.1 only — the framework migration of `active_node`/`selected_nodes`/etc. into a built-in `EditState` SessionState is deferred to v1.2.

---

## File structure

### New files

| File | Responsibility |
|------|----------------|
| `tests/core/test_state/test_app_state.py` | Unit tests — `AppState` concrete base behavior (rename from `test_library_state.py`) |
| `tests/core/test_state/test_session_state.py` | Unit tests — `SessionState` base + `LibrarySettings` prohibition check |
| `tests/core/test_state/test_session_data_namespace.py` | Unit tests — `SessionDataNamespace` lookups, KeyError, get-optional |
| `tests/core/test_state/test_container_session_scope.py` | Unit tests — container two-scope dispatch, `attach_session`/`detach_session`, fanout, hot-reload |
| `tests/core/test_state/test_session_manager_attach.py` | Unit tests — `SessionManager` attach/detach wiring |
| `tests/core/test_state/test_session_state_integration.py` | Integration test — full library enable → SessionState class registered → session attach → on_enable → access via `ctx.data` → detach → on_disable |

### Modified files

| File | Change |
|------|--------|
| `packages/haywire-core/src/haywire/core/state/base.py` | Repurpose `LibraryState` as abstract marker; add `AppState` and `SessionState` concrete bases; `SessionState.__init_subclass__` rejects `LibrarySettings`-typed fields |
| `packages/haywire-core/src/haywire/core/state/__init__.py` | Add `AppState`, `SessionState`, `SessionDataNamespace` exports; rename `DataNamespace` → `AppDataNamespace` in exports |
| `packages/haywire-core/src/haywire/core/state/data_namespace.py` | Rename `DataNamespace` class → `AppDataNamespace` (tighten `bound=AppState`); add `SessionDataNamespace` class (`bound=SessionState`, carries `session_id`) |
| `packages/haywire-core/src/haywire/core/state/registry.py` | Widen `_class_filter` exclusion to `(LibraryState, AppState, SessionState)`; type hint update |
| `packages/haywire-core/src/haywire/core/state/container.py` | Two-scope internal storage (`_app`, `_sessions`, `_known_session_ids`); scope dispatch in `_add`/`_remove`/`_reload`; new `attach_session`/`detach_session`/`get_session`/`get_session_optional`/`has_session` |
| `packages/haywire-core/src/haywire/ui/context.py` | Rename `data: DataNamespace` field → `app_data: AppDataNamespace`; add new `data: SessionDataNamespace`; update `__init__` to construct both |
| `packages/haywire-core/src/haywire/core/execution/execution_context.py` | Rename `data` field → `app_data`; type is `AppDataNamespace | None` |
| `packages/haywire-core/src/haywire/core/execution/vm.py` | Rename `data_namespace` local + ExecutionContext kwarg from `data` → `app_data` |
| `packages/haywire-core/src/haywire/ui/session_manager.py` | Constructor takes `container: LibraryStateContainer`; `create_session` calls `container.attach_session(session.session_id)` after Session construction; `remove_session` calls `container.detach_session(session_id)` after `session.cleanup()` |
| `packages/haywire-studio/src/haywire_studio/app.py` | Pass `self.library_state_container` into `SessionManager(...)` |
| `tests/ui/test_session_context_data.py` | Migrate `class Pool(LibraryState)` → `class Pool(AppState)`; update `ctx.data` → `ctx.app_data` for AppState lookups |
| `tests/core/test_execution/test_execution_context_data.py` | Migrate `class Pool(LibraryState)` → `class Pool(AppState)`; rename `ctx.data` references → `ctx.app_data` |
| `tests/core/test_execution/test_vm_library_state.py` | Migrate `class Pool(LibraryState)` → `class Pool(AppState)`; rename `ctx.data` → `ctx.app_data` |
| `tests/core/test_execution/test_interpreter_library_state.py` | (No subclass refs but keep file name; minor type-hint updates if any) |
| `tests/core/test_state/test_registry.py` | Migrate `class MyState(LibraryState)` → `class MyState(AppState)`; assertion `_class_filter(LibraryState) is False` extended for AppState/SessionState too |
| `tests/core/test_state/test_data_namespace.py` | Rename to use `AppState` subclasses; rename `DataNamespace` references → `AppDataNamespace` |
| `tests/core/test_state/test_library_state.py` | Rename → `test_app_state.py`; `class MyState(LibraryState)` → `class MyState(AppState)` (or add new file and keep this one with marker-base tests — see Task 1 step 6) |
| `tests/core/test_state/test_container.py` | Migrate `class MyState(LibraryState)` → `class MyState(AppState)` |
| `tests/core/test_state/test_di_wiring.py` | (Imports may need updating once container changes ship) |
| `tests/core/test_state/test_integration.py` | Migrate `class TestPool(LibraryState)` → `class TestPool(AppState)` |
| `docs/documentation/architecture/library_state.md` | Update cross-references and prose to reflect new taxonomy (`LibraryState` abstract marker; `AppState` is the concrete app base); link to `session_state.md` |
| `docs/documentation/architecture/session_state.md` | Status header updated to "v1.1 implemented" once Task 9 verifies green |

---

## Task 1: Rename — `LibraryState` to abstract marker, add `AppState`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/state/base.py`
- Modify: `packages/haywire-core/src/haywire/core/state/__init__.py`
- Modify: `packages/haywire-core/src/haywire/core/state/registry.py`
- Modify: `packages/haywire-core/src/haywire/core/state/container.py`
- Rename: `tests/core/test_state/test_library_state.py` → `tests/core/test_state/test_app_state.py`
- Modify: every internal test that subclasses `LibraryState` directly

This task is a single atomic refactor. The rename has to land in one commit because the registry filter, the type hints, and the internal test subclasses are entangled.

- [ ] **Step 1: Read the existing base.py to confirm starting point**

Read `packages/haywire-core/src/haywire/core/state/base.py`. Confirm it contains a single `LibraryState` class with the `class_identity: LibraryStateClassIdentity` annotation (added during v1's Task 3 cleanup commit).

- [ ] **Step 2: Rewrite base.py to introduce the marker + concrete `AppState`**

Replace the entire contents of `packages/haywire-core/src/haywire/core/state/base.py` with:

```python
"""LibraryState taxonomy — abstract marker + concrete scope bases.

A library author **never directly subclasses `LibraryState`**. They pick
one of the concrete scope bases:

  - `AppState`     — one instance, shared across all sessions and execution.
  - `SessionState` — one instance per UI session.

The mental rule is one line: *scope = base class*. Inheritance picks
multiplicity. See docs/documentation/architecture/session_state.md.
"""

from __future__ import annotations

from haywire.core.state.identity import LibraryStateClassIdentity


class LibraryState:
    """Abstract marker base. Never directly subclassed by users.

    Exists as a type-system hierarchy root and as the registry-filter
    target for `issubclass(cls, LibraryState)`. Concrete bases are
    `AppState` (app-global) and `SessionState` (per-session).
    """

    class_identity: LibraryStateClassIdentity


class AppState(LibraryState):
    """Concrete base for app-global library state.

    One instance is created when the owning library is enabled and
    shared across every browser session and the execution VM. The
    framework calls optional `on_enable()` after instantiation and
    optional `on_disable()` before teardown.

    See docs/documentation/architecture/library_state.md.
    """


# `SessionState` is added in Task 2.
```

- [ ] **Step 3: Widen the registry filter exclusion to include `AppState`**

Open `packages/haywire-core/src/haywire/core/state/registry.py`. Find `_class_filter` (around line 29). Replace:

```python
    def _class_filter(self, cls: type) -> bool:
        try:
            return inspect.isclass(cls) and issubclass(cls, LibraryState) and cls is not LibraryState
        except TypeError:
            return False
```

with:

```python
    def _class_filter(self, cls: type) -> bool:
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, LibraryState)
                and cls not in _MARKER_BASES
            )
        except TypeError:
            return False
```

At the top of `registry.py`, after the existing imports, add:

```python
from haywire.core.state.base import AppState

_MARKER_BASES: tuple[type, ...] = (LibraryState, AppState)
```

(The `SessionState` entry is added in Task 2.)

- [ ] **Step 4: Update `_register_class` parameter type hint**

In the same file, find:

```python
    def _register_class(self, cls: type[LibraryState], library_identity: LibraryIdentity) -> str | None:
```

This stays as `type[LibraryState]` (covers both AppState and SessionState transitively). No change needed — leave it as is.

- [ ] **Step 5: Update container internal type hints**

Open `packages/haywire-core/src/haywire/core/state/container.py`. Find the `__init__`:

```python
        self._instances_by_class: dict[type[LibraryState], LibraryState] = {}
        self._class_by_registry_key: dict[str, type[LibraryState]] = {}
```

Leave these as-is for now (`type[LibraryState]` still covers AppState transitively). The container is restructured in Task 3 — for Task 1 we only do the rename surface.

The `T = TypeVar("T", bound=LibraryState)` near the top of the file also stays. Likewise, `__getitem__(self, cls: type[T]) -> T` continues to typecheck for AppState subclasses.

- [ ] **Step 6: Rename test file and migrate test subclasses**

Run:

```bash
git mv tests/core/test_state/test_library_state.py tests/core/test_state/test_app_state.py
```

Open `tests/core/test_state/test_app_state.py`. Replace its entire contents with:

```python
"""Unit tests for AppState base class.

LibraryState (the abstract marker) is implicitly tested via AppState
(its concrete subclass).
"""

from haywire.core.state import AppState, LibraryState


class TestAppStateBase:
    def test_app_state_is_subclass_of_library_state(self):
        """AppState must inherit from the abstract marker base."""
        assert issubclass(AppState, LibraryState)

    def test_subclass_can_be_instantiated_with_no_arguments(self):
        class MyState(AppState):
            pass

        instance = MyState()
        assert isinstance(instance, AppState)
        assert isinstance(instance, LibraryState)

    def test_on_enable_is_optional(self):
        class NoHooks(AppState):
            pass

        instance = NoHooks()
        assert not hasattr(instance, "on_enable") or callable(instance.on_enable)

    def test_on_enable_when_defined_is_callable(self):
        calls: list[str] = []

        class WithHooks(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

            def on_disable(self) -> None:
                calls.append("disable")

        instance = WithHooks()
        instance.on_enable()
        instance.on_disable()
        assert calls == ["enable", "disable"]

    def test_subclass_can_carry_arbitrary_fields(self):
        class FullOfStuff(AppState):
            def __init__(self) -> None:
                self.devices: list[str] = []
                self.counter: int = 0

        instance = FullOfStuff()
        instance.devices.append("dev0")
        instance.counter += 1
        assert instance.devices == ["dev0"]
        assert instance.counter == 1
```

- [ ] **Step 7: Migrate every other internal `class Foo(LibraryState)`**

The following files contain `class <Name>(LibraryState):`. In each, change `LibraryState` → `AppState` (one-by-one or with a single `find/sed`):

```
tests/core/test_state/test_registry.py            (5 occurrences in test methods)
tests/core/test_state/test_data_namespace.py      (5 occurrences: MidiPool, NotRegistered×2, V1, V2)
tests/core/test_state/test_container.py           (multiple — every test class that subclasses LibraryState)
tests/core/test_state/test_integration.py         (1 occurrence: TestPool)
tests/core/test_execution/test_execution_context_data.py  (1 occurrence: Pool)
tests/core/test_execution/test_vm_library_state.py        (1 occurrence: Pool)
tests/ui/test_session_context_data.py             (1 occurrence: Pool)
```

For each, also update the import line to import `AppState` instead of (or in addition to) `LibraryState`:

```python
# Was:
from haywire.core.state import LibraryState

# Now:
from haywire.core.state import AppState
```

If the test still references `LibraryState` directly (e.g., `assert reg._class_filter(LibraryState) is False`), keep that import line and add `AppState` to it.

In `tests/core/test_state/test_registry.py`, find `test_class_filter_rejects_base_class`. Update:

```python
    def test_class_filter_rejects_base_class(self):
        reg = LibraryStateRegistry()
        assert reg._class_filter(LibraryState) is False
```

extended to:

```python
    def test_class_filter_rejects_marker_bases(self):
        from haywire.core.state import AppState
        reg = LibraryStateRegistry()
        assert reg._class_filter(LibraryState) is False
        assert reg._class_filter(AppState) is False
```

- [ ] **Step 8: Update `state/__init__.py` to export `AppState`**

Open `packages/haywire-core/src/haywire/core/state/__init__.py`. Change to:

```python
"""Library-owned runtime state — see docs/documentation/architecture/library_state.md."""

from haywire.core.state.base import AppState, LibraryState
from haywire.core.state.container import LibraryStateContainer
from haywire.core.state.data_namespace import DataNamespace
from haywire.core.state.identity import LibraryStateClassIdentity
from haywire.core.state.registry import LibraryStateRegistry

__all__ = [
    "AppState",
    "DataNamespace",
    "LibraryState",
    "LibraryStateClassIdentity",
    "LibraryStateContainer",
    "LibraryStateRegistry",
]
```

(`SessionState` and the namespace renames are added in Tasks 2 and 4.)

- [ ] **Step 9: Run the full state + execution + UI test suites**

```
uv run pytest tests/core/test_state/ tests/core/test_execution/ tests/ui/test_session_context_data.py tests/ui/test_session_context_reactive.py -v
```

Expected: all green. Any test that still subclasses `LibraryState` directly will fail because the test class is no longer registry-acceptable (filter excludes it). If anything fails, find the offending file and migrate it.

- [ ] **Step 10: Run full unit suite for regressions**

```
uv run pytest -m "not integration"
```

Expected: 904+ passed, 0 failed.

- [ ] **Step 11: Lint and type check**

```
uv run ruff check packages/haywire-core/src/haywire/core/state/ tests/core/test_state/ tests/core/test_execution/ tests/ui/
uv run mypy packages/haywire-core/src/haywire/core/state/
```

Expected: clean.

- [ ] **Step 12: Commit**

```bash
git add packages/haywire-core/src/haywire/core/state/base.py \
        packages/haywire-core/src/haywire/core/state/__init__.py \
        packages/haywire-core/src/haywire/core/state/registry.py \
        tests/core/test_state/ \
        tests/core/test_execution/ \
        tests/ui/test_session_context_data.py
git commit -m "refactor(state): introduce AppState concrete base; LibraryState becomes abstract marker

Restructures the LibraryState taxonomy: LibraryState is now an abstract
marker base (never directly subclassed by users); AppState takes over
as the concrete app-global base. Registry filter excludes both markers.
All internal test subclasses migrate from LibraryState to AppState
atomically — zero external library consumers (verified by smoke test
showing 0 LibraryState classes registered).

Lays the groundwork for SessionState as a sibling concrete base."
```

---

## Task 2: Add `SessionState` base with LibrarySettings prohibition

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/state/base.py`
- Modify: `packages/haywire-core/src/haywire/core/state/__init__.py`
- Modify: `packages/haywire-core/src/haywire/core/state/registry.py`
- Test: `tests/core/test_state/test_session_state.py`

- [ ] **Step 1: Write failing tests for SessionState base**

Write to `tests/core/test_state/test_session_state.py`:

```python
"""Unit tests for SessionState base class.

Covers:
  - SessionState is a subclass of LibraryState (and a sibling of AppState).
  - Lifecycle hooks (on_enable, on_disable) are duck-typed, same as AppState.
  - The `session_id` attribute is annotated on the base.
  - __init_subclass__ rejects fields whose annotation references LibrarySettings
    (both bare and Optional/Union forms).
"""

import pytest

from haywire.core.settings.schema import LibrarySettings
from haywire.core.state import AppState, LibraryState, SessionState


class TestSessionStateBase:
    def test_session_state_is_subclass_of_library_state(self):
        assert issubclass(SessionState, LibraryState)

    def test_session_state_is_not_a_subclass_of_app_state(self):
        """AppState and SessionState are siblings, not parent/child."""
        assert not issubclass(SessionState, AppState)
        assert not issubclass(AppState, SessionState)

    def test_subclass_can_be_instantiated(self):
        class MySS(SessionState):
            pass

        instance = MySS()
        assert isinstance(instance, SessionState)
        assert isinstance(instance, LibraryState)

    def test_session_id_attribute_is_annotated(self):
        """The container stamps session_id; the annotation lets type-checkers see it."""
        assert "session_id" in SessionState.__annotations__

    def test_on_enable_is_optional(self):
        class NoHooks(SessionState):
            pass

        instance = NoHooks()
        assert not hasattr(instance, "on_enable") or callable(instance.on_enable)


class TestSessionStateLibrarySettingsProhibition:
    def test_bare_library_settings_field_rejected(self):
        """A field annotated as a LibrarySettings subclass must raise at class definition."""

        class MySettings(LibrarySettings):
            pass

        with pytest.raises(TypeError, match="LibrarySettings cannot be composed"):

            class BadState(SessionState):
                config: MySettings

    def test_optional_library_settings_field_rejected(self):
        """`Optional[X]` and `X | None` annotations also caught."""

        class MySettings(LibrarySettings):
            pass

        with pytest.raises(TypeError, match="LibrarySettings cannot be composed"):

            class BadState(SessionState):
                config: MySettings | None = None

    def test_union_library_settings_field_rejected(self):
        """Union annotations with LibrarySettings somewhere in the union are caught."""

        class MySettings(LibrarySettings):
            pass

        with pytest.raises(TypeError, match="LibrarySettings cannot be composed"):

            class BadState(SessionState):
                config: int | MySettings

    def test_unrelated_field_not_rejected(self):
        """Fields without LibrarySettings types pass."""

        class GoodState(SessionState):
            cache: dict[str, int] = {}
            counter: int = 0

        # Class definition succeeds.
        instance = GoodState()
        assert instance.cache == {}

    def test_app_state_is_not_subject_to_the_check(self):
        """AppState may compose LibrarySettings (per library_state.md §5.1)."""

        class MySettings(LibrarySettings):
            pass

        # Must not raise.
        class GoodAppState(AppState):
            config: MySettings | None = None
```

- [ ] **Step 2: Run the tests to verify they fail**

```
uv run pytest tests/core/test_state/test_session_state.py -v
```

Expected: FAIL with `ImportError: cannot import name 'SessionState'` or similar.

- [ ] **Step 3: Add `SessionState` class with `__init_subclass__` check**

Open `packages/haywire-core/src/haywire/core/state/base.py`. Append to the file:

```python


class SessionState(LibraryState):
    """Concrete base for per-UI-session library state.

    One instance is created per active session × per registered SessionState
    class. The container stamps ``self.session_id`` between ``cls()`` and
    ``on_enable()`` — read it in ``on_enable`` or any later method, never
    in ``__init__``.

    A SessionState **must not** compose ``LibrarySettings`` as a field —
    settings are app-global, sessions are per-session. The
    ``__init_subclass__`` check below catches this at class-definition time.

    See docs/documentation/architecture/session_state.md.
    """

    session_id: str   # set by the container before on_enable runs

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
    import typing

    origin = typing.get_origin(ann)
    if origin is None:
        return [ann]
    if origin in (typing.Union, getattr(__import__("types"), "UnionType", type(None))):
        out: list[object] = []
        for arg in typing.get_args(ann):
            out.extend(_flatten_annotation(arg))
        return out
    return [ann]
```

- [ ] **Step 4: Update `__init__.py` to export `SessionState`**

In `packages/haywire-core/src/haywire/core/state/__init__.py`:

```python
"""Library-owned runtime state — see docs/documentation/architecture/library_state.md."""

from haywire.core.state.base import AppState, LibraryState, SessionState
from haywire.core.state.container import LibraryStateContainer
from haywire.core.state.data_namespace import DataNamespace
from haywire.core.state.identity import LibraryStateClassIdentity
from haywire.core.state.registry import LibraryStateRegistry

__all__ = [
    "AppState",
    "DataNamespace",
    "LibraryState",
    "LibraryStateClassIdentity",
    "LibraryStateContainer",
    "LibraryStateRegistry",
    "SessionState",
]
```

- [ ] **Step 5: Update registry filter exclusion to include `SessionState`**

In `packages/haywire-core/src/haywire/core/state/registry.py`, update the imports + module-level `_MARKER_BASES`:

```python
from haywire.core.state.base import AppState, SessionState

_MARKER_BASES: tuple[type, ...] = (LibraryState, AppState, SessionState)
```

- [ ] **Step 6: Run tests to verify they pass**

```
uv run pytest tests/core/test_state/test_session_state.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 7: Run full state + lint + mypy**

```
uv run pytest tests/core/test_state/ -v
uv run ruff check packages/haywire-core/src/haywire/core/state/ tests/core/test_state/
uv run mypy packages/haywire-core/src/haywire/core/state/
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/core/state/base.py \
        packages/haywire-core/src/haywire/core/state/__init__.py \
        packages/haywire-core/src/haywire/core/state/registry.py \
        tests/core/test_state/test_session_state.py
git commit -m "feat(state): add SessionState base with LibrarySettings prohibition

SessionState is the per-UI-session sibling of AppState. Both inherit
from the LibraryState abstract marker. The container will stamp
self.session_id between cls() and on_enable() (Task 3).

__init_subclass__ rejects fields whose annotation references
LibrarySettings (bare, Optional, or Union form) — composing global
settings inside per-session state is a semantic contradiction. Caught
at class-definition time with a clear error pointing at the offending
field. See docs/documentation/architecture/session_state.md §5.2."
```

---

## Task 3: Extend `LibraryStateContainer` with two-scope storage and dispatch

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/state/container.py`
- Test: `tests/core/test_state/test_container_session_scope.py`

- [ ] **Step 1: Write failing tests for two-scope behavior**

Write to `tests/core/test_state/test_container_session_scope.py`:

```python
"""Unit tests for LibraryStateContainer's two-scope behavior.

Covers:
  - AppState classes still work as before (regression).
  - SessionState classes are dispatched to per-session storage.
  - `attach_session(sid)` instantiates one of every registered SessionState
    class for that session, calling on_enable each time, and stamping session_id.
  - `detach_session(sid)` calls on_disable on every per-session instance and
    drops them.
  - CLASS_ADDED for a SessionState class (while sessions are already attached)
    fans out — one instance per known session.
  - CLASS_REMOVED for a SessionState class drops every per-session instance,
    calling on_disable on each.
  - CLASS_RELOADED for a SessionState class disables every old per-session
    instance, then enables a new one with the new class.
  - `get_session(cls, sid)` and `get_session_optional(cls, sid)` return what
    was stored.
"""

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state import (
    AppState,
    LibraryStateContainer,
    LibraryStateRegistry,
    SessionState,
)
from haywire.core.state.identity import LibraryStateClassIdentity


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


class TestAppScopeRegression:
    def test_app_state_class_still_creates_singleton(self):
        class Pool(AppState):
            pass

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg._register_class(Pool, lib_id)

        container.on_lifecycle_events([make_added_event(Pool, lib_id)])
        assert Pool in container
        assert container[Pool] is container[Pool]   # singleton


class TestSessionAttachDetach:
    def test_attach_then_class_added_creates_one_instance_per_session(self):
        calls: list[tuple[str, str]] = []

        class TimelineCursor(SessionState):
            def on_enable(self) -> None:
                calls.append(("enable", self.session_id))

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()

        # Attach two sessions BEFORE class is registered.
        container.attach_session("s1")
        container.attach_session("s2")

        # Now register and add the SessionState class.
        reg._register_class(TimelineCursor, lib_id)
        container.on_lifecycle_events([make_added_event(TimelineCursor, lib_id)])

        # One instance per session.
        i1 = container.get_session(TimelineCursor, "s1")
        i2 = container.get_session(TimelineCursor, "s2")
        assert isinstance(i1, TimelineCursor)
        assert isinstance(i2, TimelineCursor)
        assert i1 is not i2
        # session_id stamped before on_enable.
        assert i1.session_id == "s1"
        assert i2.session_id == "s2"
        assert sorted(calls) == [("enable", "s1"), ("enable", "s2")]

    def test_class_added_then_attach_creates_instance(self):
        calls: list[str] = []

        class Cursor(SessionState):
            def on_enable(self) -> None:
                calls.append(self.session_id)

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()

        # Register class first; no sessions yet.
        reg._register_class(Cursor, lib_id)
        container.on_lifecycle_events([make_added_event(Cursor, lib_id)])
        assert calls == []   # no instance, no session

        # Attach a session — instance is created.
        container.attach_session("only")
        assert isinstance(container.get_session(Cursor, "only"), Cursor)
        assert calls == ["only"]

    def test_detach_session_calls_on_disable_and_drops_instances(self):
        calls: list[tuple[str, str]] = []

        class Cursor(SessionState):
            def on_enable(self) -> None:
                calls.append(("enable", self.session_id))

            def on_disable(self) -> None:
                calls.append(("disable", self.session_id))

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg._register_class(Cursor, lib_id)
        container.on_lifecycle_events([make_added_event(Cursor, lib_id)])
        container.attach_session("s1")

        container.detach_session("s1")
        assert container.get_session_optional(Cursor, "s1") is None
        assert ("disable", "s1") in calls

    def test_get_session_optional_returns_none_for_missing(self):
        class Cursor(SessionState):
            pass

        container = LibraryStateContainer()
        assert container.get_session_optional(Cursor, "nope") is None


class TestSessionScopeHotReload:
    def test_class_removed_drops_all_per_session_instances(self):
        calls: list[tuple[str, str]] = []

        class Cursor(SessionState):
            def on_enable(self) -> None:
                calls.append(("enable", self.session_id))

            def on_disable(self) -> None:
                calls.append(("disable", self.session_id))

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg._register_class(Cursor, lib_id)
        container.on_lifecycle_events([make_added_event(Cursor, lib_id)])
        container.attach_session("s1")
        container.attach_session("s2")

        container.on_lifecycle_events([make_removed_event(Cursor, lib_id)])

        assert container.get_session_optional(Cursor, "s1") is None
        assert container.get_session_optional(Cursor, "s2") is None
        assert ("disable", "s1") in calls
        assert ("disable", "s2") in calls

    def test_class_reloaded_swaps_per_session_instances(self):
        calls: list[tuple[str, str]] = []

        ident = LibraryStateClassIdentity(
            class_name="V", module=__name__,
            registry_id="V", registry_key="midi:state:V", label="V",
        )

        class V1(SessionState):
            def on_enable(self) -> None:
                calls.append(("v1-enable", self.session_id))

            def on_disable(self) -> None:
                calls.append(("v1-disable", self.session_id))

        class V2(SessionState):
            def on_enable(self) -> None:
                calls.append(("v2-enable", self.session_id))

            def on_disable(self) -> None:
                calls.append(("v2-disable", self.session_id))

        V1.class_identity = ident
        V2.class_identity = ident

        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        container.on_lifecycle_events([make_added_event(V1, lib_id)])
        container.attach_session("s1")
        # Initial enable.
        assert ("v1-enable", "s1") in calls

        # Hot-reload: same registry_key, new class.
        reload_event = LifeCycleEvent(
            registry_key="midi:state:V",
            event_type=LifeCycleEventType.CLASS_RELOADED,
            affected_class=V2,
            library_identity=lib_id,
        )
        container.on_lifecycle_events([reload_event])

        # Old V1 instance disabled, new V2 instance enabled (still session "s1").
        assert ("v1-disable", "s1") in calls
        assert ("v2-enable", "s1") in calls
        new_inst = container.get_session(V2, "s1")
        assert isinstance(new_inst, V2)
        assert new_inst.session_id == "s1"
```

- [ ] **Step 2: Run the tests to verify they fail**

```
uv run pytest tests/core/test_state/test_container_session_scope.py -v
```

Expected: FAIL — `attach_session`, `get_session`, `get_session_optional` don't exist yet.

- [ ] **Step 3: Refactor container internals to two-scope storage**

Replace the contents of `packages/haywire-core/src/haywire/core/state/container.py` with:

```python
"""LibraryStateContainer — owns the LibraryState instance pool.

Subscribes to LibraryStateRegistry batch lifecycle events. Holds two
scope-keyed maps:

  - `_app`      : type[AppState]      → AppState                — singleton per class
  - `_sessions` : type[SessionState]  → dict[session_id, SessionState] — one per (class, session)

Dispatch decision is `issubclass(cls, SessionState)` at event time. See
docs/documentation/architecture/session_state.md §3.
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
        # App-scoped: one instance per class.
        self._app: dict[type[AppState], AppState] = {}
        # Session-scoped: one instance per (class, session_id).
        self._sessions: dict[type[SessionState], dict[str, SessionState]] = {}
        # Active sessions tracked for fanout on CLASS_ADDED for SessionState classes.
        self._known_session_ids: set[str] = set()
        # Reverse map: registry_key → class. Used for CLASS_RELOADED to find old class.
        self._class_by_registry_key: dict[str, type[LibraryState]] = {}

    # ------------------------------------------------------------------
    # Public lookup API — used by AppDataNamespace
    # ------------------------------------------------------------------

    def __getitem__(self, cls: type[A]) -> A:
        try:
            return self._app[cls]  # type: ignore[return-value]
        except KeyError:
            raise KeyError(
                f"No AppState instance registered for class {cls.__name__}. "
                f"Either the owning library is not enabled, or the class is not "
                f"a registered AppState subclass."
            ) from None

    def get(self, cls: type[A]) -> A | None:
        return self._app.get(cls)  # type: ignore[return-value]

    def __contains__(self, cls: type) -> bool:
        return cls in self._app

    # ------------------------------------------------------------------
    # Public lookup API — used by SessionDataNamespace
    # ------------------------------------------------------------------

    def get_session(self, cls: type[S], session_id: str) -> S:
        try:
            bag = self._sessions[cls]
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
        return self._sessions.get(cls, {}).get(session_id)  # type: ignore[return-value]

    def has_session(self, cls: type[S], session_id: str) -> bool:
        return session_id in self._sessions.get(cls, {})

    # ------------------------------------------------------------------
    # Session lifecycle — called by SessionManager
    # ------------------------------------------------------------------

    def attach_session(self, session_id: str) -> None:
        """Instantiate one of every registered SessionState class for this session."""
        if session_id in self._known_session_ids:
            return  # idempotent
        self._known_session_ids.add(session_id)
        for cls, bag in self._sessions.items():
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
                logger.error(
                    "LibraryStateContainer error handling %s: %s", event, exc, exc_info=True
                )

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

    def _remove(self, event: LifeCycleEvent) -> None:
        old_cls = self._class_by_registry_key.pop(event.registry_key, None)
        if old_cls is None:
            return
        if issubclass(old_cls, SessionState):
            self._remove_session_class(old_cls)
        elif issubclass(old_cls, AppState):
            self._remove_app_class(old_cls)

    def _reload(self, event: LifeCycleEvent) -> None:
        # Drop the OLD class first (whichever scope), then add the NEW one.
        old_cls = self._class_by_registry_key.pop(event.registry_key, None)
        if old_cls is not None:
            if issubclass(old_cls, SessionState):
                self._remove_session_class(old_cls)
            elif issubclass(old_cls, AppState):
                self._remove_app_class(old_cls)

        new_cls = event.affected_class
        if new_cls is None:
            return
        if issubclass(new_cls, SessionState):
            self._add_session_class(new_cls, event.registry_key)
        elif issubclass(new_cls, AppState):
            self._add_app_class(new_cls, event.registry_key)

    # ------------------------------------------------------------------
    # AppState scope helpers
    # ------------------------------------------------------------------

    def _add_app_class(self, cls: type[AppState], registry_key: str) -> None:
        if cls in self._app:
            return  # idempotent
        instance = cls()
        self._app[cls] = instance
        self._class_by_registry_key[registry_key] = cls
        self._call_on_enable(instance)

    def _remove_app_class(self, cls: type[AppState]) -> None:
        instance = self._app.pop(cls, None)
        if instance is not None:
            self._call_on_disable(instance)

    # ------------------------------------------------------------------
    # SessionState scope helpers
    # ------------------------------------------------------------------

    def _add_session_class(self, cls: type[SessionState], registry_key: str) -> None:
        if cls in self._sessions:
            return  # idempotent
        bag: dict[str, SessionState] = {}
        self._sessions[cls] = bag
        self._class_by_registry_key[registry_key] = cls
        # Fan out across known sessions.
        for sid in self._known_session_ids:
            self._instantiate_session_state(cls, bag, sid)

    def _remove_session_class(self, cls: type[SessionState]) -> None:
        bag = self._sessions.pop(cls, {})
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
                cls.__name__, session_id, exc, exc_info=True,
            )
            return
        instance.session_id = session_id   # stamp before on_enable
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

- [ ] **Step 4: Run the new tests to verify they pass**

```
uv run pytest tests/core/test_state/test_container_session_scope.py -v
```

Expected: all PASS.

- [ ] **Step 5: Run pre-existing container tests for regressions**

```
uv run pytest tests/core/test_state/test_container.py -v
```

Expected: all PASS — the AppState path is unchanged in behavior. If `tests/core/test_state/test_container.py` references `_instances_by_class` directly (old internal name), update those references to `_app` (or use the public `__getitem__` / `__contains__` instead).

- [ ] **Step 6: Run full state suite**

```
uv run pytest tests/core/test_state/ -v
uv run ruff check packages/haywire-core/src/haywire/core/state/ tests/core/test_state/
uv run mypy packages/haywire-core/src/haywire/core/state/
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/state/container.py \
        tests/core/test_state/test_container_session_scope.py \
        tests/core/test_state/test_container.py
git commit -m "feat(state): two-scope LibraryStateContainer with session attach/detach

Container now holds AppState instances and SessionState instances side by
side. Dispatch by issubclass(cls, SessionState) at lifecycle event time:
AppState path is unchanged singleton behavior; SessionState path fans
out across known session ids on CLASS_ADDED and on attach_session.

New public API for SessionDataNamespace consumption:
  - get_session(cls, session_id) -> instance        (raises KeyError)
  - get_session_optional(cls, session_id) -> opt    (returns None)
  - has_session(cls, session_id) -> bool
  - attach_session(session_id)                      (driven by SessionManager)
  - detach_session(session_id)

self.session_id is stamped on every SessionState instance between cls()
and on_enable(). cls() exceptions are logged and skipped — they don't
break session creation.

See docs/documentation/architecture/session_state.md §3."
```

---

## Task 4: Rename `DataNamespace` → `AppDataNamespace`; add `SessionDataNamespace`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/state/data_namespace.py`
- Modify: `packages/haywire-core/src/haywire/core/state/__init__.py`
- Modify: `tests/core/test_state/test_data_namespace.py` (renames + AppDataNamespace usage)
- Test: `tests/core/test_state/test_session_data_namespace.py` (new)

- [ ] **Step 1: Write failing tests for `SessionDataNamespace`**

Write to `tests/core/test_state/test_session_data_namespace.py`:

```python
"""Unit tests for SessionDataNamespace — the per-session typed proxy."""

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state import (
    LibraryStateContainer,
    LibraryStateRegistry,
    SessionState,
)
from haywire.core.state.data_namespace import SessionDataNamespace


def make_lib_identity() -> LibraryIdentity:
    return LibraryIdentity(
        id="midi", label="Midi", version="0.0.1",
        description="", url="", help_url="", author="", author_url="",
        dependencies=[], tags=[], module_name="haybale_midi", folder_path="",
    )


class TestSessionDataNamespace:
    def test_getitem_returns_per_session_instance(self):
        class TimelineCursor(SessionState):
            position = 0.0

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg._register_class(TimelineCursor, lib_id)
        container.on_lifecycle_events([
            LifeCycleEvent(
                registry_key=TimelineCursor.class_identity.registry_key,
                event_type=LifeCycleEventType.CLASS_ADDED,
                affected_class=TimelineCursor,
                library_identity=lib_id,
            )
        ])
        container.attach_session("s1")
        container.attach_session("s2")

        ns_s1 = SessionDataNamespace(container, "s1")
        ns_s2 = SessionDataNamespace(container, "s2")

        assert isinstance(ns_s1[TimelineCursor], TimelineCursor)
        assert isinstance(ns_s2[TimelineCursor], TimelineCursor)
        assert ns_s1[TimelineCursor] is not ns_s2[TimelineCursor]
        assert ns_s1[TimelineCursor].session_id == "s1"
        assert ns_s2[TimelineCursor].session_id == "s2"

    def test_getitem_raises_keyerror_for_unregistered(self):
        class NotRegistered(SessionState):
            pass

        ns = SessionDataNamespace(LibraryStateContainer(), "anysid")
        with pytest.raises(KeyError):
            _ = ns[NotRegistered]

    def test_get_returns_none_for_missing(self):
        class NotRegistered(SessionState):
            pass

        ns = SessionDataNamespace(LibraryStateContainer(), "anysid")
        assert ns.get(NotRegistered) is None

    def test_contains_reflects_per_session_membership(self):
        class Cursor(SessionState):
            pass

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg._register_class(Cursor, lib_id)
        container.on_lifecycle_events([
            LifeCycleEvent(
                registry_key=Cursor.class_identity.registry_key,
                event_type=LifeCycleEventType.CLASS_ADDED,
                affected_class=Cursor,
                library_identity=lib_id,
            )
        ])
        container.attach_session("s1")

        ns_s1 = SessionDataNamespace(container, "s1")
        ns_s2 = SessionDataNamespace(container, "s2")    # not attached
        assert Cursor in ns_s1
        assert Cursor not in ns_s2
```

- [ ] **Step 2: Run the tests to verify they fail**

```
uv run pytest tests/core/test_state/test_session_data_namespace.py -v
```

Expected: FAIL — `SessionDataNamespace` doesn't exist.

- [ ] **Step 3: Rewrite `data_namespace.py` with both classes**

Replace the contents of `packages/haywire-core/src/haywire/core/state/data_namespace.py` with:

```python
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


# Backwards-compatible alias for any external code that imports DataNamespace.
# The public canonical name is AppDataNamespace.
DataNamespace = AppDataNamespace
```

- [ ] **Step 4: Update `__init__.py` to export both namespaces**

In `packages/haywire-core/src/haywire/core/state/__init__.py`:

```python
"""Library-owned runtime state — see docs/documentation/architecture/library_state.md."""

from haywire.core.state.base import AppState, LibraryState, SessionState
from haywire.core.state.container import LibraryStateContainer
from haywire.core.state.data_namespace import (
    AppDataNamespace,
    DataNamespace,           # deprecated alias of AppDataNamespace
    SessionDataNamespace,
)
from haywire.core.state.identity import LibraryStateClassIdentity
from haywire.core.state.registry import LibraryStateRegistry

__all__ = [
    "AppDataNamespace",
    "AppState",
    "DataNamespace",
    "LibraryState",
    "LibraryStateClassIdentity",
    "LibraryStateContainer",
    "LibraryStateRegistry",
    "SessionDataNamespace",
    "SessionState",
]
```

- [ ] **Step 5: Update `test_data_namespace.py` references**

Open `tests/core/test_state/test_data_namespace.py`. Change all `DataNamespace` references to `AppDataNamespace`. Confirm the `class V1(LibraryState)` / `class V2(LibraryState)` cases were already migrated to `AppState` in Task 1 (if not, do it now). Update the import:

```python
from haywire.core.state.data_namespace import AppDataNamespace
```

and in the test bodies, replace every `DataNamespace(container)` with `AppDataNamespace(container)`.

- [ ] **Step 6: Run all data-namespace tests**

```
uv run pytest tests/core/test_state/test_data_namespace.py tests/core/test_state/test_session_data_namespace.py -v
```

Expected: all PASS.

- [ ] **Step 7: Lint + mypy**

```
uv run ruff check packages/haywire-core/src/haywire/core/state/ tests/core/test_state/
uv run mypy packages/haywire-core/src/haywire/core/state/
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/core/state/data_namespace.py \
        packages/haywire-core/src/haywire/core/state/__init__.py \
        tests/core/test_state/test_data_namespace.py \
        tests/core/test_state/test_session_data_namespace.py
git commit -m "feat(state): two scope-bound namespace proxies (AppDataNamespace + SessionDataNamespace)

Renames DataNamespace → AppDataNamespace (with bound=AppState TypeVar)
and adds SessionDataNamespace (bound=SessionState, carries session_id).
Wrong-scope lookups are caught statically by the type checker.

DataNamespace stays as a deprecated alias of AppDataNamespace for the
duration of the v1.1 transition. The public canonical name is
AppDataNamespace; the alias exists only to ease the rename diff.

See docs/documentation/architecture/session_state.md §2.3."
```

---

## Task 5: Update `SessionContext` — add `data: SessionDataNamespace`, rename old `data` → `app_data`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/context.py`
- Modify: `tests/ui/test_session_context_data.py`
- Modify: every file that reads `ctx.data` for the AppState namespace (internal only — verified)

- [ ] **Step 1: Find all internal `ctx.data` references**

```bash
grep -rn "ctx\.data\b\|ctx\.data\[" packages/haywire-core/src packages/haywire-studio/src tests barn 2>/dev/null | head -30
```

Capture the list. Every match (currently) refers to the AppState namespace and will rename to `ctx.app_data`. **Do not auto-replace** — read each match in context to confirm it's a state-namespace lookup (not, e.g., a `data` field on a node or DataPort).

- [ ] **Step 2: Update `SessionContext` field declarations and `__init__`**

Open `packages/haywire-core/src/haywire/ui/context.py`. Locate the SessionContext class (around line 37). Modify:

a) **Update imports near the top**. Replace:

```python
from haywire.core.state.data_namespace import DataNamespace
```

with:

```python
from haywire.core.state.data_namespace import AppDataNamespace, SessionDataNamespace
```

b) **Update the field declarations**. Find:

```python
    data: DataNamespace
```

Replace with:

```python
    app_data: AppDataNamespace
    data: SessionDataNamespace
```

c) **Update `__init__`** (around line 73). Replace:

```python
        self.data = DataNamespace(app.library_state_container)
```

with:

```python
        self.app_data = AppDataNamespace(app.library_state_container)
        self.data = SessionDataNamespace(app.library_state_container, session_id)
```

d) **Update the class docstring** (around line 37–47). The current docstring mentions `data` as the AppState namespace. Replace the text mentioning `data` with:

```python
    """
    Per-session context carrying current UI state.

    Reactive fields are accessed as `ctx.<field>.value` (read) or
    `ctx.<field>.value = ...` (write). Plain fields (`session_id`,
    `app`, `session`, `app_data`, `data`) are non-reactive.

    `ctx.data`     — typed proxy over the app's LibraryStateContainer for
                     SessionState lookups, scoped to this session.
    `ctx.app_data` — typed proxy over the app's LibraryStateContainer for
                     AppState lookups, shared across the whole app.

    See docs/documentation/architecture/session_state.md.
    """
```

e) **Update the module docstring** (around lines 14–17). Current text:

```
The `data` attribute is a typed DataNamespace proxy over the app's
LibraryStateContainer — class-keyed access to library-owned runtime
state. See docs/documentation/architecture/library_state.md.
```

Replace with:

```
SessionContext exposes two scope-bound proxies over the app's
LibraryStateContainer:

  - `ctx.app_data[Cls]` — AppState lookups (shared across the app).
  - `ctx.data[Cls]`     — SessionState lookups (this session's slice).

See docs/documentation/architecture/session_state.md.
```

- [ ] **Step 3: Update existing `tests/ui/test_session_context_data.py`**

Rename references throughout: `ctx.data[Pool]` → `ctx.app_data[Pool]` (Pool is an AppState class). Add new tests for `ctx.data[SessionStateClass]`:

Open `tests/ui/test_session_context_data.py`. The current file tests the `data` namespace as AppState. After Task 5, that's `app_data`. Restructure the file as follows (replace its entire contents):

```python
"""Tests for SessionContext.app_data (AppState) and SessionContext.data (SessionState)."""

from haywire.core.state import (
    AppState,
    LibraryStateContainer,
    SessionState,
)
from haywire.core.state.data_namespace import AppDataNamespace, SessionDataNamespace
from haywire.ui.context import SessionContext


class FakeApp:
    """Minimal IProjectState stub for SessionContext construction."""

    def __init__(self, container: LibraryStateContainer) -> None:
        self.library_state_container = container


class TestSessionContextAppData:
    def test_session_context_exposes_app_data_namespace(self):
        container = LibraryStateContainer()
        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert isinstance(ctx.app_data, AppDataNamespace)

    def test_app_data_resolves_to_container(self):
        class Pool(AppState):
            value: int = 42

        container = LibraryStateContainer()
        instance = Pool()
        container._app[Pool] = instance       # plant directly for the test

        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert ctx.app_data[Pool] is instance


class TestSessionContextSessionData:
    def test_session_context_exposes_data_namespace_bound_to_session_id(self):
        container = LibraryStateContainer()
        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert isinstance(ctx.data, SessionDataNamespace)
        # Internal: namespace knows its session_id.
        assert ctx.data._session_id == "s1"

    def test_session_context_no_longer_has_metadata(self):
        """metadata field removed in v1; this is the regression test."""
        container = LibraryStateContainer()
        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert not hasattr(ctx, "metadata")
```

- [ ] **Step 4: Update internal callers of `ctx.data`**

For every call site identified in Step 1, rewrite `ctx.data` → `ctx.app_data` if the lookup is for an AppState class. The internal callers identified earlier (from `tests/ui/test_canvas_handlers/`, etc.) currently DO NOT use `ctx.data` for state — they construct fake apps with `library_state_container = LibraryStateContainer()` for SessionContext construction. Confirm by re-running grep; if any `ctx.data[X]` calls remain in source (not test setup), update each.

- [ ] **Step 5: Run UI tests for regressions**

```
uv run pytest tests/ui/ -v
```

Expected: all PASS. The migrated test file plus the FakeApp stubs continue to work.

- [ ] **Step 6: Lint + mypy**

```
uv run ruff check packages/haywire-core/src/haywire/ui/context.py tests/ui/
uv run mypy packages/haywire-core/src/haywire/ui/context.py
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/context.py \
        tests/ui/test_session_context_data.py
git commit -m "feat(state): SessionContext gains data:SessionDataNamespace, renames data->app_data

SessionContext now exposes two scope-bound namespaces:
  - ctx.data      → SessionDataNamespace (this session's SessionState bag)
  - ctx.app_data  → AppDataNamespace (shared AppState pool)

The old ctx.data (AppState) is renamed to ctx.app_data. Internal callers
updated. Test file restructured to cover both namespaces.

See docs/documentation/architecture/session_state.md §2.3."
```

---

## Task 6: Update `ExecutionContext` and `HaywireVM` — rename `data` → `app_data`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/execution/execution_context.py`
- Modify: `packages/haywire-core/src/haywire/core/execution/vm.py`
- Modify: `tests/core/test_execution/test_execution_context_data.py`
- Modify: `tests/core/test_execution/test_vm_library_state.py`

- [ ] **Step 1: Update `ExecutionContext`**

Open `packages/haywire-core/src/haywire/core/execution/execution_context.py`. In the `TYPE_CHECKING` block, change:

```python
    from haywire.core.state.data_namespace import DataNamespace
```

to:

```python
    from haywire.core.state.data_namespace import AppDataNamespace
```

In the dataclass body, change:

```python
    data: Optional["DataNamespace"] = None
    """Class-keyed proxy to the app's LibraryStateContainer. None if the VM
    was constructed without a container reference (test contexts only)."""
```

to:

```python
    app_data: Optional["AppDataNamespace"] = None
    """Typed proxy to the app's LibraryStateContainer for AppState lookups.
    None if the VM was constructed without a container reference (test
    contexts only). ExecutionContext does not have a `data` (SessionState)
    namespace because graphs run app-globally — the VM has no notion of
    which UI session triggered execution. See
    docs/documentation/architecture/session_state.md §2.3."""
```

- [ ] **Step 2: Update `HaywireVM._create_execution_context`**

Open `packages/haywire-core/src/haywire/core/execution/vm.py`. Find the local variable `data_namespace` and the `ExecutionContext(...)` keyword arg. Replace:

```python
        from haywire.core.state.data_namespace import DataNamespace

        data_namespace: Optional[DataNamespace] = (
            DataNamespace(self._library_state_container)
            if self._library_state_container is not None
            else None
        )

        return ExecutionContext(
            ...,
            data=data_namespace,
        )
```

with:

```python
        from haywire.core.state.data_namespace import AppDataNamespace

        app_data_namespace: Optional[AppDataNamespace] = (
            AppDataNamespace(self._library_state_container)
            if self._library_state_container is not None
            else None
        )

        return ExecutionContext(
            ...,
            app_data=app_data_namespace,
        )
```

(Match the existing kwargs list — only the `data=` line is renamed; the other args stay.)

- [ ] **Step 3: Update execution-test references**

In `tests/core/test_execution/test_execution_context_data.py`:

- Replace `ctx.data` → `ctx.app_data` everywhere.
- Replace `data=ns` → `app_data=ns` in the `ExecutionContext(...)` constructor calls.
- Update `test_data_field_default_none` → `test_app_data_field_default_none`.
- Update `test_data_field_can_be_set` → `test_app_data_field_can_be_set`.
- Replace the `class Pool(LibraryState)` (already migrated to AppState in Task 1).

In `tests/core/test_execution/test_vm_library_state.py`:

- Replace `ctx.data` → `ctx.app_data` in assertions.
- Update test names if they contain "data" referring specifically to the AppState path.

- [ ] **Step 4: Run execution tests**

```
uv run pytest tests/core/test_execution/ -v
```

Expected: all PASS.

- [ ] **Step 5: Run full unit suite for regressions**

```
uv run pytest -m "not integration"
```

Expected: 904+ passed.

- [ ] **Step 6: Lint + mypy**

```
uv run ruff check packages/haywire-core/src/haywire/core/execution/ tests/core/test_execution/
uv run mypy packages/haywire-core/src/haywire/core/execution/
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/execution/execution_context.py \
        packages/haywire-core/src/haywire/core/execution/vm.py \
        tests/core/test_execution/test_execution_context_data.py \
        tests/core/test_execution/test_vm_library_state.py
git commit -m "feat(state): ExecutionContext renames data->app_data; no data attribute

ExecutionContext has only app_data (AppState lookups) — no `data`
attribute, because graphs run app-globally and the VM has no session.
HaywireVM._create_execution_context populates app_data from its
container reference.

The asymmetric availability of data/app_data across SessionContext and
ExecutionContext is intentional: it reflects the architectural reality
that node graphs are app-scoped, not session-scoped. Trying to read
exec_ctx.data is now an AttributeError caught statically by the type
checker.

See docs/documentation/architecture/session_state.md §2.3."
```

---

## Task 7: Wire `SessionManager` to call `attach_session` / `detach_session`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/session_manager.py`
- Modify: `packages/haywire-studio/src/haywire_studio/app.py`
- Test: `tests/core/test_state/test_session_manager_attach.py` (new)

- [ ] **Step 1: Write failing tests for SessionManager wiring**

Write to `tests/core/test_state/test_session_manager_attach.py`:

```python
"""Tests verifying SessionManager calls container.attach_session / detach_session
around session creation / removal."""

from unittest.mock import MagicMock

from haywire.core.state import LibraryStateContainer, SessionState
from haywire.ui.session_manager import SessionManager


class TestSessionManagerAttachDetach:
    def _make_session_kwargs(self, container: LibraryStateContainer) -> dict:
        """Build kwargs that satisfy Session.__init__."""
        project_state = MagicMock()
        project_state.library_state_container = container
        return {"project_state": project_state, "workspace_manager": MagicMock()}

    def test_create_session_attaches_to_container(self):
        container = LibraryStateContainer()
        manager = SessionManager(container=container)

        session = manager.create_session(**self._make_session_kwargs(container))

        assert session.session_id in container._known_session_ids

    def test_remove_session_detaches_from_container(self):
        container = LibraryStateContainer()
        manager = SessionManager(container=container)
        session = manager.create_session(**self._make_session_kwargs(container))

        manager.remove_session(session.session_id)

        assert session.session_id not in container._known_session_ids

    def test_session_state_class_visible_after_attach(self):
        """A SessionState registered before session creation gets an instance per session."""
        calls: list[str] = []

        class TimelineCursor(SessionState):
            def on_enable(self) -> None:
                calls.append(self.session_id)

        # Plant the SessionState class directly onto the container so we don't
        # need the registry plumbing for this unit test. (Integration test
        # exercises the registry path in Task 8.)
        container = LibraryStateContainer()
        container._sessions[TimelineCursor] = {}

        manager = SessionManager(container=container)
        session = manager.create_session(**self._make_session_kwargs(container))

        # on_enable fired for the new session.
        assert calls == [session.session_id]
        # Container has an instance for this session.
        assert TimelineCursor in container._sessions
        assert session.session_id in container._sessions[TimelineCursor]

    def test_remove_session_calls_on_disable(self):
        calls: list[str] = []

        class Cursor(SessionState):
            def on_disable(self) -> None:
                calls.append(self.session_id)

        container = LibraryStateContainer()
        container._sessions[Cursor] = {}
        manager = SessionManager(container=container)
        session = manager.create_session(**self._make_session_kwargs(container))

        manager.remove_session(session.session_id)
        assert calls == [session.session_id]
```

- [ ] **Step 2: Run the tests to verify they fail**

```
uv run pytest tests/core/test_state/test_session_manager_attach.py -v
```

Expected: FAIL — `SessionManager()` currently takes zero args, has no `container` parameter.

- [ ] **Step 3: Update `SessionManager.__init__` and `create_session` / `remove_session`**

Open `packages/haywire-core/src/haywire/ui/session_manager.py`. At the top, add to the imports:

```python
from haywire.core.state import LibraryStateContainer
```

Modify `__init__`:

```python
    def __init__(self, container: LibraryStateContainer):
        self._sessions: Dict[str, "Session"] = {}
        self._container = container
```

Modify `create_session`:

```python
    def create_session(self, **session_kwargs) -> "Session":
        """
        Create a new Session and register it.

        All keyword arguments are forwarded to the Session constructor.
        ``session_manager=self`` is injected automatically so callers do
        not pass it.

        After Session construction, the LibraryStateContainer is told to
        attach this session_id — every registered SessionState class gets
        a fresh instance for this session, with on_enable called.

        Returns:
            The newly created Session.
        """
        from haywire.ui.session import Session

        session = Session(session_manager=self, **session_kwargs)
        self._sessions[session.session_id] = session
        # Attach AFTER Session is fully constructed so SessionContext exists
        # and SessionDataNamespace can immediately resolve lookups.
        self._container.attach_session(session.session_id)
        logger.info(f"SessionManager: created session {session.session_id[:8]}")
        return session
```

Modify `remove_session`:

```python
    def remove_session(self, session_id: str) -> None:
        """
        Clean up and remove a session by ID.

        Order: session.cleanup() runs first (UI / editors / slots tear
        down), then container.detach_session() runs (SessionState
        on_disable fires, instances dropped). This way a panel/editor
        that reads ctx.data[X] during its own cleanup still sees the
        instance.

        Args:
            session_id: The full session ID string.
        """
        session = self._sessions.pop(session_id, None)
        if session is not None:
            try:
                session.cleanup()
            except Exception as e:
                logger.warning(f"SessionManager: error cleaning up session {session_id[:8]}: {e}")
        # Detach AFTER cleanup so on_disable can't observe a half-torn-down session.
        self._container.detach_session(session_id)
        if session is not None:
            logger.info(f"SessionManager: removed session {session_id[:8]}")
```

- [ ] **Step 4: Update `HaywireApp.setup_shared_services`**

Open `packages/haywire-studio/src/haywire_studio/app.py`. Find the `setup_shared_services` method (around line 120). The current order constructs `SessionManager()` (line 124) BEFORE `self.library_state_container` is set up (line 135). We need to reorder so the container exists first.

Replace the relevant block:

```python
    def setup_shared_services(self):
        """Setup services shared across all sessions."""
        from haywire.ui.session_manager import SessionManager

        self.session_manager = SessionManager()

        # Registries and factories (from DI)
        self.node_registry = self.library_service.get_node_registry()
        self.node_factory = self.library_service.get_node_factory()
        self.skin_factory = self.library_service.get_skin_factory()
        self.adapter_factory = self.library_service.get_adapter_factory()
        self.panel_registry = self.library_service.get_panel_registry()

        from haywire.core.state import LibraryStateContainer
        self.library_state_container = self.library_service.injector.get(LibraryStateContainer)
```

with:

```python
    def setup_shared_services(self):
        """Setup services shared across all sessions."""
        from haywire.core.state import LibraryStateContainer
        from haywire.ui.session_manager import SessionManager

        # Registries and factories (from DI)
        self.node_registry = self.library_service.get_node_registry()
        self.node_factory = self.library_service.get_node_factory()
        self.skin_factory = self.library_service.get_skin_factory()
        self.adapter_factory = self.library_service.get_adapter_factory()
        self.panel_registry = self.library_service.get_panel_registry()
        self.library_state_container = self.library_service.injector.get(LibraryStateContainer)

        # SessionManager needs the container to drive attach/detach.
        self.session_manager = SessionManager(container=self.library_state_container)
```

- [ ] **Step 5: Update other `SessionManager()` callers**

```bash
grep -rn "SessionManager()" packages/haywire-core/src/ packages/haywire-studio/src/ tests/
```

There are likely none left after fixing app.py, but if any test directly constructs `SessionManager()`, update to `SessionManager(container=LibraryStateContainer())` (a fresh empty container is fine for tests).

- [ ] **Step 6: Run new tests + studio + UI tests**

```
uv run pytest tests/core/test_state/test_session_manager_attach.py tests/studio/ tests/ui/ -v
```

Expected: all PASS.

- [ ] **Step 7: Run full unit suite**

```
uv run pytest -m "not integration"
```

Expected: 904+ passed.

- [ ] **Step 8: Lint + mypy**

```
uv run ruff check packages/haywire-core/src/haywire/ui/session_manager.py packages/haywire-studio/src/haywire_studio/app.py tests/
uv run mypy packages/haywire-core/src/haywire/ui/session_manager.py
```

Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/session_manager.py \
        packages/haywire-studio/src/haywire_studio/app.py \
        tests/core/test_state/test_session_manager_attach.py
git commit -m "feat(state): SessionManager drives container attach_session / detach_session

SessionManager.__init__ now takes a LibraryStateContainer. create_session
calls attach_session(session.session_id) AFTER Session construction so
SessionContext is fully built before on_enable hooks run on per-session
instances. remove_session calls detach_session AFTER session.cleanup()
so UI tears down first, SessionState second.

HaywireApp.setup_shared_services reordered so the container is resolved
before SessionManager is constructed.

See docs/documentation/architecture/session_state.md §3.5."
```

---

## Task 8: End-to-end integration test

**Files:**
- Test: `tests/core/test_state/test_session_state_integration.py` (new)

- [ ] **Step 1: Write the integration test**

Write to `tests/core/test_state/test_session_state_integration.py`:

```python
"""End-to-end: full LibrarySystemService + SessionManager + SessionState pipeline.

Verifies that registering a SessionState class through the registry's public
API path, attaching a session via SessionManager, and reading via
SessionDataNamespace all work end-to-end with the actual DI graph.
"""

import pytest
from unittest.mock import MagicMock

from haywire.core.di.config import LibrarySystemService, create_haywire_injector
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType,
)
from haywire.core.state import (
    LibraryStateContainer,
    LibraryStateRegistry,
    SessionState,
)
from haywire.core.state.data_namespace import SessionDataNamespace
from haywire.ui.session_manager import SessionManager


@pytest.mark.integration
class TestSessionStateIntegration:
    def test_register_then_attach_then_access_then_detach(self):
        """Full lifecycle: register class → attach session → on_enable → access → detach → on_disable."""
        injector = create_haywire_injector()
        service = LibrarySystemService(injector)
        service.initialize()

        registry = injector.get(LibraryStateRegistry)
        container = injector.get(LibraryStateContainer)

        calls: list[tuple[str, str]] = []

        class TimelineCursor(SessionState):
            position: float = 0.0

            def on_enable(self) -> None:
                calls.append(("enable", self.session_id))

            def on_disable(self) -> None:
                calls.append(("disable", self.session_id))

        # Build a minimal LibraryIdentity for this test "library".
        lib_id = LibraryIdentity(
            id="testlib", label="Test Library", version="0.0.1",
            description="", url="", help_url="", author="", author_url="",
            dependencies=[], tags=[], module_name="testlib", folder_path="",
        )

        # Register the class via the same path a real library would use.
        key = registry._register_class(TimelineCursor, lib_id)
        assert key is not None

        # Simulate the registry emitting CLASS_ADDED for the SessionState class.
        added_event = LifeCycleEvent(
            registry_key=key,
            event_type=LifeCycleEventType.CLASS_ADDED,
            affected_class=TimelineCursor,
            library_identity=lib_id,
        )
        registry._lifecycle_event_queue.append(added_event)
        registry._notify_batch_event_subscribers()

        # No sessions yet — no instances exist.
        assert calls == []

        # Construct a SessionManager wired to this container.
        manager = SessionManager(container=container)
        project_state = MagicMock()
        project_state.library_state_container = container
        session = manager.create_session(
            project_state=project_state,
            workspace_manager=MagicMock(),
        )

        # on_enable fired for this session.
        assert calls == [("enable", session.session_id)]

        # Access via SessionDataNamespace.
        ns = SessionDataNamespace(container, session.session_id)
        instance = ns[TimelineCursor]
        assert isinstance(instance, TimelineCursor)
        assert instance.session_id == session.session_id

        # Tear down — on_disable fires.
        manager.remove_session(session.session_id)
        assert ("disable", session.session_id) in calls
        # Container no longer has an instance for this session.
        assert ns.get(TimelineCursor) is None
```

- [ ] **Step 2: Run with the integration marker**

```
uv run pytest tests/core/test_state/test_session_state_integration.py -v -m integration
```

Expected: PASS.

- [ ] **Step 3: Run the entire test suite**

```
uv run pytest
```

Expected: full suite green (including all v1 integration tests + this new one).

- [ ] **Step 4: Commit**

```bash
git add tests/core/test_state/test_session_state_integration.py
git commit -m "test(state): end-to-end SessionState integration

Drives the full DI + LibrarySystemService + SessionManager pipeline:
registers a SessionState class through the registry, creates a session,
verifies on_enable fired with stamped session_id, accesses the instance
via SessionDataNamespace, removes the session, verifies on_disable
fired and the per-session bag dropped."
```

---

## Task 9: Run the full quality suite

- [ ] **Step 1: Lint**

```
uv run ruff check .
```

Expected: zero errors introduced by this branch. Pre-existing baseline errors in files this branch did not touch are not blockers (verify by `git log --oneline master..HEAD -- <file>` for each — empty output means we didn't touch it).

- [ ] **Step 2: Format check**

```
uv run ruff format --check .
```

Expected: all branch-touched files formatted. If anything reports drift in branch-touched files, fix with `uv run ruff format <files>` and commit.

- [ ] **Step 3: Mypy**

```
uv run mypy packages/haywire-core/src/
```

Expected: `Success: no issues found`.

- [ ] **Step 4: Full test suite with coverage**

```
uv run pytest --cov
```

Expected: all tests pass. Coverage on `haywire/core/state/` should remain ≥ 90% — every public method has a unit test plus the integration test.

- [ ] **Step 5: Smoke test the app**

```
perl -e 'alarm 15; exec @ARGV' uv run haywire 2>&1 | tail -50
```

Expected: app starts, library system initializes, NiceGUI starts on port 8082, no errors related to LibraryState or SessionState. Look for the registry status output and confirm no SessionState classes errored on registration.

- [ ] **Step 6: Sanity-check ExecutionContext changes did not break execution**

If a test exercising actual graph execution exists in the suite (e.g. integration tests for the Interpreter), confirm those passed in Step 4. Otherwise, verify by searching for any test that runs a flow:

```bash
grep -rn "interpreter.start_execution\|vm.run\|exec_ctx\.app_data" tests/ | head -10
```

If none, that's fine — execution was tested via the unit tests in Tasks 6 + 8.

---

## Task 10: Documentation updates

**Files:**
- Modify: `docs/documentation/architecture/library_state.md`
- Modify: `docs/documentation/architecture/session_state.md`

- [ ] **Step 1: Update `library_state.md` cross-references**

Open `docs/documentation/architecture/library_state.md`. Update the status block at the top:

Find:

```markdown
> Status: **v1 implemented (2026-05-06).** This document is the canonical
> reference for LibraryState. Phase 2 (observable container, reactive
> auto-tracking) remains pending — see spec_panel_reactivity.md.
```

Replace with:

```markdown
> Status: **v1 implemented (2026-05-06); v1.1 implemented (today's date).**
> v1.1 introduces `SessionState` as a sibling of `AppState` (the renamed
> concrete app-global base) under an abstract `LibraryState` marker. See
> [`session_state.md`](session_state.md) for the per-session scope and
> [`spec_panel_reactivity.md`](spec_panel_reactivity.md) for the deferred
> Phase 2 reactive auto-tracking.
```

Then walk the body of the doc and update wherever it says "subclass of `LibraryState`" or "`LibraryState` is the concrete base" — these now refer to `AppState`. Specifically:

- §1 Mental model — replace text describing LibraryState as concrete with text describing it as a marker; point at AppState as the concrete app-scoped base.
- §2.1 Declaration — change `class MidiPool(LibraryState):` → `class MidiPool(AppState):`.
- §2.3 Access — change `ctx.data[MidiPool]` → `ctx.app_data[MidiPool]`. Add a note that SessionState lookups use `ctx.data` per session_state.md.
- §3.1 Two-component split — note that the container now holds two scopes, link to session_state.md §3 for details.
- §6 Implementation surface — note that types listed are now siblings of SessionState; cross-link to session_state.md §6.

- [ ] **Step 2: Update `session_state.md` status header**

Open `docs/documentation/architecture/session_state.md`. Change the status block:

Find:

```markdown
> Status: **Speculative (v1.1).** Designed via inquisition on 2026-05-06.
```

Replace with:

```markdown
> Status: **v1.1 implemented (today's date).** This document is the canonical
> reference for SessionState. v1.2 (framework EditState migration) is a
> separate plan/spec — see Open Questions §9.
```

Use today's actual date (replace "today's date" with the value from `date +%Y-%m-%d`).

- [ ] **Step 3: Verify cross-references resolve**

```bash
grep -rn "session_state\.md\|library_state\.md" docs/ packages/ tests/ --include="*.md" --include="*.py" | grep -v "spec_library_state\|spec_session_state"
```

Confirm every reference points at a file that exists. No broken links.

- [ ] **Step 4: Commit**

```bash
git add docs/documentation/architecture/library_state.md \
        docs/documentation/architecture/session_state.md
git commit -m "docs(state): mark SessionState v1.1 implemented; update library_state cross-refs

library_state.md now reflects the new taxonomy: LibraryState as
abstract marker, AppState as concrete app-global base, with prose and
code examples updated. session_state.md status moves from speculative
to v1.1 implemented.

v1.2 (framework EditState migration) remains a separate follow-up."
```

---

## Self-review checklist (already applied)

- [x] **Spec coverage**:
  - §2.1 Declaration → Task 2 (SessionState base + LibrarySettings prohibition).
  - §2.2 Registration → Task 1 (filter exclusion adds AppState) + Task 2 (filter exclusion adds SessionState). No new registration path; reuses v1 machinery.
  - §2.3 Access (two namespaces) → Task 4 (namespace classes) + Task 5 (SessionContext) + Task 6 (ExecutionContext).
  - §2.4 Type-checking → Task 4 (TypeVar bounds tightened on each namespace).
  - §3.1 Container two-scope storage → Task 3.
  - §3.2 Eager instantiation → Task 3 (`_add_session_class` + `attach_session` both fanout).
  - §3.3 Detach → Task 3 (`detach_session`) + Task 7 (called from `remove_session`).
  - §3.4 Hot-reload → Task 3 (`_reload` dispatches by scope; SessionState path fans out).
  - §3.5 Construction order → Task 7 (attach after Session(); detach after cleanup()).
  - §4 Reactivity → unchanged from v1; no new code (mentioned in spec).
  - §5.1 Boundary table → covered by Task 10 docs.
  - §5.2 LibrarySettings prohibition → Task 2 (`__init_subclass__` check + tests).
  - §6.1 New types → Tasks 2 (SessionState), 4 (SessionDataNamespace).
  - §6.2 Changes to existing types → Tasks 1 (LibraryState marker, AppState concrete), 3 (container), 4 (DataNamespace → AppDataNamespace), 5 (SessionContext), 6 (ExecutionContext + VM), 7 (SessionManager + HaywireApp).
  - §6.3 Breaking changes → all internal-only; covered atomically across Tasks 1–7.
  - §7 Examples → docs only; covered by Task 10.
  - §8.1 v1.1 ships → covered by Tasks 1–9.
  - §8.2 v1.2 deferred → mentioned in spec and in commit messages; not in this plan.

- [x] **Placeholder scan**: every step has concrete code or commands. No "TBD" / "similar to Task N" / "implement appropriate error handling" / "add validation".

- [x] **Type consistency**: `LibraryState` (abstract marker), `AppState` (concrete app), `SessionState` (concrete session), `LibraryStateRegistry`, `LibraryStateContainer`, `AppDataNamespace`, `SessionDataNamespace`, `LibraryStateClassIdentity` — names match across all tasks. Method names: `attach_session`, `detach_session`, `get_session`, `get_session_optional`, `has_session`, `_add_session_class`, `_remove_session_class`, `_instantiate_session_state` — consistent throughout. Hooks: `on_enable`/`on_disable` (no aliases). `self.session_id` stamped between `cls()` and `on_enable` — consistent in container code and tests.
