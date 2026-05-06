# Panel Contract Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate PropertiesEditor and its 16 panels from the legacy string-keyed `BasePanel` system to the new contract-centric `Panel` system, introducing the `Reactive[T]` primitive and descriptor-based `SessionContext` along the way.

**Architecture:** Bottom-up. Build the `Reactive[T]` primitive and descriptor pattern. Rewrite `SessionContext` as a single breaking change with descriptor-based reactive fields. Add a new `Panel` base class and contract-centric `@panel` decorator alongside the legacy ones. Add registry methods for class-keyed lookup. Rewrite PropertiesEditor's toolbar to discover focuses via the registry. Migrate 16 panels one at a time. No reactive Subscriptions, no auto-tracking, no `@reads` enforcement — those are Phase 2.

**Tech Stack:** Python 3.12+, NiceGUI, pytest, mypy, ruff. The codebase uses `uv` for package management.

**Reference specs:**
- [`docs/speculative/spec_panel_contract.md`](../../speculative/archive/spec_panel_contract.md) — destination contract (the `Panel` base class, `@panel` decorator surface, action Protocol, focus system, layout, lifecycle).
- [`docs/speculative/spec_panel_reactivity.md`](../../speculative/spec_panel_reactivity.md) — Phase 2 mechanism (out of scope here).
- [`docs/speculative/spec_panel_migration.md`](../../speculative/archive/spec_panel_migration.md) — full inventory of legacy panels (Phase 1 covers a subset).

**Phase 1 scope (locked via inquisition 2026-05-03):**
- 16 panels migrated: 12 PropertiesEditor-only panels in `barn/haybale-core` + 4 in `barn/haybale-studio`.
- `EdgeErrorsPanel` and `EdgeWarningsPanel` (dual-host) **stay on `BasePanel`** in Phase 1; Phase 1.5 handles them via the shared Protocol pattern.
- All 14 context-menu panels stay on `BasePanel`.
- Legacy `BasePanel`, `register_scope`, `ScopeDescriptor` remain in the codebase. Cleanup is Phase 1.5.

**Out of scope:**
- Reactivity (`Subscription`, auto-tracking, `@reads` verification) — Phase 2.
- Context-menu panels and the `ContextMenuActions` Protocol — Phase 1.5.
- Final cleanup of legacy framework code — Phase 1.5.
- Hot-reload edge cases beyond what already works.

---

## File Structure

### New files
- `packages/haywire-core/src/haywire/ui/reactive/__init__.py` — package exports
- `packages/haywire-core/src/haywire/ui/reactive/reactive.py` — `Reactive[T]` primitive (no tracking yet)
- `packages/haywire-core/src/haywire/ui/reactive/descriptor.py` — `reactive_field()` factory + descriptor
- `packages/haywire-core/src/haywire/ui/reactive/path.py` — `ReactivePath` dataclass (skeleton; consumed in Phase 2)
- `packages/haywire-core/src/haywire/ui/panel/panel.py` — new `Panel` base class
- `packages/haywire-core/src/haywire/ui/panel/focus.py` — `Focus` base class with `id` ClassVar
- `tests/ui/reactive/test_reactive_value.py` — primitive tests
- `tests/ui/reactive/test_reactive_descriptor.py` — descriptor behavior tests
- `tests/ui/panel/test_panel_decorator.py` — decorator validation tests
- `tests/ui/panel/test_panel_registry_class_keyed.py` — class-keyed lookup tests
- `tests/ui/panel/test_focus.py` — Focus base + id auto-discovery tests
- `tests/ui/properties_editor/test_toolbar_discovery.py` — toolbar from default_focuses ∪ registry
- `tests/ui/properties_editor/test_panel_mounting.py` — panel mount per focus

### Modified files
- `packages/haywire-core/src/haywire/ui/context.py` — SessionContext rewritten with descriptor-based reactive fields (breaking change)
- `packages/haywire-core/src/haywire/ui/panel/decorator.py` — `@panel` accepts `action=` and validates
- `packages/haywire-core/src/haywire/ui/panel/registry.py` — adds `get_panels_for(actions_provider, focus)` and `get_focuses_for(actions_provider)`; tracks focus classes
- `packages/haywire-core/src/haywire/ui/panel/identity.py` — adds `action: type | None`, `focus: type[Focus] | None` fields
- `packages/haywire-core/src/haywire/ui/panel/__init__.py` — exports `Panel`, `Focus`
- `packages/haywire-core/src/haywire/ui/reactive/` — directory created (none today)
- `barn/haybale-studio/haybale_studio/editors/properties_editor.py` — toolbar rewrite, registry queries via new methods, action Protocol satisfaction
- `barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py` — Protocol stays as-is (one method); expand per-panel-migration
- `barn/haybale-core/haybale_core/focuses.py` — add `id` ClassVar to existing focuses
- `barn/haybale-studio/haybale_studio/focuses.py` — add `id` ClassVar to existing focuses
- 12 panel files in `barn/haybale-core/haybale_core/panels/` — migrate to new contract
- 4 panel files in `barn/haybale-studio/haybale_studio/panels/` — migrate to new contract
- All call sites that read/write SessionContext fields (~26 across packages and barn) — switch to `.value` form

### Deleted files
None in Phase 1. `BasePanel`, `ScopeDescriptor`, `register_scope` survive.

---

## Tracks

The plan groups tasks into four tracks. Each track is independently committable.

- **Track P (Primitives):** Tasks 1–4. `Reactive[T]` + descriptor + path. Foundation.
- **Track S (SessionContext):** Tasks 5–7. Rewrite SessionContext; update every reader/writer.
- **Track F (Framework):** Tasks 8–14. New `Panel` class, `Focus` base, decorator updates, registry additions.
- **Track E (Editor + panels):** Tasks 15–16. PropertiesEditor toolbar rewrite + 16 panel migrations.

Tracks P, F can be developed in parallel after Track S lands. Track E depends on F.

---

## Track P — Reactive Primitives

### Task 1: Reactive[T] value primitive (no tracking)

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/reactive/__init__.py`
- Create: `packages/haywire-core/src/haywire/ui/reactive/reactive.py`
- Test: `tests/ui/reactive/test_reactive_value.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/reactive/test_reactive_value.py
"""Phase 1: Reactive[T] is a value holder. No tracking yet."""
import pytest
from haywire.ui.reactive import Reactive


def test_reactive_holds_initial_value():
    r: Reactive[int] = Reactive(42)
    assert r.value == 42


def test_reactive_value_setter_updates():
    r: Reactive[int] = Reactive(0)
    r.value = 7
    assert r.value == 7


def test_reactive_equal_write_is_noop():
    """Writing the same value twice should not change anything."""
    r: Reactive[int] = Reactive(5)
    r.value = 5  # same value
    assert r.value == 5  # unchanged


def test_reactive_handles_none_initial():
    r: Reactive[int | None] = Reactive(None)
    assert r.value is None
    r.value = 3
    assert r.value == 3


def test_reactive_repr_includes_value():
    r: Reactive[str] = Reactive("hello")
    assert "hello" in repr(r)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/reactive/test_reactive_value.py -v`
Expected: FAIL — `from haywire.ui.reactive import Reactive` raises ImportError.

- [ ] **Step 3: Create the package init and Reactive primitive**

```python
# packages/haywire-core/src/haywire/ui/reactive/__init__.py
"""Reactive primitives for Haywire UI.

Phase 1 ships only the value-holder. Subscription, auto-tracking, and
@reads verification are Phase 2.
"""

from haywire.ui.reactive.reactive import Reactive

__all__ = ["Reactive"]
```

```python
# packages/haywire-core/src/haywire/ui/reactive/reactive.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/reactive/test_reactive_value.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run full quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/reactive/ tests/ui/reactive/`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/reactive/ tests/ui/reactive/`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/reactive/`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/reactive/__init__.py \
        packages/haywire-core/src/haywire/ui/reactive/reactive.py \
        tests/ui/reactive/test_reactive_value.py
git commit -m "feat(reactive): add Reactive[T] value holder primitive"
```

---

### Task 2: ReactivePath skeleton

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/reactive/path.py`
- Modify: `packages/haywire-core/src/haywire/ui/reactive/__init__.py`
- Test: `tests/ui/reactive/test_reactive_path.py`

ReactivePath is the typed reference returned by class-level access to a reactive field. Phase 1 ships the dataclass so that `@reads(...)` decorators in panels can be authored against it; Phase 2 wires it up to Subscriptions.

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/reactive/test_reactive_path.py
"""ReactivePath identifies one reactive field on a class. Phase 1: data only."""
from haywire.ui.reactive import ReactivePath


def test_reactive_path_identity():
    class Owner:
        pass

    p1 = ReactivePath(owner=Owner, attr="x")
    p2 = ReactivePath(owner=Owner, attr="x")
    assert p1 == p2
    assert hash(p1) == hash(p2)


def test_reactive_path_repr():
    class SomeContext:
        pass

    p = ReactivePath(owner=SomeContext, attr="active_node")
    assert "SomeContext" in repr(p)
    assert "active_node" in repr(p)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/reactive/test_reactive_path.py -v`
Expected: FAIL — ImportError for ReactivePath.

- [ ] **Step 3: Create ReactivePath**

```python
# packages/haywire-core/src/haywire/ui/reactive/path.py
"""ReactivePath: a typed reference to a reactive field on a class.

Phase 1: data class only. Class-level attribute access on a SessionContext
that uses `reactive_field()` returns one of these. Phase 2's `@reads`
decorator records these as method metadata for drift verification.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReactivePath:
    """Identifies a single reactive field on a class.

    `owner` is the class that defines the field. `attr` is the attribute
    name. Two ReactivePaths with the same (owner, attr) compare equal and
    hash equal, so they can be used as dict keys.
    """

    owner: type
    attr: str

    def __repr__(self) -> str:
        return f"{self.owner.__name__}.{self.attr}"
```

- [ ] **Step 4: Update package init**

Replace the contents of `packages/haywire-core/src/haywire/ui/reactive/__init__.py`:

```python
# packages/haywire-core/src/haywire/ui/reactive/__init__.py
"""Reactive primitives for Haywire UI.

