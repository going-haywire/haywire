# Type-Floor Hoist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate the primitive type floor (scalars, vectors, color) and its basic adapters out of the `haybale-core` plugin into a framework-internal `builtin` library that loads before any plugin, so the framework owns its own types.

**Architecture:** Re-activate the dormant `load_core_libraries` capability in the library registry (Priority-1 load tier, currently disabled). Create a real `@library(id="builtin")` bundled inside the `haywire-core` package at `haywire/barn/builtin/`, holding the hoisted types/adapters. Registry keys derive from the library id, so moving types under `id="builtin"` automatically rekeys them `builtin:type:INT` (breaking the handful of existing graphs — accepted). `haybale-core` slims to its remaining plugin content.

**Tech Stack:** Python 3.10+, the haywire library/registry system (`BaseLibrary`, `TypeRegistry`, `AdapterRegistry`), `injector` DI, pytest, ruff, mypy.

---

## Scope

**This plan (Plan 1 of 3)** hoists ONLY the type floor + basic adapters and wires registration. It does NOT touch widgets (Plan 2) or the promote-setting-to-inlet feature (Plan 3). Plan 1 must produce a working, testable app on its own: graphs build, types resolve under their new keys, the app boots.

### What counts as "the floor" (decided)

The floor is the **self-contained primitive unit**: types whose conversions live entirely among themselves, plus the vector and color settings types being promoted to real ITypes.

| Hoists to `builtin` | Stays in `haybale-core` |
|---|---|
| `INT`, `FLOAT`, `STRING`, `BOOL` (from `specs.py`) | `GROUP`, `EXEC`, `CALLBACK` (flow/structural — not data floor) |
| New: `VEC2I/3I/4I`, `VEC2F/3F/4F`, `COLOR` (Plan 1 creates these as ITypes) | `BYTES`, `LIST`, `DICT` (primitives but not part of the settings/promotion floor; leave to avoid scope creep) |
| `basic_adapters.py` (INT↔FLOAT, FLOAT→STRING, BOOL→INT — all floor-internal) | `ArrayType`, `PooledType` (`array_type.py`, `pooled_type.py`) |
| | `compound_adapters.py` (operates on ArrayType) |
| | `nodes/`, `skins/`, `panels/`, `themes/`, `editors/` |

**Why `EXEC`/`CALLBACK` stay:** they are flow-control types, not data types a setting or a promoted inlet uses. Moving them is out of scope and would widen the blast radius into the execution engine.

**Why `BYTES/LIST/DICT` stay:** no setting declares them and they have no basic adapters among the floor; hoisting them buys nothing for Plans 2–3.

### The hard-cutover decision (carried into Plan 2)

`setting[FLOAT]` becoming mandatory and deleting Python-type inference is a **Plan 2** concern (it depends on widgets resolving by IType). Plan 1 only makes the ITypes *exist in the framework*; it does not rewrite any `setting[...]` declarations.

---

## File Structure

**New package — the bundled builtin library:**
- `packages/haywire-core/src/haywire/barn/__init__.py` — namespace marker (empty)
- `packages/haywire-core/src/haywire/barn/builtin/__init__.py` — the `@library(id="builtin")` class + `register_components()`
- `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py`
- `packages/haywire-core/src/haywire/barn/builtin/types/specs.py` — hoisted INT/FLOAT/STRING/BOOL
- `packages/haywire-core/src/haywire/barn/builtin/types/vectors.py` — new VEC* ITypes
- `packages/haywire-core/src/haywire/barn/builtin/types/color.py` — new COLOR IType
- `packages/haywire-core/src/haywire/barn/builtin/adapters/__init__.py`
- `packages/haywire-core/src/haywire/barn/builtin/adapters/basic_adapters.py` — hoisted basic adapters
- `packages/haywire-core/src/haywire/barn/builtin/py.typed`

**Modified — registration wiring:**
- `packages/haywire-core/src/haywire/core/di/config.py:148-156` — enable `load_core_libraries`, set `core_libraries_path`