Phase 1 ships only the value-holder and ReactivePath skeleton.
Subscription, auto-tracking, and @reads verification are Phase 2.
"""

from haywire.ui.reactive.path import ReactivePath
from haywire.ui.reactive.reactive import Reactive

__all__ = ["Reactive", "ReactivePath"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/reactive/ -v`
Expected: all tests pass (Task 1 + Task 2 tests).

- [ ] **Step 6: Run quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/reactive/ tests/ui/reactive/`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/reactive/ tests/ui/reactive/`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/reactive/`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/reactive/path.py \
        packages/haywire-core/src/haywire/ui/reactive/__init__.py \
        tests/ui/reactive/test_reactive_path.py
git commit -m "feat(reactive): add ReactivePath dataclass skeleton"
```

---

### Task 3: reactive_field() descriptor

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/reactive/descriptor.py`
- Modify: `packages/haywire-core/src/haywire/ui/reactive/__init__.py`
- Test: `tests/ui/reactive/test_reactive_descriptor.py`

The descriptor is what makes `Class.field` return a `ReactivePath` while `instance.field` returns the `Reactive[T]` container. This is the load-bearing piece for SessionContext.

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/reactive/test_reactive_descriptor.py
"""reactive_field() — class access yields ReactivePath; instance access yields Reactive[T]."""
from haywire.ui.reactive import Reactive, ReactivePath, reactive_field


class _ExampleContext:
    """Test-only context class. Defined inside test module to avoid leakage."""

    counter: Reactive[int] = reactive_field(0)
    name: Reactive[str] = reactive_field("anon")

    def __init__(self) -> None:
        # Trigger descriptor's per-instance initialization.
        # Mirrors what SessionContext will do in __post_init__.
        for descriptor_name in dir(type(self)):
            attr = getattr(type(self), descriptor_name, None)
            if hasattr(attr, "_initial"):
                self.__dict__[descriptor_name] = Reactive(attr._initial)


def test_class_access_returns_reactive_path():
    p = _ExampleContext.counter
    assert isinstance(p, ReactivePath)
    assert p.owner is _ExampleContext
    assert p.attr == "counter"


def test_instance_access_returns_reactive_container():
    ctx = _ExampleContext()
    assert isinstance(ctx.counter, Reactive)
    assert ctx.counter.value == 0


def test_instance_value_is_independent_per_instance():
    a = _ExampleContext()
    b = _ExampleContext()
    a.counter.value = 5
    assert a.counter.value == 5
    assert b.counter.value == 0


def test_class_access_for_different_attr():
    p = _ExampleContext.name
    assert p.attr == "name"
    assert p.owner is _ExampleContext


def test_two_classes_descriptor_ownership_is_correct():
    class Other:
        flag: Reactive[bool] = reactive_field(False)

    p_self = _ExampleContext.counter
    p_other = Other.flag
    assert p_self.owner is _ExampleContext
    assert p_other.owner is Other
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/reactive/test_reactive_descriptor.py -v`
Expected: FAIL — ImportError for `reactive_field`.

- [ ] **Step 3: Implement the descriptor**

```python
# packages/haywire-core/src/haywire/ui/reactive/descriptor.py
"""reactive_field(): a descriptor whose access mode determines its return type.

- Class-level access (e.g., SessionContext.active_node) → ReactivePath.
- Instance-level access (e.g., ctx.active_node) → Reactive[T] container.

The class hosting reactive_field() descriptors is responsible for
initializing the per-instance Reactive[T] containers in __init__ /
__post_init__. This module exposes `iter_reactive_fields(cls)` for that
purpose.
"""

from __future__ import annotations

from typing import Any, Generic, Iterator, TypeVar

from haywire.ui.reactive.path import ReactivePath
from haywire.ui.reactive.reactive import Reactive

T = TypeVar("T")


class _ReactiveDescriptor(Generic[T]):
    """Internal descriptor returned by reactive_field()."""

    def __init__(self, initial: T) -> None:
        self._initial: T = initial
        self._attr_name: str | None = None  # populated by __set_name__

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            assert self._attr_name is not None, "descriptor missing __set_name__"
            return ReactivePath(owner=owner, attr=self._attr_name)
        # Instance access — return the per-instance Reactive[T] container.
        # Hosting class is responsible for populating instance.__dict__[attr_name].
        assert self._attr_name is not None
        return instance.__dict__[self._attr_name]


def reactive_field(initial: T) -> Reactive[T]:
    """Declare a reactive field on a class.

    Usage:
        class SessionContext:
            active_node: Reactive[NodeWrapper | None] = reactive_field(None)

    The annotation type (`Reactive[T]`) describes instance-level access.
    Class-level access (`SessionContext.active_node`) returns a
    ReactivePath instead — the descriptor handles the dispatch.

    The hosting class must initialize per-instance Reactive[T] containers,
    typically by iterating `iter_reactive_fields(cls)` in __init__ or
    __post_init__.
    """
    # Lie to mypy: the annotation is what panels see (Reactive[T]).
    # The runtime returns a descriptor.
    return _ReactiveDescriptor(initial)  # type: ignore[return-value]


def iter_reactive_fields(cls: type) -> Iterator[tuple[str, Any]]:
    """Yield (attr_name, initial_value) for each reactive_field() on cls.

    Used by hosting classes to initialize per-instance Reactive[T]
    containers.
    """
    for name in dir(cls):
        attr = getattr(cls, name, None)
        # ReactivePath is what class-access returns; we need the descriptor itself.
        # Walk the MRO and inspect __dict__ entries directly to find descriptors.
        pass

    for klass in cls.__mro__:
        for name, attr in klass.__dict__.items():
            if isinstance(attr, _ReactiveDescriptor):
                yield name, attr._initial
```

- [ ] **Step 4: Update the package init**

Replace `packages/haywire-core/src/haywire/ui/reactive/__init__.py`:

```python
# packages/haywire-core/src/haywire/ui/reactive/__init__.py
"""Reactive primitives for Haywire UI.

Phase 1 ships:
- Reactive[T]: a value-holder primitive.
- ReactivePath: a typed reference to a reactive field (class identity).
- reactive_field(): descriptor declaring a reactive field on a class.
- iter_reactive_fields(): helper for hosting classes to initialize
  per-instance Reactive[T] containers.

Phase 2 will add Subscription, auto-tracking, and @reads verification.
"""

from haywire.ui.reactive.descriptor import iter_reactive_fields, reactive_field
from haywire.ui.reactive.path import ReactivePath
from haywire.ui.reactive.reactive import Reactive

__all__ = ["Reactive", "ReactivePath", "reactive_field", "iter_reactive_fields"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/reactive/ -v`
Expected: all 12 tests pass.

- [ ] **Step 6: Run quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/reactive/ tests/ui/reactive/`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/reactive/ tests/ui/reactive/`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/reactive/`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/reactive/descriptor.py \
        packages/haywire-core/src/haywire/ui/reactive/__init__.py \
        tests/ui/reactive/test_reactive_descriptor.py
git commit -m "feat(reactive): add reactive_field() descriptor for SessionContext"
```

---

### Task 4: iter_reactive_fields helper test

**Files:**
- Test: `tests/ui/reactive/test_iter_reactive_fields.py`

Validate the helper that hosting classes (like SessionContext) will use to initialize their per-instance Reactives.

- [ ] **Step 1: Write the test**

```python
# tests/ui/reactive/test_iter_reactive_fields.py
"""iter_reactive_fields walks a class's MRO and yields (name, initial) per descriptor."""
from haywire.ui.reactive import Reactive, iter_reactive_fields, reactive_field


def test_iter_yields_each_descriptor():
    class C:
        x: Reactive[int] = reactive_field(1)
        y: Reactive[str] = reactive_field("hi")
        not_reactive = 99

    pairs = dict(iter_reactive_fields(C))
    assert pairs == {"x": 1, "y": "hi"}


def test_iter_includes_inherited_fields():
    class Base:
        a: Reactive[int] = reactive_field(0)

    class Sub(Base):
        b: Reactive[bool] = reactive_field(True)

    pairs = dict(iter_reactive_fields(Sub))
    assert pairs == {"a": 0, "b": True}


def test_iter_skips_non_reactive_attrs():
    class C:
        method_attr: Reactive[int] = reactive_field(7)

        def some_method(self) -> None:
            pass

    pairs = dict(iter_reactive_fields(C))
    assert pairs == {"method_attr": 7}
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/ui/reactive/test_iter_reactive_fields.py -v`
Expected: 3 passed (the helper exists from Task 3).

- [ ] **Step 3: Run quality suite**

Run: `uv run ruff check tests/ui/reactive/`
Run: `uv run ruff format tests/ui/reactive/`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add tests/ui/reactive/test_iter_reactive_fields.py
git commit -m "test(reactive): cover iter_reactive_fields helper"
```

---

## Track S — SessionContext Rewrite

This track is a single breaking change. Once SessionContext fields become reactive, every reader and writer must use `.value`. There are roughly 26 call sites across the codebase. The rewrite happens in one logical commit; we test green before and after.

### Task 5: Rewrite SessionContext with descriptor-based reactive fields

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/context.py`
- Test: `tests/ui/test_session_context_reactive.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_session_context_reactive.py
"""SessionContext fields are reactive: class access yields ReactivePath, instance access yields Reactive[T]."""
from unittest.mock import MagicMock

import pytest

from haywire.ui.context import SessionContext
from haywire.ui.reactive import Reactive, ReactivePath


def _make_ctx() -> SessionContext:
    """Build a SessionContext with mock dependencies."""
    return SessionContext(session_id="test", app=MagicMock())


def test_active_node_class_access_is_reactive_path():
    p = SessionContext.active_node
    assert isinstance(p, ReactivePath)
    assert p.owner is SessionContext
    assert p.attr == "active_node"


def test_active_node_instance_access_is_reactive():
    ctx = _make_ctx()
    assert isinstance(ctx.active_node, Reactive)
    assert ctx.active_node.value is None


def test_active_node_write_through_value():
    ctx = _make_ctx()
    sentinel = MagicMock(name="node_wrapper")
    ctx.active_node.value = sentinel
    assert ctx.active_node.value is sentinel


def test_each_instance_has_independent_reactives():
    a = _make_ctx()
    b = _make_ctx()
    a.active_node.value = MagicMock()
    assert a.active_node.value is not None
    assert b.active_node.value is None


def test_all_documented_reactive_fields_are_present():
    ctx = _make_ctx()
    expected_fields = {
        "active_graph",
        "active_node",
        "active_edge",
        "active_port",
        "selected_nodes",
        "selected_edges",
        "workspace_name",
        "active_library",
        "active_component",
        "active_file",
        "active_graph_path",
        "active_workbench_theme_key",
        "active_node_theme_key",
        "context_menu_trigger",
    }
    for name in expected_fields:
        attr = getattr(ctx, name)
        assert isinstance(attr, Reactive), f"{name} is not Reactive: {type(attr)}"


def test_metadata_is_still_a_plain_dict():
    """metadata stays as a dict for now (Phase 1.5 lifts gesture state to typed fields)."""
    ctx = _make_ctx()
    assert isinstance(ctx.metadata, dict)
    ctx.metadata["k"] = "v"
    assert ctx.metadata["k"] == "v"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/ui/test_session_context_reactive.py -v`
Expected: FAIL — `SessionContext.active_node` is currently a plain attribute.

- [ ] **Step 3: Rewrite SessionContext**

Replace the contents of `packages/haywire-core/src/haywire/ui/context.py`:

```python
# packages/haywire-core/src/haywire/ui/context.py
"""
Session context for the Haywire UI system.

SessionContext is the central state object that flows through the entire UI hierarchy.
Each browser session has its own instance. Analogous to Blender's bContext.

Phase 1 reactive shape: every selection/active-* field is a `Reactive[T]`
declared via `reactive_field()`. Class-level access yields a `ReactivePath`;
instance-level access yields the `Reactive[T]` container. Read values via
`.value`; write values via `.value = ...`. Phase 2 layers Subscriptions
and auto-tracking on top — no read-site changes required for Phase 2.

The `metadata` dict remains a plain dict in Phase 1; Phase 1.5 lifts
context-menu gesture state to typed fields on the host (see
spec_panel_migration.md §4).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, TYPE_CHECKING

from haywire.ui.reactive import Reactive, iter_reactive_fields, reactive_field

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.graph.base import BaseGraph
    from haywire.core.library.base import BaseLibrary
    from haywire.core.node.base import DataPort
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.ui.protocols import IProjectState
    from haywire.ui.session import Session


class SessionContext:
    """
    Per-session context carrying current UI state.

    Reactive fields are accessed as `ctx.<field>.value` (read) or
    `ctx.<field>.value = ...` (write). Plain fields (`session_id`,
    `app`, `session`, `metadata`) are non-reactive.
    """

    # --- Plain fields (non-reactive) ---
    session_id: str
    app: "IProjectState"
    session: "Session"  # set by Session.__init__ immediately after construction
    metadata: Dict[str, Any]

    # --- Reactive fields ---
    active_graph: Reactive[Optional["BaseGraph"]] = reactive_field(None)
    active_node: Reactive[Optional["NodeWrapper"]] = reactive_field(None)
    active_edge: Reactive[Optional["EdgeWrapper"]] = reactive_field(None)
    active_port: Reactive[Optional["DataPort"]] = reactive_field(None)
    selected_nodes: Reactive[Set[str]] = reactive_field(set())
    selected_edges: Reactive[Set[str]] = reactive_field(set())
    workspace_name: Reactive[str] = reactive_field("default")
    active_library: Reactive[Optional["BaseLibrary"]] = reactive_field(None)
    active_component: Reactive[Optional[str]] = reactive_field(None)
    active_file: Reactive[Optional[Any]] = reactive_field(None)
    active_graph_path: Reactive[Optional[Any]] = reactive_field(None)
    active_workbench_theme_key: Reactive[Optional[str]] = reactive_field(None)
    active_node_theme_key: Reactive[Optional[str]] = reactive_field(None)
    context_menu_trigger: Reactive[Optional[str]] = reactive_field(None)

    def __init__(self, session_id: str, app: "IProjectState") -> None:
        self.session_id = session_id
        self.app = app
        self.metadata = {}
        # Initialize per-instance Reactive[T] containers for every
        # descriptor on this class. Default values come from
        # reactive_field(initial) declarations above. Mutable defaults
        # (e.g., set()) are deep-copied per-instance to avoid sharing.
        from copy import copy

        for name, initial in iter_reactive_fields(type(self)):
            self.__dict__[name] = Reactive(copy(initial))
        # `session` is set by Session.__init__ after this constructor returns.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/ui/test_session_context_reactive.py -v`
Expected: 6 passed.

- [ ] **Step 5: Run the broader test suite — expect MANY failures**

Run: `uv run pytest tests/ -x 2>&1 | tail -50`
Expected: FAILS in many places — every reader/writer of plain attributes is now broken. This is the moment to do the cleanup pass before committing.

Read the failure summary; identify all failing call sites. Each one needs one of:
- Read: `ctx.active_node` → `ctx.active_node.value`
- Write: `ctx.active_node = X` → `ctx.active_node.value = X`

Most of these are mechanical. A few are at unit-test boundaries that may need fixture updates.

- [ ] **Step 6: Commit the SessionContext rewrite as a checkpoint**

```bash
git add packages/haywire-core/src/haywire/ui/context.py \
        tests/ui/test_session_context_reactive.py
git commit -m "feat(context): rewrite SessionContext with descriptor-based reactive fields

BREAKING: every read/write of a SessionContext field now goes through
.value. Subsequent commits update all call sites.

Phase 1 of the panel-contract migration. See
docs/superpowers/plans/2026-05-03-panel-contract-phase-1.md."
```

---

### Task 6: Update all SessionContext readers and writers

This is the breaking-change cleanup. The previous task left the codebase failing; this task makes it green again.

**Files (illustrative — actual list discovered by failure output):**
- Modify: `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py` (sets `_context.active_node`, `_context.active_edge`, `_context.active_port`, etc.)
- Modify: every panel currently reading `context.active_node` / `context.active_edge` / etc.
- Modify: tests that build SessionContext fixtures or assert on its fields.

The list is bounded by the 26 call sites grep found earlier. Approach: run tests, fix one file at a time, re-run, until green.

- [ ] **Step 1: Inventory every failure site**

Run: `uv run pytest tests/ -x --tb=line 2>&1 | grep "AttributeError\|TypeError" | head -40`
Read the output. Make a list of files to fix.

Run: `grep -rn "\.active_node\|\.active_edge\|\.active_graph\|\.active_port\|\.selected_nodes\|\.selected_edges\|\.workspace_name\|\.active_library\|\.active_component\|\.active_file\|\.active_graph_path\|\.active_workbench_theme_key\|\.active_node_theme_key\|\.context_menu_trigger" --include="*.py" packages barn tests | grep -v "\.value" | grep -v "\.__" | head -50`
This shows non-`.value` accesses on those fields. Each may need updating. Filter out matches that are clearly not SessionContext (e.g., method definitions on other classes).

- [ ] **Step 2: Update each file**

For each file in the inventory:
- **Reads** like `ctx.active_node` become `ctx.active_node.value`.
- **Writes** like `ctx.active_node = X` become `ctx.active_node.value = X`.
- **Truthiness checks** like `if ctx.active_node:` become `if ctx.active_node.value is not None:` (preserved meaning; `if ctx.active_node:` would test the Reactive container's truthiness which is always True).

Example: `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`:

```python
# Before:
if self._context.active_graph is not None:
    wrapper = self._context.active_graph.get_node_wrapper(node_id)
    if wrapper is not None:
        self._context.active_node = wrapper

# After:
graph = self._context.active_graph.value
if graph is not None:
    wrapper = graph.get_node_wrapper(node_id)
    if wrapper is not None:
        self._context.active_node.value = wrapper
```

Don't try to be clever — keep the structure of each call site, just change the access.

- [ ] **Step 3: Run tests after each file**

Run: `uv run pytest tests/ -x --tb=short 2>&1 | tail -20`
Iterate: pick the first failure, fix the file, re-run.

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest tests/ -v 2>&1 | tail -30`
Expected: full green.

- [ ] **Step 5: Run the full quality suite**

Run: `uv run ruff check .`
Run: `uv run ruff format .`
Run: `uv run mypy packages/haywire-core/src/`
Expected: clean.

- [ ] **Step 6: Smoke-test the app**

Run: `uv run haywire` (in another terminal). Open the browser. Click a node. Click an edge. Open Properties. Verify nothing crashes. Close.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: update all SessionContext readers/writers for reactive fields

Mechanical migration: ctx.active_node → ctx.active_node.value
across packages, barn, and tests. Truthiness checks updated to
explicit is-not-None comparisons.

Phase 1 of the panel-contract migration."
```

---

### Task 7: Verify SessionContext rewrite complete

**Files:**
- None modified. Verification only.

- [ ] **Step 1: Confirm no plain-attribute reads remain**

Run: `grep -rn "ctx\.active_node[^.]" --include="*.py" packages barn tests | grep -v "\.value"`
Expected: empty output (every access goes through `.value`).

Repeat for the other reactive fields if you want to be thorough.

- [ ] **Step 2: Run the full test suite under coverage**

Run: `uv run pytest tests/ --cov=haywire.ui --cov-report=term-missing 2>&1 | tail -20`
Expected: green; SessionContext code coverage at or above prior level.

- [ ] **Step 3: Run integration tests**

Run: `uv run pytest tests/ -m integration -v 2>&1 | tail -10`
Expected: green.

- [ ] **Step 4: No commit needed — verification only**

If anything failed, return to Task 6 and fix.

---

## Track F — Framework

Track F is independent of Track S after Task 5. It can be started in parallel by another contributor or sequenced after S.

### Task 8: Focus base class with id ClassVar

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/panel/focus.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/__init__.py`
- Test: `tests/ui/panel/test_focus.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/panel/test_focus.py
"""Focus base class: classmethod available(); id ClassVar; auto-discovery map."""
import pytest

from haywire.ui.panel.focus import Focus, focus_by_id


def test_focus_subclass_must_define_id():
    """A Focus subclass without id should fail validation."""

    class _MissingId(Focus):
        label = "x"
        icon = "x"

        @classmethod
        def available(cls, ctx):
            return True

    # Without id, focus_by_id() should not find it (and it shouldn't crash).
    # Strict validation can be added later; for now just assert lookup works
    # for properly-declared focuses and not for misdeclared ones.
    assert focus_by_id("x") is None  # nothing named "x" registered properly


def test_focus_subclass_with_id_is_discoverable():
    class _MyFocus(Focus):
        id = "my_test_focus_unique_id"
        label = "My"
        icon = "icon"

        @classmethod
        def available(cls, ctx):
            return True

    assert focus_by_id("my_test_focus_unique_id") is _MyFocus


def test_focus_id_collision_raises():
    """Two Focus subclasses with the same id raise at class definition."""

    class _A(Focus):
        id = "duplicate_id_for_collision_test"
        label = "A"
        icon = "i"

        @classmethod
        def available(cls, ctx):
            return True

    with pytest.raises(ValueError, match="duplicate"):

        class _B(Focus):
            id = "duplicate_id_for_collision_test"
            label = "B"
            icon = "i"

            @classmethod
            def available(cls, ctx):
                return True


def test_focus_class_attributes_are_documented():
    """Focus subclasses declare label, icon, order, id."""

    class _Demo(Focus):
        id = "demo_focus_id"
        label = "Demo"
        icon = "star"
        order = 50

        @classmethod
        def available(cls, ctx):
            return True

    assert _Demo.label == "Demo"
    assert _Demo.icon == "star"
    assert _Demo.order == 50
    assert _Demo.id == "demo_focus_id"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/panel/test_focus.py -v`
Expected: FAIL — `from haywire.ui.panel.focus import Focus` doesn't exist.

- [ ] **Step 3: Implement Focus base + auto-discovery map**

```python
# packages/haywire-core/src/haywire/ui/panel/focus.py
"""Focus: a class hierarchy that discriminates which Panels apply to current state.