**Modified — slim the plugin:**
- `barn/haybale-core/haybale_core/types/specs.py` — remove INT/FLOAT/STRING/BOOL
- `barn/haybale-core/haybale_core/adapters/basic_adapters.py` — delete (moved)
- `barn/haybale-core/haybale_core/types/__init__.py`, `adapters/__init__.py` — drop removed exports
- All in-repo imports `from haybale_core.types import FLOAT|INT|STRING|BOOL` → `from haywire.barn.builtin.types import ...`

**Tests:**
- `tests/barn/builtin/test_builtin_library_loads.py`
- `tests/barn/builtin/test_type_keys.py`
- `tests/barn/builtin/test_vectors_color.py`
- `tests/barn/builtin/test_basic_adapters.py`

---

## Pre-flight Baseline

- [ ] **Step 0: Establish the clean baseline**

Run:
```sh
uv run ruff check packages/haywire-core/src/ barn/haybale-core/
uv run mypy packages/haywire-core/src/ barn/haybale-core/haybale_core/
uv run pytest -m "not integration" -q
```
Expected: all clean (CLAUDE.md guarantees no pre-existing errors). If anything fails here, STOP and resolve interactively with the user before proceeding — post-edit failures must be attributable to this plan.

---

## Task 1: Create the empty `builtin` library skeleton that loads at Priority 1

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/__init__.py`
- Create: `packages/haywire-core/src/haywire/barn/builtin/__init__.py`
- Create: `packages/haywire-core/src/haywire/barn/builtin/py.typed`
- Modify: `packages/haywire-core/src/haywire/core/di/config.py:148-156`
- Test: `tests/barn/builtin/test_builtin_library_loads.py`

- [ ] **Step 1: Write the failing test**

`tests/barn/builtin/test_builtin_library_loads.py`:
```python
import haywire.core.graph.editor  # noqa: F401  # import first to avoid circular import (CLAUDE.md)

from haywire.barn.builtin import Library


def test_builtin_library_identity():
    """The bundled builtin library declares id='builtin'."""
    assert Library.class_identity.id == "builtin"


def test_builtin_library_is_baselibrary():
    from haywire.core.library.base import BaseLibrary

    assert issubclass(Library, BaseLibrary)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/barn/builtin/test_builtin_library_loads.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haywire.barn'`

- [ ] **Step 3: Create the namespace marker**

`packages/haywire-core/src/haywire/barn/__init__.py`:
```python
"""Framework-bundled libraries (loaded at Priority 1, before plugins)."""
```

`packages/haywire-core/src/haywire/barn/builtin/py.typed`: (empty file)

- [ ] **Step 4: Write the minimal library class**

`packages/haywire-core/src/haywire/barn/builtin/__init__.py`:
```python
"""Builtin Library — framework-owned primitive types, vectors, color, and their
basic adapters. Loaded at Priority 1 before any entry-point plugin so that
``builtin:type:*`` keys resolve when graphs and plugins reference them.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library


@library(
    label="Builtin",
    id="builtin",
    version="0.0.0",
    description="Framework-owned primitive types and adapters",
    author="maybites",
    dependencies=[],
    tags=["builtin", "types", "adapters"],
    file_watcher=False,
)
class Library(BaseLibrary):
    """Framework-internal builtin library."""

    def register_components(self):
        # Folders are added in later tasks (types, adapters).
        pass

    def validate(self) -> bool:
        return True
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/barn/builtin/test_builtin_library_loads.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Enable Priority-1 loading of the builtin library**

In `packages/haywire-core/src/haywire/core/di/config.py`, find lines 148-156:
```python
        # Core libraries are not used (loaded via pip entry points instead)
        library_registry.load_core_libraries = False

        # Enable pip package discovery (priority 2 & 3)
        library_registry.load_pip_packages = True

        # Add all configured library paths (priority 4)
        for path in self.library_paths:
            library_registry.add_library_root_path(path)
```

Replace the first two lines with:
```python
        # Builtin library (primitive types + basic adapters) ships inside the
        # haywire-core package and loads at Priority 1, before any plugin.
        from pathlib import Path
        import haywire.barn as _barn

        library_registry.load_core_libraries = True
        library_registry.core_libraries_path = str(Path(_barn.__file__).parent)

        # Enable pip package discovery (priority 2 & 3)
        library_registry.load_pip_packages = True
```
(Leave the `library_paths` loop unchanged.)

- [ ] **Step 7: Add an integration test that the registry actually loads it**

Append to `tests/barn/builtin/test_builtin_library_loads.py`:
```python
import pytest


@pytest.mark.integration
def test_builtin_library_discovered_at_priority_one():
    """The registry discovers the bundled builtin library via core_libraries_path."""
    from pathlib import Path
    import haywire.barn as barn
    from haywire.core.library.registry import LibraryRegistry

    reg = LibraryRegistry()
    reg.load_core_libraries = True
    reg.core_libraries_path = str(Path(barn.__file__).parent)

    discovered = reg._discover_core_libraries()
    ids = [d.identity.id for d in discovered]
    assert "builtin" in ids
```

- [ ] **Step 8: Run the integration test**

Run: `uv run pytest tests/barn/builtin/test_builtin_library_loads.py -v -m integration`
Expected: PASS. If `_discover_core_libraries` signature differs, read `packages/haywire-core/src/haywire/core/library/registry.py:559` and adapt the call — do not invent a method.

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/ tests/barn/builtin/test_builtin_library_loads.py packages/haywire-core/src/haywire/core/di/config.py
git commit -m "feat(types): bundle empty builtin library, load at Priority 1

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Hoist the scalar primitives (INT/FLOAT/STRING/BOOL) into `builtin`

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py`
- Create: `packages/haywire-core/src/haywire/barn/builtin/types/specs.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/__init__.py` (register the types folder)
- Test: `tests/barn/builtin/test_type_keys.py`

- [ ] **Step 1: Write the failing test**

`tests/barn/builtin/test_type_keys.py`:
```python
import haywire.core.graph.editor  # noqa: F401

from haywire.barn.builtin.types import INT, FLOAT, STRING, BOOL


def test_scalar_keys_are_builtin_namespaced():
    """Hoisted scalars derive a builtin:type:* key from the library id."""
    assert INT.class_identity.registry_key == "builtin:type:INT"
    assert FLOAT.class_identity.registry_key == "builtin:type:FLOAT"
    assert STRING.class_identity.registry_key == "builtin:type:STRING"
    assert BOOL.class_identity.registry_key == "builtin:type:BOOL"


def test_scalar_element_types():
    assert FLOAT.element_type_cls is float
    assert INT.element_type_cls is int
    assert STRING.element_type_cls is str
    assert BOOL.element_type_cls is bool
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/barn/builtin/test_type_keys.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haywire.barn.builtin.types'`

- [ ] **Step 3: Move the scalar type definitions**

Read the current source: `barn/haybale-core/haybale_core/types/specs.py:40-152` (the `INT`, `INTField`, `FLOAT`, `FLOATField`, `STRING`, `BOOL` classes).