Each Focus subclass declares:
  - id: ClassVar[str]   — short stable identifier (used by DOM attributes
                          for context-menu triggers and by registry lookup).
  - label: ClassVar[str] — human-readable, used in toolbar chrome.
  - icon: ClassVar[str]  — Material Symbols icon name.
  - order: ClassVar[int] — sort priority in toolbars (lower = earlier).
  - available(cls, ctx) -> bool — classmethod returning whether this focus
                                  is reachable given current state.

The framework auto-builds an id → class map at class-definition time via
__init_subclass__. Collisions raise ValueError immediately.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

# id → Focus subclass map. Populated by Focus.__init_subclass__.
_FOCUS_BY_ID: dict[str, type["Focus"]] = {}


class Focus(ABC):
    """Discriminator for which Panels apply to current session state."""

    id: ClassVar[str]
    label: ClassVar[str]
    icon: ClassVar[str]
    order: ClassVar[int] = 100

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Skip subclasses that don't declare id (intermediate ABCs).
        if "id" not in cls.__dict__:
            return
        focus_id = cls.__dict__["id"]
        if focus_id in _FOCUS_BY_ID:
            existing = _FOCUS_BY_ID[focus_id]
            raise ValueError(
                f"Focus id collision: {cls.__name__} and {existing.__name__} "
                f"both declare id={focus_id!r}"
            )
        _FOCUS_BY_ID[focus_id] = cls

    @classmethod
    @abstractmethod
    def available(cls, ctx: Any) -> bool:
        """Return True if this Focus is reachable given current state.

        Implementations typically read one or more reactive fields off ctx.
        """


def focus_by_id(focus_id: str) -> type[Focus] | None:
    """Return the Focus subclass whose id matches focus_id, or None."""
    return _FOCUS_BY_ID.get(focus_id)


def all_focuses() -> list[type[Focus]]:
    """Return all registered Focus subclasses."""
    return list(_FOCUS_BY_ID.values())
```

- [ ] **Step 4: Update panel package exports**

Modify `packages/haywire-core/src/haywire/ui/panel/__init__.py` to add:

```python
from .focus import Focus, all_focuses, focus_by_id
```

And add `"Focus", "all_focuses", "focus_by_id"` to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/panel/test_focus.py -v`
Expected: 4 passed.

- [ ] **Step 6: Run quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/panel/ tests/ui/panel/`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/panel/ tests/ui/panel/`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/panel/focus.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/focus.py \
        packages/haywire-core/src/haywire/ui/panel/__init__.py \
        tests/ui/panel/test_focus.py
git commit -m "feat(panel): add Focus base class with id ClassVar and auto-discovery map"
```

---

### Task 9: Migrate existing focuses to declare id

**Files:**
- Modify: `barn/haybale-core/haybale_core/focuses.py`
- Modify: `barn/haybale-studio/haybale_studio/focuses.py`
- Test: `tests/libraries/test_focuses_have_ids.py` (new)

The Focus subclasses in haybale-core and haybale-studio don't exist on `main` (they were on the panels_and_hosts branch). We need to create them now. Refer to the panels_and_hosts branch for shape; the migration spec §3.2 has the focus list.

Wait — let me check whether the focus classes exist on main.

- [ ] **Step 0: Check whether haybale-core/focuses.py exists**

Run: `ls barn/haybale-core/haybale_core/focuses.py barn/haybale-studio/haybale_studio/focuses.py 2>&1`

If both files exist (carried over from the merge of panels_and_hosts foundations into main): proceed to Step 1, adding `id` ClassVar to existing classes.

If they don't exist: create them from scratch using the patterns below.

- [ ] **Step 1: Add tests**

```python
# tests/libraries/test_focuses_have_ids.py
"""Every Focus subclass in haybale-core and haybale-studio must declare an id."""
import pytest

from haywire.ui.panel.focus import all_focuses, focus_by_id


def test_node_focus_has_id():
    # Importing the module triggers Focus.__init_subclass__.
    from haybale_core.focuses import NodeFocus

    assert NodeFocus.id == "node"
    assert focus_by_id("node") is NodeFocus


def test_edge_focus_has_id():
    from haybale_core.focuses import EdgeFocus

    assert EdgeFocus.id == "edge"
    assert focus_by_id("edge") is EdgeFocus


def test_graph_focus_has_id():
    from haybale_core.focuses import GraphFocus

    assert GraphFocus.id == "graph"
    assert focus_by_id("graph") is GraphFocus


def test_port_focus_has_id():
    from haybale_core.focuses import PortFocus

    assert PortFocus.id == "port"
    assert focus_by_id("port") is PortFocus


def test_app_focus_has_id():
    from haybale_studio.focuses import AppFocus

    assert AppFocus.id == "app"
    assert focus_by_id("app") is AppFocus


def test_execution_focus_has_id():
    from haybale_studio.focuses import ExecutionFocus

    assert ExecutionFocus.id == "execution"
    assert focus_by_id("execution") is ExecutionFocus


def test_canvas_focus_has_id():
    from haybale_studio.focuses import CanvasFocus

    assert CanvasFocus.id == "canvas"


def test_settings_focus_has_id():
    from haybale_studio.focuses import SettingsFocus

    assert SettingsFocus.id == "settings"
```

- [ ] **Step 2: Run tests to verify their pass/fail state**

Run: `uv run pytest tests/libraries/test_focuses_have_ids.py -v`
Expected: depends on Step 0 result. Either ImportError (no focuses module) or AttributeError (no `id` ClassVar).

- [ ] **Step 3: Create or update the focus modules**

```python
# barn/haybale-core/haybale_core/focuses.py
"""Selection-state Focus classes — live with their semantic owner.

Each focus reads from a SessionContext reactive field to determine
availability.
"""

from __future__ import annotations

from haywire.ui.context import SessionContext
from haywire.ui.panel.focus import Focus


class GraphFocus(Focus):
    id = "graph"
    label = "Graph"
    icon = "polyline"
    order = 50

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.active_graph.value is not None


class NodeFocus(Focus):
    id = "node"
    label = "Node"
    icon = "account_tree"
    order = 60

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.active_node.value is not None


class EdgeFocus(Focus):
    id = "edge"
    label = "Edge"
    icon = "cable"
    order = 70

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.active_edge.value is not None


class PortFocus(Focus):
    id = "port"
    label = "Port"
    icon = "settings_input_component"
    order = 80

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.active_port.value is not None
```

```python
# barn/haybale-studio/haybale_studio/focuses.py
"""Studio-specific Focus classes for PropertiesEditor.

App/Execution/Canvas focuses are always-available (mode tabs).
SettingsFocus gates on active_node — settings panels need a node.
"""

from __future__ import annotations

from haywire.ui.context import SessionContext
from haywire.ui.panel.focus import Focus


class AppFocus(Focus):
    id = "app"
    label = "Application"
    icon = "home"
    order = 10

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True


class ExecutionFocus(Focus):
    id = "execution"
    label = "Execution"
    icon = "rocket_launch"
    order = 20

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True


class CanvasFocus(Focus):
    id = "canvas"
    label = "Canvas & Nodes"
    icon = "grid_on"
    order = 30

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True


class SettingsFocus(Focus):
    id = "settings"
    label = "Settings"
    icon = "tune"
    order = 65

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.active_node.value is not None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/libraries/test_focuses_have_ids.py -v`
Expected: 8 passed.

- [ ] **Step 5: Run quality suite**

Run: `uv run ruff check barn/haybale-core/haybale_core/focuses.py barn/haybale-studio/haybale_studio/focuses.py tests/libraries/test_focuses_have_ids.py`
Run: `uv run ruff format barn/haybale-core/haybale_core/focuses.py barn/haybale-studio/haybale_studio/focuses.py tests/libraries/test_focuses_have_ids.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-core/haybale_core/focuses.py \
        barn/haybale-studio/haybale_studio/focuses.py \
        tests/libraries/test_focuses_have_ids.py
git commit -m "feat(focus): declare focus classes with id ClassVar"
```

---

### Task 10: Add Panel base class

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/panel/panel.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/__init__.py`
- Test: `tests/ui/panel/test_panel_base.py`

`Panel` is the new base class. Phase 1 contract: `poll` is a classmethod, `draw` is an instance method. Both default-implementations are minimal so subclasses can override.

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/panel/test_panel_base.py
"""Panel base class: classmethod poll (default True); abstract draw."""
import pytest

from haywire.ui.panel import Panel


def test_panel_default_poll_returns_true():
    class P(Panel):
        def draw(self, ctx, layout, actions):
            pass

    assert P.poll(ctx=None) is True


def test_panel_subclass_can_override_poll():
    class P(Panel):
        @classmethod
        def poll(cls, ctx):
            return False

        def draw(self, ctx, layout, actions):
            pass

    assert P.poll(ctx=None) is False


def test_panel_draw_is_required():
    """Instantiating a Panel without draw should fail."""

    class P(Panel):
        pass

    with pytest.raises(TypeError, match="abstract"):
        P()


def test_panel_with_draw_can_be_instantiated():
    class P(Panel):
        def draw(self, ctx, layout, actions):
            pass

    instance = P()
    assert instance is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/panel/test_panel_base.py -v`
Expected: FAIL — `from haywire.ui.panel import Panel` fails.

- [ ] **Step 3: Create the Panel base class**

```python
# packages/haywire-core/src/haywire/ui/panel/panel.py
"""Panel — the new contract base class.

Phase 1 contract:
  - poll(cls, ctx) -> bool: classmethod; default True. Host evaluates
    before instantiating the panel.
  - draw(self, ctx, layout, actions) -> None: instance method; abstract.
    Host calls only when poll returned True.

Phase 2 promotes poll to an instance method, adds @reads, and wraps
both methods in Subscriptions. Panels written for Phase 1 migrate
mechanically to Phase 2 (drop @classmethod, change cls → self).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.panel.base import PanelLayout
    from haywire.ui.panel.identity import PanelIdentity


class Panel(ABC):
    """Base class for new-contract panels.

    Subclasses are decorated with `@panel(...)` and inherit from `Panel`:

        @panel(action=PropertiesEditorActions, focus=NodeFocus, label="My Panel")
        class MyPanel(Panel):
            @classmethod
            def poll(cls, ctx: SessionContext) -> bool:
                return ctx.active_node.value is not None

            def draw(self, ctx, layout, actions):
                ...
    """

    # Set by @panel decorator.
    class_identity: ClassVar["PanelIdentity"]

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        """Return whether the panel should currently be visible.

        Default: True (always visible). Override when visibility depends
        on session state.

        Phase 1: classmethod (host calls before instantiation).
        Phase 2: instance method (wrapped in Subscription).
        """
        return True

    @abstractmethod
    def draw(
        self,
        ctx: "SessionContext",
        layout: "PanelLayout",
        actions: Any,
    ) -> None:
        """Render the panel's content.

        Called only when poll returned True. The panel renders into
        `layout`'s container. `actions` is the host's actions object,
        typed against the panel's declared `action=` Protocol.
        """
```

- [ ] **Step 4: Update panel package exports**

Modify `packages/haywire-core/src/haywire/ui/panel/__init__.py` to add:

```python
from .panel import Panel
```

And add `"Panel"` to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/panel/test_panel_base.py -v`
Expected: 4 passed.

- [ ] **Step 6: Run quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/panel/ tests/ui/panel/`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/panel/ tests/ui/panel/`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/panel/panel.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/panel.py \
        packages/haywire-core/src/haywire/ui/panel/__init__.py \
        tests/ui/panel/test_panel_base.py
git commit -m "feat(panel): add Panel base class for new-contract panels"
```

---

### Task 11: Extend @panel decorator with action= argument

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/decorator.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/identity.py`
- Test: `tests/ui/panel/test_panel_decorator.py`

The legacy `@panel` already supports `host=`/`focus=` (carried over from panels_and_hosts foundations on main). We need to:
1. Add `action=` argument (replaces `host=` for the new contract).
2. Store action and focus class references on `class_identity`.
3. Reject panels that mix legacy (`editors=`/`scopes=`) and new (`action=`/`focus=`) forms.
4. Validate `action` is a class.

Phase 1 keeps the legacy form working for the unmigrated panels.

- [ ] **Step 1: Read current decorator and identity**

Run: `cat packages/haywire-core/src/haywire/ui/panel/decorator.py`
Run: `cat packages/haywire-core/src/haywire/ui/panel/identity.py`

Familiarize with current shape. The `host=` argument exists and translates to a string editor_key today; we replace it with `action=` while keeping the same registry-side translation.

- [ ] **Step 2: Write the failing tests**

```python
# tests/ui/panel/test_panel_decorator.py
"""@panel with action= and focus= validates required args."""
from typing import Protocol, runtime_checkable

import pytest

from haywire.ui.panel import Panel, panel
from haywire.ui.panel.focus import Focus


@runtime_checkable
class _DummyActions(Protocol):
    def do_thing(self) -> None: ...


class _DummyFocus(Focus):
    id = "decorator_test_focus"
    label = "Test"
    icon = "x"

    @classmethod
    def available(cls, ctx):
        return True


def test_panel_with_action_and_focus_validates_and_sets_identity():
    @panel(
        action=_DummyActions,
        focus=_DummyFocus,
        label="My Panel",
    )
    class P(Panel):
        def draw(self, ctx, layout, actions):
            pass

    assert P.class_identity.label == "My Panel"
    assert P.class_identity.action is _DummyActions
    assert P.class_identity.focus is _DummyFocus


def test_panel_action_must_be_a_class():
    with pytest.raises(TypeError, match="action"):

        @panel(
            action="not_a_class",  # type: ignore[arg-type]
            focus=_DummyFocus,
            label="Bad",
        )
        class P(Panel):
            def draw(self, ctx, layout, actions):
                pass


def test_panel_focus_must_subclass_focus():
    class _NotAFocus:
        pass

    with pytest.raises(TypeError, match="focus"):

        @panel(
            action=_DummyActions,
            focus=_NotAFocus,  # type: ignore[arg-type]
            label="Bad",
        )
        class P(Panel):
            def draw(self, ctx, layout, actions):
                pass


def test_panel_legacy_and_new_args_mutually_exclusive():
    """Mixing editors=/action= raises."""

    with pytest.raises(ValueError, match="legacy|new|both"):

        @panel(
            editors="properties",
            action=_DummyActions,
            focus=_DummyFocus,
            label="Mixed",
        )
        class P(Panel):
            def draw(self, ctx, layout, actions):
                pass


def test_panel_label_is_required_for_new_form():
    with pytest.raises((TypeError, ValueError)):

        @panel(
            action=_DummyActions,
            focus=_DummyFocus,
            # label missing
        )
        class P(Panel):
            def draw(self, ctx, layout, actions):
                pass
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/ui/panel/test_panel_decorator.py -v`
Expected: FAIL — `action=` arg not supported, validation not present.

- [ ] **Step 4: Update PanelIdentity to carry action and focus**

Read `packages/haywire-core/src/haywire/ui/panel/identity.py`. Add fields:

```python
# At the appropriate point in the existing dataclass:
    action: type | None = None       # new contract: the action Protocol/ABC class
    focus: type | None = None        # new contract: the Focus subclass
```

Keep the legacy fields (`editor_keys`, `scopes`) as-is — they remain for unmigrated panels.

- [ ] **Step 5: Update the decorator**

Edit `packages/haywire-core/src/haywire/ui/panel/decorator.py`:

1. Add `action` parameter:

```python
def panel(
    cls=None,
    /,
    *,
    editors: Optional[Union[str, list[str]]] = None,
    scopes: Optional[Union[str, list[str]]] = None,
    host: Optional[type] = None,        # legacy class-keyed; will be removed in Phase 1.5
    focus: Optional[type] = None,
    action: Optional[type] = None,      # NEW: action Protocol/ABC class
    label: Optional[str] = None,
    icon: Optional[str] = None,
    order: int = 100,
    default_open: bool = True,
    description: str = "",
    registry_id: Optional[str] = None,
):
```

2. In the inner decorator, identify which form is used and validate:

```python
        legacy_provided = editors is not None or scopes is not None
        host_provided = host is not None
        new_provided = action is not None

        if legacy_provided and new_provided:
            raise ValueError(
                "@panel: specify either legacy (editors=, scopes=) OR new (action=, focus=), "
                "not both"
            )

        if new_provided:
            if focus is None:
                raise ValueError("@panel: action= requires focus=")
            if label is None:
                raise ValueError("@panel: action= form requires label=")
            if not isinstance(action, type):
                raise TypeError(f"@panel: action= must be a class, got {type(action)}")
            from haywire.ui.panel.focus import Focus

            if not (isinstance(focus, type) and issubclass(focus, Focus)):
                raise TypeError(
                    f"@panel: focus= must be a Focus subclass, got {focus}"
                )
            # Translate to legacy editor_keys/scopes for the index — Phase 1
            # registry continues to use string keys internally; new methods
            # added in Task 13 do the class lookup.
            _editors: list[str] = ["properties"]  # all new-form panels in Phase 1 target PropertiesEditor
            _scopes: list[str] = [focus.id]
            _action = action
            _focus = focus
        elif host_provided:
            # Legacy host-keyed form (already supported on main).
            ...
        elif legacy_provided:
            # Legacy editors= / scopes= form.
            ...
        else:
            raise ValueError("@panel: must specify (editors, scopes), (host, focus), or (action, focus)")

        # ... build PanelIdentity with action=_action, focus=_focus when new form
```

(Adapt to actual current code structure; see existing logic.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/ui/panel/test_panel_decorator.py -v`
Expected: 5 passed.

- [ ] **Step 7: Run the full test suite — verify nothing broke**

Run: `uv run pytest tests/ -x 2>&1 | tail -20`
Expected: green. Existing legacy-form panels still register correctly.

- [ ] **Step 8: Run quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/panel/ tests/ui/panel/`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/panel/ tests/ui/panel/`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/panel/`
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/decorator.py \
        packages/haywire-core/src/haywire/ui/panel/identity.py \
        tests/ui/panel/test_panel_decorator.py
git commit -m "feat(panel): add action= argument to @panel decorator with validation"
```

---

### Task 12: Add registry methods for class-keyed lookup

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/registry.py`
- Test: `tests/ui/panel/test_panel_registry_class_keyed.py`

Two new methods:
- `get_panels_for(actions_provider, focus)` — returns panels whose `action` Protocol is satisfied by `actions_provider` AND whose `focus` matches.
- `get_focuses_for(actions_provider)` — returns the set of focus classes referenced by panels whose `action` is satisfied by `actions_provider`.

Phase 1 implementation: walk the existing `_index`, filter by `class_identity.action` and `class_identity.focus`. Phase 1.5 may rebuild the index for performance.

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/panel/test_panel_registry_class_keyed.py
"""PanelRegistry.get_panels_for and get_focuses_for use isinstance + focus-class match."""
from typing import Protocol, runtime_checkable

import pytest

from haywire.ui.panel import Panel, PanelRegistry, panel
from haywire.ui.panel.focus import Focus


@runtime_checkable
class _ActionsA(Protocol):
    def verb_a(self) -> None: ...


@runtime_checkable
class _ActionsB(Protocol):
    def verb_b(self) -> None: ...


class _FocusOne(Focus):
    id = "one_test_focus"
    label = "One"
    icon = "1"

    @classmethod
    def available(cls, ctx):
        return True


class _FocusTwo(Focus):
    id = "two_test_focus"
    label = "Two"
    icon = "2"

    @classmethod
    def available(cls, ctx):
        return True


@panel(action=_ActionsA, focus=_FocusOne, label="A1")
class _PanelA1(Panel):
    def draw(self, ctx, layout, actions):
        pass


@panel(action=_ActionsA, focus=_FocusTwo, label="A2")
class _PanelA2(Panel):
    def draw(self, ctx, layout, actions):
        pass


@panel(action=_ActionsB, focus=_FocusOne, label="B1")
class _PanelB1(Panel):
    def draw(self, ctx, layout, actions):
        pass


class _ProviderA:
    def verb_a(self) -> None:
        pass


class _ProviderB:
    def verb_b(self) -> None:
        pass


def _registry_with_panels() -> PanelRegistry:
    """Build a registry, manually register the test panels."""
    reg = PanelRegistry()
    for cls in (_PanelA1, _PanelA2, _PanelB1):
        reg._register_class(cls)
    return reg


def test_get_panels_for_filters_by_action_and_focus():
    reg = _registry_with_panels()
    p = _ProviderA()
    panels = reg.get_panels_for(actions_provider=p, focus=_FocusOne)
    assert _PanelA1 in panels
    assert _PanelA2 not in panels  # wrong focus
    assert _PanelB1 not in panels  # wrong action


def test_get_panels_for_returns_empty_when_action_doesnt_satisfy():
    reg = _registry_with_panels()

    class _Unrelated:
        pass

    panels = reg.get_panels_for(actions_provider=_Unrelated(), focus=_FocusOne)
    assert panels == []


def test_get_focuses_for_returns_focuses_referenced_by_compatible_panels():
    reg = _registry_with_panels()
    p_a = _ProviderA()
    focuses = reg.get_focuses_for(actions_provider=p_a)
    assert _FocusOne in focuses
    assert _FocusTwo in focuses

    p_b = _ProviderB()
    focuses_b = reg.get_focuses_for(actions_provider=p_b)
    assert _FocusOne in focuses_b
    assert _FocusTwo not in focuses_b
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/panel/test_panel_registry_class_keyed.py -v`
Expected: FAIL — `get_panels_for` and `get_focuses_for` don't exist (or have signatures from panels_and_hosts that differ).

- [ ] **Step 3: Read current registry**

Run: `cat packages/haywire-core/src/haywire/ui/panel/registry.py | head -100`

Note: `get_panels_for_host(host_cls, focus_cls)` may already exist (carried over from panels_and_hosts). Phase 1 introduces the new contract version.

- [ ] **Step 4: Add the new methods to PanelRegistry**

Edit `packages/haywire-core/src/haywire/ui/panel/registry.py`. Add (preserving existing methods):

```python
    # ------------------------------------------------------------------
    # Phase 1 contract-centric lookup
    # ------------------------------------------------------------------

    def get_panels_for(
        self,
        actions_provider: Any,
        focus: type,  # Focus subclass
    ) -> List[type]:
        """Return panels whose action contract is satisfied by actions_provider
        AND whose focus matches the given focus class.

        Sorted by class_identity.order. Phase 1 implementation walks
        the registered classes; Phase 1.5 may add an indexed lookup.
        """
        result: List[type] = []
        for cls in self.get_all_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            action = getattr(identity, "action", None)
            panel_focus = getattr(identity, "focus", None)
            if action is None or panel_focus is None:
                continue
            if panel_focus is not focus:
                continue
            if not isinstance(actions_provider, action):
                continue
            result.append(cls)
        result.sort(key=lambda c: c.class_identity.order)
        return result

    def get_focuses_for(self, actions_provider: Any) -> List[type]:
        """Return the set of focus classes referenced by any panel whose
        action contract is satisfied by actions_provider.

        Returned as a list (preserving registry insertion order is not
        guaranteed; the consumer typically merges with default_focuses
        and sorts by Focus.order).
        """
        focuses: list[type] = []
        seen: set[type] = set()
        for cls in self.get_all_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            action = getattr(identity, "action", None)
            focus = getattr(identity, "focus", None)
            if action is None or focus is None:
                continue
            if focus in seen:
                continue
            if isinstance(actions_provider, action):
                seen.add(focus)
                focuses.append(focus)
        return focuses
```

If `get_all_classes()` doesn't exist on `BaseRegistry`, use the existing iteration mechanism (walk `self._index` values uniquely, or whatever is in place — read the registry file to confirm).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/panel/test_panel_registry_class_keyed.py -v`
Expected: 3 passed.

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest tests/ -x 2>&1 | tail -20`
Expected: green; existing tests still pass.

- [ ] **Step 7: Quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/panel/ tests/ui/panel/`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/panel/ tests/ui/panel/`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/panel/registry.py`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/registry.py \
        tests/ui/panel/test_panel_registry_class_keyed.py
git commit -m "feat(registry): add get_panels_for and get_focuses_for class-keyed lookup"
```

---

### Task 13: Error trapping at the host boundary — helper

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/panel/error_boundary.py`
- Test: `tests/ui/panel/test_panel_error_boundary.py`

Per spec §6, panel poll/draw failures must be caught, wrapped as `HaywireException`, and rendered inline. We add a helper used by hosts.

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/panel/test_panel_error_boundary.py
"""Panel error boundary catches exceptions, wraps as HaywireException, returns error info."""
from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui.panel.error_boundary import safe_call_panel_method


def test_safe_call_returns_value_on_success():
    def fn():
        return 42

    result, error = safe_call_panel_method(fn, panel_name="MyPanel", method_name="poll")
    assert result == 42
    assert error is None


def test_safe_call_catches_exceptions_and_wraps():
    def fn():
        raise ValueError("boom")

    result, error = safe_call_panel_method(fn, panel_name="MyPanel", method_name="poll")
    assert result is None
    assert isinstance(error, HaywireException)
    assert "MyPanel" in str(error)
    assert "poll" in str(error)


def test_safe_call_passes_through_haywire_exception():
    """If the function raises HaywireException, don't double-wrap."""
    inner = HaywireException("inner failure")

    def fn():
        raise inner

    result, error = safe_call_panel_method(fn, panel_name="MyPanel", method_name="draw")
    assert error is inner
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/panel/test_panel_error_boundary.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the helper**