Create `packages/haywire-core/src/haywire/barn/builtin/types/specs.py` containing EXACTLY those six classes (INT, INTField, FLOAT, FLOATField, STRING, BOOL), copied verbatim, with their `@type(...)`/`@primitive_type(...)` decorators. Update the import header at the top of the new file to pull `PrimitiveType`, `PrimitiveField` from their real homes:
```python
from haywire.core.types.base import PrimitiveType
from haywire.core.types.fields import PrimitiveField
from haywire.core.types.decorator import type  # or primitive_type — match the original decorator used
```
(Read the original file's imports and decorator names; replicate them. Do NOT change the class bodies or decorator kwargs — the `registry_id` defaults to the class name, and the `builtin` namespace is supplied by the owning library at scan time.)

`packages/haywire-core/src/haywire/barn/builtin/types/__init__.py`:
```python
from .specs import INT, INTField, FLOAT, FLOATField, STRING, BOOL

__all__ = ["INT", "INTField", "FLOAT", "FLOATField", "STRING", "BOOL"]
```

- [ ] **Step 4: Register the types folder in the builtin library**

In `packages/haywire-core/src/haywire/barn/builtin/__init__.py`, replace `register_components`:
```python
    def register_components(self):
        from haywire.core.types.registry import TypeRegistry

        base_path = Path(__file__).parent
        self.add_folder_to_registry(
            folder_path=str(base_path / "types"), registry_cls=TypeRegistry
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/barn/builtin/test_type_keys.py -v`
Expected: PASS (2 tests). If `registry_key` is computed lazily (only after registration), the test may need the library's `register_components()` run first; if so, read how `barn/haybale-core`'s own type tests assert keys (search `tests/` for `registry_key` assertions on types) and mirror that setup. Do not fabricate a registration call.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/types/ packages/haywire-core/src/haywire/barn/builtin/__init__.py tests/barn/builtin/test_type_keys.py
git commit -m "feat(types): hoist INT/FLOAT/STRING/BOOL into builtin library

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Add VEC* vector ITypes (new — promoting settings vec types)

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/types/vectors.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py`
- Test: `tests/barn/builtin/test_vectors_color.py`

**Background:** `Vec2i/3i/4i/2f/3f/4f` are framework-defined classes in
`packages/haywire-core/src/haywire/core/settings/types.py` (`Vec3f(list)` etc., with
`VecMeta(length, element_type, labels)` in `_VEC_META`). Per the design, vectors become
real ITypes as `PrimitiveType[Vec_]` wrappers (the `Vec_` class is the unwrapped value),
with `VecMeta` carried as widget metadata. This is layering-clean (the `Vec_` classes
already live in the framework).

- [ ] **Step 1: Write the failing test**

`tests/barn/builtin/test_vectors_color.py`:
```python
import haywire.core.graph.editor  # noqa: F401

from haywire.barn.builtin.types import VEC3F, VEC2I
from haywire.core.settings.types import Vec3f, Vec2i


def test_vec3f_key_and_element_type():
    assert VEC3F.class_identity.registry_key == "builtin:type:VEC3F"
    assert VEC3F.element_type_cls is Vec3f


def test_vec2i_key_and_element_type():
    assert VEC2I.class_identity.registry_key == "builtin:type:VEC2I"
    assert VEC2I.element_type_cls is Vec2i
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/barn/builtin/test_vectors_color.py -v`
Expected: FAIL with `ImportError: cannot import name 'VEC3F'`

- [ ] **Step 3: Implement the vector ITypes**

First read an existing `@type`-decorated `PrimitiveType` subclass to copy the exact decorator
kwarg shape: `barn/haybale-core/haybale_core/types/specs.py:73` (the FLOAT class).

`packages/haywire-core/src/haywire/barn/builtin/types/vectors.py`:
```python
"""Vector ITypes — PrimitiveType wrappers over the framework Vec_ classes.

VecMeta (length, element_type, component labels) is attached via widget metadata
so the vec editor renders X/Y/Z component fields.
"""

from haywire.core.flow import FlowType
from haywire.core.types.base import PrimitiveType
from haywire.core.types.decorator import type
from haywire.core.settings.types import (
    Vec2i, Vec3i, Vec4i, Vec2f, Vec3f, Vec4f, get_vec_meta,
)


def _vec_default(vec_cls: type) -> dict:
    meta = get_vec_meta(vec_cls)
    zero = 0 if meta.element_type is int else 0.0
    return {"value": [zero] * meta.length}


@type(flow_type=FlowType.DATA, label="Vec2i", description="2D integer vector",
      default=_vec_default(Vec2i))
class VEC2I(PrimitiveType[Vec2i]):
    """2D integer vector."""


@type(flow_type=FlowType.DATA, label="Vec3i", description="3D integer vector",
      default=_vec_default(Vec3i))
class VEC3I(PrimitiveType[Vec3i]):
    """3D integer vector."""


@type(flow_type=FlowType.DATA, label="Vec4i", description="4D integer vector",
      default=_vec_default(Vec4i))
class VEC4I(PrimitiveType[Vec4i]):
    """4D integer vector."""


@type(flow_type=FlowType.DATA, label="Vec2f", description="2D float vector",
      default=_vec_default(Vec2f))
class VEC2F(PrimitiveType[Vec2f]):
    """2D float vector."""


@type(flow_type=FlowType.DATA, label="Vec3f", description="3D float vector",
      default=_vec_default(Vec3f))
class VEC3F(PrimitiveType[Vec3f]):
    """3D float vector."""


@type(flow_type=FlowType.DATA, label="Vec4f", description="4D float vector",
      default=_vec_default(Vec4f))
class VEC4F(PrimitiveType[Vec4f]):
    """4D float vector."""
```
**Verify before relying on it:** confirm `from haywire.core.flow import FlowType` is the correct import (grep `class FlowType`); confirm the `@type` decorator accepts `flow_type=` and `default=` by reading `barn/haybale-core/haybale_core/types/specs.py:73`. Adjust kwargs to match the FLOAT example exactly. If `@type` requires a `widget_key`, omit it here — that is Plan 2's job; Plan 1 only needs the types to exist and key correctly.

- [ ] **Step 4: Export the vectors**

Update `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py`:
```python
from .specs import INT, INTField, FLOAT, FLOATField, STRING, BOOL
from .vectors import VEC2I, VEC3I, VEC4I, VEC2F, VEC3F, VEC4F

__all__ = [
    "INT", "INTField", "FLOAT", "FLOATField", "STRING", "BOOL",
    "VEC2I", "VEC3I", "VEC4I", "VEC2F", "VEC3F", "VEC4F",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/barn/builtin/test_vectors_color.py::test_vec3f_key_and_element_type tests/barn/builtin/test_vectors_color.py::test_vec2i_key_and_element_type -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/types/ tests/barn/builtin/test_vectors_color.py
git commit -m "feat(types): add VEC2/3/4 i/f vector ITypes to builtin

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Add the COLOR IType (promoted from the `Color = str` alias)

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/types/color.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py`
- Test: `tests/barn/builtin/test_vectors_color.py` (extend)

**Background:** `Color = str` today (a bare alias, no class). The design promotes Color to its
own IType. Because `PrimitiveType[Color]` would collapse to `PrimitiveType[str]` (since
`Color is str`), COLOR must wrap a distinct `str` subclass.

- [ ] **Step 1: Write the failing test**

Append to `tests/barn/builtin/test_vectors_color.py`:
```python
def test_color_is_its_own_type():
    from haywire.barn.builtin.types import COLOR, ColorStr

    assert COLOR.class_identity.registry_key == "builtin:type:COLOR"
    # COLOR wraps a real str subclass, NOT plain str, so it is distinct from STRING.
    assert issubclass(ColorStr, str)
    assert COLOR.element_type_cls is ColorStr
    assert COLOR.element_type_cls is not str
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/barn/builtin/test_vectors_color.py::test_color_is_its_own_type -v`
Expected: FAIL with `ImportError: cannot import name 'COLOR'`

- [ ] **Step 3: Implement COLOR**

`packages/haywire-core/src/haywire/barn/builtin/types/color.py`:
```python
"""COLOR IType — a distinct str subclass so a color port is type-separable from STRING.

The color picker widget is wired in Plan 2 (widget unification); Plan 1 only
establishes the type.
"""

from haywire.core.flow import FlowType
from haywire.core.types.base import PrimitiveType
from haywire.core.types.decorator import type


class ColorStr(str):
    """Hex/rgba color string. A str subclass so COLOR != STRING at the type level."""


@type(flow_type=FlowType.DATA, label="Color", description="Hex or rgba color string",
      color="#f7b0ff", default={"value": "#ffffff"})
class COLOR(PrimitiveType[ColorStr]):
    """Color data type."""
```
(Match the `@type` kwargs to the FLOAT example; adjust if `color=`/`default=` differ.)

- [ ] **Step 4: Export COLOR**

Update `__init__.py` to add `from .color import COLOR, ColorStr` and include both in `__all__`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/barn/builtin/test_vectors_color.py::test_color_is_its_own_type -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/types/ tests/barn/builtin/test_vectors_color.py
git commit -m "feat(types): add COLOR IType as a distinct str subclass

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Hoist the basic adapters

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/adapters/__init__.py`
- Create: `packages/haywire-core/src/haywire/barn/builtin/adapters/basic_adapters.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/__init__.py` (register adapters folder)
- Test: `tests/barn/builtin/test_basic_adapters.py`

- [ ] **Step 1: Write the failing test**

`tests/barn/builtin/test_basic_adapters.py`:
```python
import haywire.core.graph.editor  # noqa: F401


def test_int_to_float_adapter_exists_and_converts():
    from haywire.barn.builtin.adapters.basic_adapters import IntToFloatAdapter

    # Adapter name may differ; read the source. Assert the conversion result.
    adapter = IntToFloatAdapter()
    assert adapter.convert(3) == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/barn/builtin/test_basic_adapters.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Move basic_adapters.py**

Read `barn/haybale-core/haybale_core/adapters/basic_adapters.py` in full. Copy it to
`packages/haywire-core/src/haywire/barn/builtin/adapters/basic_adapters.py` verbatim, then
change its type import:
```python
# was: from ..types.specs import BOOL, FLOAT, INT, STRING
from haywire.barn.builtin.types import BOOL, FLOAT, INT, STRING
```
Adjust the test's class name (`IntToFloatAdapter`) to the actual class name in the file. Keep
all `@adapter(converts_from=..., converts_to=...)` decorators unchanged.

`packages/haywire-core/src/haywire/barn/builtin/adapters/__init__.py`: (empty — the folder scan picks up the module)

- [ ] **Step 4: Register the adapters folder**

In `packages/haywire-core/src/haywire/barn/builtin/__init__.py` `register_components`, add after the types registration:
```python
        from haywire.core.adapter.registry import AdapterRegistry

        self.add_folder_to_registry(
            folder_path=str(base_path / "adapters"), registry_cls=AdapterRegistry
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/barn/builtin/test_basic_adapters.py -v`
Expected: PASS (after correcting the class name)

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/adapters/ packages/haywire-core/src/haywire/barn/builtin/__init__.py tests/barn/builtin/test_basic_adapters.py
git commit -m "feat(types): hoist basic adapters into builtin library

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Remove the hoisted types/adapters from `haybale-core`

**Files:**
- Modify: `barn/haybale-core/haybale_core/types/specs.py` (remove INT/FLOAT/STRING/BOOL + their Field classes)
- Delete: `barn/haybale-core/haybale_core/adapters/basic_adapters.py`
- Modify: `barn/haybale-core/haybale_core/types/__init__.py`, `adapters/__init__.py`

**Warning:** This is the breaking step. After it, anything importing `from haybale_core.types import FLOAT|INT|STRING|BOOL` breaks until Task 7 rewrites them.

- [ ] **Step 1: Remove the four scalar classes from the plugin's specs.py**

In `barn/haybale-core/haybale_core/types/specs.py`, delete the `INT`, `INTField`, `FLOAT`,
`FLOATField`, `STRING`, `BOOL` class definitions (lines 40-152 in the current file). Leave
`GROUP`, `BYTES`, `LIST`, `DICT`, `EXEC`, `CALLBACK` intact. `CALLBACK(STRING)` now needs
its base: change its import/base to pull STRING from the builtin:
```python
from haywire.barn.builtin.types import STRING
```
(at the top of the plugin's specs.py).

- [ ] **Step 2: Delete the moved adapter file**

Run:
```bash
git rm barn/haybale-core/haybale_core/adapters/basic_adapters.py
```

- [ ] **Step 3: Fix the plugin's type/adapter `__init__.py` exports**

In `barn/haybale-core/haybale_core/types/__init__.py`, remove exports of INT/FLOAT/STRING/BOOL
(and re-export from builtin only if other plugin code imports them via `haybale_core.types` —
prefer rewriting those call sites in Task 7 instead).

In `barn/haybale-core/haybale_core/adapters/__init__.py`, remove any import of `basic_adapters`.

- [ ] **Step 4: Run type-check to surface every broken import**

Run: `uv run mypy barn/haybale-core/haybale_core/`
Expected: errors listing every site that imported the removed names. Record them — Task 7 fixes them. Do NOT commit yet (repo is in a broken intermediate state).

---

## Task 7: Rewrite all in-repo imports to the builtin location

**Files:**
- Modify: every file flagged by Task 6 Step 4 (in `barn/`, `packages/`, and `tests/`)

- [ ] **Step 1: Find every stale import**

Run:
```bash
grep -rln "from haybale_core.types import" barn/ packages/ tests/ | xargs grep -l "FLOAT\|INT\|STRING\|BOOL" 2>/dev/null
grep -rn "from ..types.specs import\|from ...types.specs import" barn/haybale-core/
```

- [ ] **Step 2: Rewrite each import**

For every flagged file, change the scalar imports from the plugin to the builtin:
```python
# from: from haybale_core.types import FLOAT, INT, STRING, BOOL
from haywire.barn.builtin.types import FLOAT, INT, STRING, BOOL
```
Where a file imports BOTH builtin scalars AND plugin-retained types (e.g. `EXEC`, `ArrayType`)
in one line, split into two imports — builtin scalars from `haywire.barn.builtin.types`,
the rest from `haybale_core.types`.

This is a string-reference sweep; the `/check-rename` skill is designed to catch
`patch("...")`, `importlib.import_module`, and doc citations the IDE misses. Run it after the
mechanical pass.

- [ ] **Step 3: Re-run type-check and lint clean**

Run:
```bash
uv run mypy packages/haywire-core/src/ barn/haybale-core/haybale_core/
uv run ruff check packages/haywire-core/src/ barn/haybale-core/
```
Expected: clean. Fix any remaining stale references.

- [ ] **Step 4: Run the full non-integration suite**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS. Failures here are almost certainly stale string-based type-key assertions
(`"core:type:INT"` → `"builtin:type:INT"`); update them to the new key.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(types): repoint imports from haybale_core to haywire.barn.builtin

BREAKING: scalar/vec/color type keys are now builtin:type:* (was core:type:*).
Existing graphs referencing core:type:* will not load.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: End-to-end verification — app boots, types resolve, integration green

**Files:**
- Test: `tests/barn/builtin/test_floor_end_to_end.py`

- [ ] **Step 1: Write an integration test that a graph builds with builtin types**

`tests/barn/builtin/test_floor_end_to_end.py`:
```python
import pytest

import haywire.core.graph.editor  # noqa: F401


@pytest.mark.integration
def test_builtin_types_resolve_through_registry():
    """After full init, the type registry resolves builtin:type:* keys."""
    from haywire.core.types.registry import TypeRegistry

    reg = TypeRegistry()
    assert reg.get_type_class("builtin:type:INT") is not None
    assert reg.get_type_class("builtin:type:FLOAT") is not None
    assert reg.get_type_class("builtin:type:COLOR") is not None
    assert reg.get_type_class("builtin:type:VEC3F") is not None
```
If `TypeRegistry()` is not a standalone-constructable singleton, read how existing integration
tests obtain the populated registry (search `tests/` for `get_type_class`) and mirror that
fixture. Do not invent a constructor.

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/barn/builtin/test_floor_end_to_end.py -v -m integration`
Expected: PASS

- [ ] **Step 3: Run the FULL suite (unit + integration)**

Run: `uv run pytest -q`
Expected: PASS. Re-enabling `load_core_libraries` is a global init change — watch for failures
in marketplace library enumeration or dep-detection that assumed `load_core_libraries=False`.
If any appear, read the failing test and reconcile (the builtin library is now an expected
member of the loaded set).

- [ ] **Step 4: Boot the real app to confirm**

Run: `uv run haywire` (let it start, confirm no import/registration errors in the log, then stop it).
Expected: clean startup; the builtin library appears in the loaded-libraries log at Priority 1.

- [ ] **Step 5: Full quality gate**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest -q
```
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add tests/barn/builtin/test_floor_end_to_end.py
git commit -m "test(types): end-to-end verification of builtin type floor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Handoff — record actual outcomes & divergences for Plans 2 and 3

Plans 2 and 3 were written against the *assumptions* in this plan. Reality may differ
(decorator names, registry constructor shapes, renamed classes, the exact key format). This
task captures what actually landed so the downstream plans verify against fact, not assumption.

**Files:**

- Create: `docs/superpowers/plans/2026-06-28-type-floor-hoist-DEVIATIONS.md`

- [ ] **Step 1: Probe the landed state**

Run each probe and record the real answer:
```bash
# 1. Exact key format that actually got assigned
uv run python -c "import haywire.core.graph.editor; from haywire.barn.builtin.types import INT, FLOAT, STRING, BOOL, VEC3F, COLOR; \
print('INT', INT.class_identity.registry_key); print('FLOAT', FLOAT.class_identity.registry_key); \
print('STRING', STRING.class_identity.registry_key); print('BOOL', BOOL.class_identity.registry_key); \
print('VEC3F', VEC3F.class_identity.registry_key); print('COLOR', COLOR.class_identity.registry_key)"

# 2. Which decorator the hoisted scalars actually use
grep -n "^@type\|^@primitive_type" packages/haywire-core/src/haywire/barn/builtin/types/specs.py

# 3. Final export surface (names Plans 2/3 will import)
grep -n "__all__" -A 12 packages/haywire-core/src/haywire/barn/builtin/types/__init__.py

# 4. The actual basic-adapter class names (Plan 2/3 may reference them)
grep -n "^class .*Adapter\|@adapter" packages/haywire-core/src/haywire/barn/builtin/adapters/basic_adapters.py

# 5. Did haybale_core.types keep re-exporting any scalars? (Plans assume NOT)
grep -n "FLOAT\|INT\|STRING\|BOOL" barn/haybale-core/haybale_core/types/__init__.py || echo "no scalar re-exports (as planned)"
```

- [ ] **Step 2: Write the deviations file**

Create `docs/superpowers/plans/2026-06-28-type-floor-hoist-DEVIATIONS.md` using this template,
filling EVERY field from Step 1's output. If a value matches the plan's assumption, write
"as planned"; if not, write the actual value and a one-line note on the consequence:

```markdown
# Plan 1 (Type-Floor Hoist) — Landed-State Deviations

> Plans 2 and 3 MUST read this before their Task 0 verification gate.

## Type registry keys (actual)
- INT:    <actual key>
- FLOAT:  <actual key>
- STRING: <actual key>
- BOOL:   <actual key>
- VEC3F:  <actual key>   (and VEC2I/3I/4I, VEC2F/4F follow the same pattern: <pattern>)
- COLOR:  <actual key>

**Assumed:** `builtin:type:<CLASSNAME>`. **Actual:** <as planned | deviation + consequence>

## Decorator used for scalars
<@type | @primitive_type>  — Plans 2/3 use this when adding `widget_key=` defaults.

## Builtin types export surface
<paste the __all__ list>  — these are the import names Plans 2/3 rely on.

## Basic adapter class names
<list>  — referenced if Plan 2/3 touch adapter↔type wiring.

## haybale_core.types scalar re-exports
<none | list>  — if any survived, Plan 2's hard-cutover import sweep must also clean them.

## Other surprises encountered during Plan 1
<free text: renamed classes, registry constructor signatures that differed from the test
caveats, integration tests that needed reconciling for load_core_libraries=True, etc.
Anything an executor of Plan 2/3 would be wrong to assume away.>
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-06-28-type-floor-hoist-DEVIATIONS.md
git commit -m "docs(plan): record Plan 1 landed-state deviations for Plans 2 and 3

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review Notes (for the executing engineer)

- **Key-format assumption:** the plan assumes `registry_key = "{library_id}:type:{ClassName}"` (verified: `reg_key()` builds `f"{id}:{module}:{class_id}"`, module `"type"`). If a hoisted type sets an explicit `registry_id`, the class-name segment changes — read each `@type` decorator before asserting a key. **Whatever lands, Task 9 records it.**
- **`@type` vs `@primitive_type`:** the original scalars may use `@primitive_type`. Replicate whichever decorator the source uses; both set `class_identity`. Task 9 records which.
- **Out of scope (do NOT do here):** rewriting `setting[float]` → `setting[FLOAT]` (Plan 2), wiring `widget_key` defaults onto types (Plan 2), deleting `compatible_types` (Plan 2), any promote-to-inlet work (Plan 3).
- **The `core:type:*` → `builtin:type:*` break is intentional and accepted** (handful of graphs at this stage). No migration is written.
- **Plan 1 ends by writing `…-DEVIATIONS.md` (Task 9).** Plans 2 and 3 begin by reading it (their Task 0). That file is the contract between the plans.