```python
# packages/haywire-core/src/haywire/ui/panel/error_boundary.py
"""Error boundary helper for panel hosts.

Hosts call `safe_call_panel_method` to invoke a panel's poll() or draw().
Any exception is caught, wrapped as HaywireException, and returned as
(None, exception). The host then renders an error widget inline rather
than crashing.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from haywire.core.errors.haywire_exception import HaywireException

logger = logging.getLogger(__name__)


def safe_call_panel_method(
    fn: Callable[[], Any],
    *,
    panel_name: str,
    method_name: str,
) -> tuple[Any, HaywireException | None]:
    """Call fn(), returning (result, None) on success or (None, exception) on failure.

    HaywireException instances are passed through unchanged. Other
    exceptions are wrapped with context about the panel and method.
    The error is also logged.
    """
    try:
        return fn(), None
    except HaywireException as exc:
        logger.warning(
            "Panel error in %s.%s: %s", panel_name, method_name, exc, exc_info=True
        )
        return None, exc
    except Exception as exc:
        wrapped = HaywireException(
            f"Panel {panel_name}.{method_name} raised {type(exc).__name__}: {exc}",
        )
        wrapped.__cause__ = exc
        logger.warning(
            "Panel error in %s.%s: %s", panel_name, method_name, exc, exc_info=True
        )
        return None, wrapped
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/panel/test_panel_error_boundary.py -v`
Expected: 3 passed.

- [ ] **Step 5: Quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/panel/error_boundary.py tests/ui/panel/test_panel_error_boundary.py`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/panel/error_boundary.py tests/ui/panel/test_panel_error_boundary.py`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/panel/error_boundary.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/error_boundary.py \
        tests/ui/panel/test_panel_error_boundary.py
git commit -m "feat(panel): add error boundary helper for safe panel method invocation"
```

---

### Task 14: Verify framework foundations integrate

Smoke verification that the new primitives compose correctly with each other before we touch PropertiesEditor.

- [ ] **Step 1: Write an integration test**

```python
# tests/ui/panel/test_phase1_integration.py
"""Cross-cutting: define a Panel, register it, query the registry, get an actions provider, get the panel."""
from typing import Protocol, runtime_checkable
from unittest.mock import MagicMock

from haywire.ui.context import SessionContext
from haywire.ui.panel import Panel, PanelRegistry, panel
from haywire.ui.panel.focus import Focus


@runtime_checkable
class _Verbose(Protocol):
    def speak(self) -> None: ...


class _LoudFocus(Focus):
    id = "loud_test_focus"
    label = "Loud"
    icon = "volume_up"

    @classmethod
    def available(cls, ctx):
        return True


@panel(action=_Verbose, focus=_LoudFocus, label="Speaker")
class _SpeakerPanel(Panel):
    @classmethod
    def poll(cls, ctx):
        return ctx.active_node.value is not None

    def draw(self, ctx, layout, actions):
        pass


def test_full_pipeline_panel_registered_and_queryable():
    reg = PanelRegistry()
    reg._register_class(_SpeakerPanel)

    class Host:
        def speak(self) -> None:
            pass

    host = Host()
    panels = reg.get_panels_for(actions_provider=host, focus=_LoudFocus)
    assert _SpeakerPanel in panels


def test_full_pipeline_focus_discovered_via_registry():
    reg = PanelRegistry()
    reg._register_class(_SpeakerPanel)

    class Host:
        def speak(self) -> None:
            pass

    focuses = reg.get_focuses_for(actions_provider=Host())
    assert _LoudFocus in focuses


def test_panel_poll_is_classmethod_and_reads_session_context():
    ctx = SessionContext(session_id="t", app=MagicMock())

    # No active node — poll returns False.
    assert _SpeakerPanel.poll(ctx) is False

    ctx.active_node.value = MagicMock()
    assert _SpeakerPanel.poll(ctx) is True
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/ui/panel/test_phase1_integration.py -v`
Expected: 3 passed.

- [ ] **Step 3: Run full test suite as final framework checkpoint**

Run: `uv run pytest tests/ -v 2>&1 | tail -10`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add tests/ui/panel/test_phase1_integration.py
git commit -m "test(panel): integration test for Phase 1 framework foundations"
```

---

## Track E — PropertiesEditor + Panel Migrations

### Task 15: Rewrite PropertiesEditor toolbar to use focus discovery

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/properties_editor.py`
- Test: `tests/ui/properties_editor/test_toolbar_discovery.py`

The toolbar reads from `default_focuses ∪ registry.get_focuses_for(self)` (per Q13). The legacy `get_scopes("properties")` source is dropped. Panels keep working through the legacy registry index until they migrate.

- [ ] **Step 1: Read current PropertiesEditor**

Run: `cat barn/haybale-studio/haybale_studio/editors/properties_editor.py | head -100`
Note the current toolbar-build path. Today it queries `panel_registry.get_scopes("properties")`.

- [ ] **Step 2: Write the toolbar discovery test**

```python
# tests/ui/properties_editor/test_toolbar_discovery.py
"""PropertiesEditor toolbar = default_focuses ∪ registry.get_focuses_for(self), sorted by Focus.order."""
from typing import Protocol, runtime_checkable
from unittest.mock import MagicMock

from haywire.ui.panel import Panel, PanelRegistry, panel
from haywire.ui.panel.focus import Focus


# Define a library focus that PropertiesEditor doesn't enumerate by default.
class _LibraryFocus(Focus):
    id = "library_provided_focus_test"
    label = "Library Provided"
    icon = "library_books"
    order = 90

    @classmethod
    def available(cls, ctx):
        return True


@panel(
    action="haybale_studio.editors.properties_editor_actions:PropertiesEditorActions",  # see Step 3 about importing
    focus=_LibraryFocus,
    label="Library Panel",
)
class _LibraryProvidedPanel(Panel):
    def draw(self, ctx, layout, actions):
        pass


# This test scaffolds will need adjustment depending on PropertiesEditor's
# constructor signature and how it composes default_focuses. Adjust to
# match the actual editor.
def test_toolbar_includes_default_focuses():
    """All default_focuses appear in the toolbar regardless of registered panels."""
    from haybale_studio.editors.properties_editor import PropertiesEditor

    editor = PropertiesEditor(panel_registry=PanelRegistry())
    focuses = editor._compute_toolbar_focuses()
    # AppFocus should be in default_focuses.
    from haybale_studio.focuses import AppFocus

    assert AppFocus in focuses


def test_toolbar_includes_library_focus_via_registry():
    """A library-defined focus appears in the toolbar via registry discovery."""
    from haybale_studio.editors.properties_editor import PropertiesEditor

    reg = PanelRegistry()
    reg._register_class(_LibraryProvidedPanel)
    editor = PropertiesEditor(panel_registry=reg)
    focuses = editor._compute_toolbar_focuses()
    assert _LibraryFocus in focuses


def test_toolbar_focuses_are_sorted_by_focus_order():
    from haybale_studio.editors.properties_editor import PropertiesEditor
    from haybale_studio.focuses import AppFocus, ExecutionFocus

    editor = PropertiesEditor(panel_registry=PanelRegistry())
    focuses = editor._compute_toolbar_focuses()
    app_idx = focuses.index(AppFocus)  # order 10
    exec_idx = focuses.index(ExecutionFocus)  # order 20
    assert app_idx < exec_idx
```

(Note: the `action=` argument value in `_LibraryProvidedPanel` should reference an actual class. Use `PropertiesEditorActions` from haybale_studio. Adjust the import at the top of the test.)

Adjust the test:

```python
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions

@panel(
    action=PropertiesEditorActions,
    focus=_LibraryFocus,
    label="Library Panel",
)
class _LibraryProvidedPanel(Panel):
    ...
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/ui/properties_editor/test_toolbar_discovery.py -v`
Expected: FAIL — `_compute_toolbar_focuses` doesn't exist; the editor's toolbar code doesn't yet use registry discovery.

- [ ] **Step 4: Update PropertiesEditor**

Edit `barn/haybale-studio/haybale_studio/editors/properties_editor.py`:

1. Add `default_focuses` ClassVar (replacing or renaming any existing `accepted_focuses`):

```python
class PropertiesEditor(BaseEditor):
    default_focuses: ClassVar[tuple[type[Focus], ...]] = (
        AppFocus,
        ExecutionFocus,
        CanvasFocus,
        GraphFocus,
        NodeFocus,
        SettingsFocus,
        EdgeFocus,
        PortFocus,
    )
```

2. Add a `_compute_toolbar_focuses` method:

```python
    def _compute_toolbar_focuses(self) -> list[type[Focus]]:
        """Compute the toolbar's focuses: default ∪ registry-discovered, sorted by Focus.order."""
        focuses: set[type[Focus]] = set(self.default_focuses)
        if self._panel_registry is not None:
            focuses.update(self._panel_registry.get_focuses_for(actions_provider=self))
        return sorted(focuses, key=lambda f: f.order)
```

3. Update the toolbar render path to call `_compute_toolbar_focuses()` instead of `panel_registry.get_scopes(...)`. Each focus class now provides label/icon directly (Focus.label, Focus.icon) rather than via ScopeDescriptor.

(The exact edit depends on the current structure — may require reading 100-200 lines of the editor. Apply the principle: replace `get_scopes` source with `_compute_toolbar_focuses` source, and read `focus.label`/`focus.icon` instead of `scope_descriptor.label`/`.icon`.)

4. Update the panel-mounting path to use `get_panels_for(actions_provider=self, focus=self._active_focus)` instead of `get_panels(editor_key, scope_id)`.

5. Ensure `PropertiesEditor` satisfies the `PropertiesEditorActions` Protocol (it already has `clear_selection`; nothing to add for Phase 1's start state).

6. Update `_RELEVANT_SIGNALS` to include `SelectionMoved` (per Q10):

```python
from haywire.ui.context_signals import GraphDataMutated, SelectionMoved

class PropertiesEditor(BaseEditor):
    _RELEVANT_SIGNALS = (GraphDataMutated, SelectionMoved)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/properties_editor/test_toolbar_discovery.py -v`
Expected: 3 passed.

- [ ] **Step 6: Run the full test suite — verify no regressions**

Run: `uv run pytest tests/ -x 2>&1 | tail -30`
Expected: green. The PropertiesEditor's existing legacy panels (`scopes="node"`, etc.) should still appear because the registry's `get_panels_for` only returns class-keyed panels — but Phase 1 needs a transitional path: PropertiesEditor must mount BOTH legacy AND new-form panels for its current focus.

- [ ] **Step 7: Add the dual-mount path**

If tests reveal that legacy panels stop appearing after the toolbar rewrite, update PropertiesEditor's mount path to query BOTH:

```python
    def _mount_panels_for_active_focus(self) -> list:
        """Phase 1 transitional: mount class-keyed Panels AND legacy BasePanels."""
        new_panels = self._panel_registry.get_panels_for(
            actions_provider=self, focus=self._active_focus
        )
        legacy_panels = self._panel_registry.get_panels(
            editor_key="properties", scope_id=self._active_focus.id
        )
        # Filter out duplicates (a class won't appear in both — they have
        # different identity shapes — but be defensive).
        seen = set(new_panels)
        merged = list(new_panels) + [p for p in legacy_panels if p not in seen]
        merged.sort(key=lambda c: c.class_identity.order)
        return merged
```

Both old and new panels coexist for Phase 1. Cleanup happens in Phase 1.5.

- [ ] **Step 8: Smoke-test the app**

Run: `uv run haywire`. Open the app. Click a node. Verify the Properties panel renders the same panels it did before. Toggle through focuses. Verify the toolbar shows the same tabs.

- [ ] **Step 9: Run the full quality suite**

Run: `uv run ruff check barn/haybale-studio/haybale_studio/editors/properties_editor.py tests/ui/properties_editor/`
Run: `uv run ruff format barn/haybale-studio/haybale_studio/editors/properties_editor.py tests/ui/properties_editor/`
Run: `uv run mypy packages/haywire-core/src/`
Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/properties_editor.py \
        tests/ui/properties_editor/test_toolbar_discovery.py
git commit -m "feat(properties-editor): toolbar reads from default_focuses ∪ registry.get_focuses_for

- Drops dependency on register_scope/get_scopes for toolbar metadata.
- Adds dual-mount path for class-keyed Panel and legacy BasePanel.
- Re-adds SelectionMoved to _RELEVANT_SIGNALS for coarse re-render.

Phase 1 of the panel-contract migration."
```

---

### Task 16: Migrate the 16 Phase 1 panels

This is the main migration. Each panel converts from `BasePanel` to `Panel`, from `editors=`/`scopes=` to `action=`/`focus=`. Each panel is a small, isolated change. Migrate one at a time; commit each.

For each panel below, follow this pattern:

1. **Read the current panel.** Note its `editors`, `scopes`, `label`, `icon`, `order`, `default_open`, `description`. Note the `poll` (if overridden) and `draw` body.
2. **Update the file:**
   - Imports: replace `from haywire.ui.panel.base import BasePanel, PanelLayout` with `from haywire.ui.panel import Panel` (keep `PanelLayout` if needed).
   - Add: `from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions`
   - Add: `from haybale_core.focuses import NodeFocus` (or whichever focus matches).
   - Decorator: `@panel(editors="properties", scopes="X", ...)` → `@panel(action=PropertiesEditorActions, focus=XFocus, ...)`.
   - Class: `class P(BasePanel):` → `class P(Panel):`.
   - Method: `def draw(self, context: SessionContext, layout: PanelLayout)` → `def draw(self, ctx: SessionContext, layout: PanelLayout, actions: PropertiesEditorActions)`. (Rename `context` to `ctx` if preferred for consistency with new contract; also acceptable to keep `context` if the body has many references.)
   - Read sites inside draw: `context.active_node` → `ctx.active_node.value` (already done in Task 6 for SessionContext fields, but per-panel may have its own state reads to update).
   - `actions` parameter is unused for settings panels; that's expected (per Q15).
3. **Test the panel.** If a corresponding test exists, run it. If not, write a minimal mount test.
4. **Smoke-test the app.** Click around; verify the panel renders.
5. **Commit each panel separately.**

The 16 panels by focus:

#### 16.1: NodeSettingsPanel (settings focus)

- [ ] **Files:** `barn/haybale-core/haybale_core/panels/node_settings.py`
- [ ] **Migrate using the pattern above.** `scopes="settings"` → `focus=SettingsFocus`. Action is unused; declare `action=PropertiesEditorActions`.
- [ ] **Run:** `uv run pytest tests/libraries/ -k "node_settings or settings_panel" -v`
- [ ] **Smoke test app.**
- [ ] **Commit:** `git commit -m "refactor(node_settings): migrate NodeSettingsPanel to new contract"`

#### 16.2: NodePortsPanel (node focus)

- [ ] **Files:** `barn/haybale-core/haybale_core/panels/node_ports_panel.py`
- [ ] Migrate: `scopes="node"` → `focus=NodeFocus`. Settings panel pattern.
- [ ] **Run:** related tests.
- [ ] **Smoke test.**
- [ ] **Commit.**

#### 16.3: NodeStatusPanel (node focus)

- [ ] **Files:** `barn/haybale-core/haybale_core/panels/node_status.py`
- [ ] Migrate.
- [ ] Test, smoke, commit.

#### 16.4: NodeInfoPanel (node focus)

- [ ] **Files:** `barn/haybale-core/haybale_core/panels/node_props_panel.py` (NodeInfoPanel class)
- [ ] Migrate.
- [ ] Test, smoke, commit.

#### 16.5: NodePropertiesPanel (node focus)

- [ ] **Files:** `barn/haybale-core/haybale_core/panels/node_props_panel.py` (NodePropertiesPanel class — same file as 16.4; one commit covering both is acceptable)
- [ ] Migrate.
- [ ] Test, smoke. Commit covers both classes if migrated together.

#### 16.6: ExecutionStatisticsEdgePanel (edge focus)

- [ ] **Files:** `barn/haybale-core/haybale_core/panels/edge_panels.py` (`ExecutionStatisticsEdgePanel` class only — leave `EdgeErrorsPanel` and `EdgeWarningsPanel` on BasePanel for Phase 1.5; leave `DeleteEdgePanel` since it's context_menu-only)
- [ ] Migrate `ExecutionStatisticsEdgePanel`: `scopes="edge"` → `focus=EdgeFocus`.
- [ ] Test, smoke, commit.

#### 16.7: ConnectionPathEdgePanel (edge focus)

- [ ] **Files:** `barn/haybale-core/haybale_core/panels/edge_panels.py` (`ConnectionPathEdgePanel` class)
- [ ] Migrate.
- [ ] Test, smoke, commit.

#### 16.8: CanvasSettingsPanel (canvas focus)

- [ ] **Files:** `barn/haybale-core/haybale_core/panels/canvas_settings.py` (`CanvasSettingsPanel`)
- [ ] Migrate `scopes="canvas"` → `focus=CanvasFocus`.
- [ ] Test, smoke, commit.

#### 16.9: NodeSkinSettingsPanel (canvas focus)

- [ ] **Files:** `barn/haybale-core/haybale_core/panels/canvas_settings.py` (`NodeSkinSettingsPanel`)
- [ ] Migrate.
- [ ] Test, smoke, commit (combine with 16.8 if desired — they're in the same file).

#### 16.10: EdgeUISettingsPanel, EditorZoomPanSettingsPanel, MinimapSettingsPanel (canvas focus)

- [ ] **Files:** `barn/haybale-core/haybale_core/panels/canvas_settings.py` (remaining 3 classes)
- [ ] Migrate all three.
- [ ] Test, smoke, commit.

#### 16.11: GraphInfoPanel (graph focus)

- [ ] **Files:** `barn/haybale-core/haybale_core/panels/graph_info_panel.py`
- [ ] Migrate `scopes="graph"` → `focus=GraphFocus`.
- [ ] Test, smoke, commit.

#### 16.12: ExecutionSettingsPanel (execution focus, haybale-studio)

- [ ] **Files:** `barn/haybale-studio/haybale_studio/panels/execution_panel.py`
- [ ] Migrate `scopes="execution"` → `focus=ExecutionFocus`.
- [ ] Test, smoke, commit.

#### 16.13: DebugSettingsPanel (execution focus, haybale-studio)

- [ ] **Files:** `barn/haybale-studio/haybale_studio/panels/debug_panel.py`
- [ ] Migrate.
- [ ] Test, smoke, commit.

#### 16.14: ThemeSettingsPanel (app focus, haybale-studio)

- [ ] **Files:** `barn/haybale-studio/haybale_studio/panels/app_panels.py` (`ThemeSettingsPanel`)
- [ ] Migrate `scopes="app"` → `focus=AppFocus`.
- [ ] Test, smoke, commit.

#### 16.15: NodeSkinDefaultPanel, EditorSettingsPanel (app focus)

- [ ] **Files:** `barn/haybale-studio/haybale_studio/panels/app_panels.py` (remaining 2 classes)
- [ ] Migrate both.
- [ ] Test, smoke, commit.

#### After all 16 panels migrated

- [ ] **Run the full test suite**

Run: `uv run pytest tests/ -v 2>&1 | tail -30`
Expected: green.

- [ ] **Run integration tests**

Run: `uv run pytest tests/ -m integration -v 2>&1 | tail -10`
Expected: green.

- [ ] **Run quality suite**

Run: `uv run ruff check .`
Run: `uv run ruff format .`
Run: `uv run mypy packages/haywire-core/src/`
Expected: clean.

- [ ] **Comprehensive smoke test**

Run: `uv run haywire`. Walk through:
- App focus: theme, default skin, editor settings panels render.
- Execution focus: execution & debug settings render.
- Canvas focus: canvas, skin, edge UI, zoom-pan, minimap settings render.
- Graph focus: select a graph; graph info renders.
- Node focus: select a node; node ports, status, info, properties render.
- Settings focus: select a node; node settings render.
- Edge focus: select an edge; execution stats and connection path render. **EdgeErrors/EdgeWarnings still render via legacy path** (they're on BasePanel until Phase 1.5).
- Port focus: right-click a port; port info renders (legacy context-menu path).

Verify no regressions in any panel.

---

## Phase 1 Closeout

### Task 17: Update spec docs to reflect Phase 1 completion

**Files:**
- Modify: `docs/speculative/spec_panel_contract.md`
- Modify: `docs/speculative/spec_panel_migration.md`

- [ ] **Step 1: Update spec_panel_contract.md status**

Edit the header to note Phase 1 is implemented:

```markdown
> Status: Phase 1 implemented (2026-MM-DD). The contract (decorator, base class,
> registry methods, error trapping, lifecycle commitments, focus discovery)
> is in place. Reactive Subscriptions and auto-tracking are pending Phase 2.
```

- [ ] **Step 2: Update spec_panel_migration.md status**

Mark migrated panels as done; note remaining work for Phase 1.5.

- [ ] **Step 3: Commit**

```bash
git add docs/speculative/spec_panel_contract.md docs/speculative/spec_panel_migration.md
git commit -m "docs(spec): mark Phase 1 of panel-contract migration as complete"
```

---

### Task 18: Final verification

- [ ] **Step 1: All tests green**

Run: `uv run pytest tests/ -v 2>&1 | tail -30`
Expected: full green.

- [ ] **Step 2: Coverage check**

Run: `uv run pytest tests/ --cov=haywire.ui --cov-report=term-missing 2>&1 | tail -30`
Expected: coverage on new modules ≥ 90%.

- [ ] **Step 3: Type check**

Run: `uv run mypy packages/haywire-core/src/`
Expected: clean.

- [ ] **Step 4: Lint and format**

Run: `uv run ruff check .`
Run: `uv run ruff format .`
Expected: clean.

- [ ] **Step 5: Manual smoke test**

Run: `uv run haywire`. Click through all focus tabs. Verify all 16 migrated panels render correctly. Verify legacy panels (EdgeErrors/EdgeWarnings, all 14 context-menu panels) still work through the legacy path.

- [ ] **Step 6: Commit confirmation note (optional)**

Optional: tag the milestone.

```bash
git tag -a phase-1-panel-contract -m "Phase 1 of panel-contract migration complete"
```

---

## Phase 1 Done. Phase 1.5 begins.

Phase 1.5 scope (separate plan):
- Design `ContextMenuActions` Protocol from the verb audit.
- Migrate 14 context-menu panels.
- Resolve dual-host `EdgeErrorsPanel` / `EdgeWarningsPanel` via shared Protocol.
- Migrate DOM attributes from `data-hw-custom-menu-scope` to `data-hw-custom-menu-focus-id`.
- Lift gesture/popup state from `metadata` dict to provider properties or typed SessionContext fields.
- Cleanup: remove `BasePanel`, `register_scope`, `get_scopes`, `ScopeDescriptor`, `editors=`/`scopes=` decorator args, the legacy registry `_index` path, the dual-mount path in PropertiesEditor.
