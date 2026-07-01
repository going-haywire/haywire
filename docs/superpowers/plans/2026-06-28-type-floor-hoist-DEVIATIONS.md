# Plan 1 (Type-Floor Hoist) — Landed-State Deviations

> Plans 2 and 3 MUST read this before their Task 0 verification gate.

## Type registry keys (actual)
- INT:    `builtin:type:INT`
- FLOAT:  `builtin:type:FLOAT`
- STRING: `builtin:type:STRING`
- BOOL:   `builtin:type:BOOL`
- VEC3F:  `builtin:type:VEC3F`   (VEC2I/3I/4I, VEC2F/4F follow the same pattern: `builtin:type:<CLASSNAME>`)
- COLOR:  `builtin:type:COLOR`

**Assumed:** `builtin:type:<CLASSNAME>`. **Actual:** as planned. The class-name segment
is the upper-case class name verbatim (no explicit `registry_id` override on any hoisted
or new type), so the key is `builtin:type:` + the exact class name.

## Decorator used for scalars
`@type` — the scalars (INT/FLOAT/STRING/BOOL) use the `@type` decorator imported from
`haywire.core.types` (i.e. `from haywire.core.types import type`). There is no
`@primitive_type`. Plans 2/3 add `widget_key=` defaults to this same `@type` decorator.

> NOTE on the `type` name clash: `vectors.py` and `color.py` import the decorator as
> `from haywire.core.types import type as type_decorator` and decorate with
> `@type_decorator(...)`. This was required because those modules also annotate a
> parameter `vec_cls: type` (the builtin `type`), and importing the decorator as `type`
> shadowed it, tripping mypy `[valid-type]`. `specs.py` keeps the bare `@type` name (it
> has no such annotation). If Plan 2 edits vectors/color decorators, use `type_decorator`,
> not `type`, in those two files.

## Builtin types export surface
`packages/haywire-core/src/haywire/barn/builtin/types/__init__.py` `__all__`:
```
"INT", "INTField", "FLOAT", "FLOATField", "STRING", "BOOL",
"VEC2I", "VEC3I", "VEC4I", "VEC2F", "VEC3F", "VEC4F",
"COLOR", "ColorStr",
```
These are the import names Plans 2/3 rely on. Import path: `haywire.barn.builtin.types`.
`ColorStr` (a `str` subclass) is the unwrapped element type behind `COLOR`.

## Basic adapter class names
In `haywire.barn.builtin.adapters.basic_adapters`:
- `IntToFloatAdapter`   (INT → FLOAT)
- `FloatToIntAdapter`   (FLOAT → INT)
- `FloatToStringAdapter` (FLOAT → STRING)
- `BoolToIntAdapter`    (BOOL → INT)

Registered keys: `builtin:adapter:<ClassName>`.

## haybale_core.types scalar re-exports
None — `barn/haybale-core/haybale_core/types/__init__.py` no longer exports INT/FLOAT/
STRING/BOOL (or INTField/FLOATField). It retains: `ArrayType`, `ArrayField`, `PooledType`,
`PooledField`, `GROUP`, `BYTES`, `LIST`, `DICT`, `EXEC`, `CALLBACK`. Plan 2's hard-cutover
import sweep does NOT need to clean stale re-exports here — the cutover is already complete.

## Other surprises encountered during Plan 1

1. **`LibraryIdentity` has three REQUIRED positional fields the plan's `@library` block
   omitted:** `url`, `help_url`, `author_url`. The builtin `@library(...)` decorator in
   `haywire/barn/builtin/__init__.py` had to supply all three (set to the project URLs,
   matching the core library). Any new bundled library must include them.

2. **`haywire.core.flow` does NOT exist.** The plan's vector/color snippets imported
   `from haywire.core.flow import FlowType`. The real location is `haywire.core.types`
   (`from haywire.core.types import FlowType, PrimitiveType`). `PrimitiveField` is also in
   `haywire.core.types`, not `haywire.core.types.fields` / `...base` as the plan guessed.

3. **MAJOR — bundled-library import path required a registry-loader change.** The plan
   pointed `core_libraries_path` at `haywire/barn/` and assumed the existing loader would
   import the library as `haywire.barn.builtin`. It did NOT: `_load_module_and_metadata`
   special-cased only the literal path `"src/haywire/libraries"` and otherwise imported a
   flat library under its **bare folder name** (`builtin`). That produced a SECOND, distinct
   module/class object — `discovered.library_cls is not haywire.barn.builtin.Library` — the
   classic "same name, distinct objects" hazard (CLAUDE.md). Types/adapters scanned under
   the bare-name module would have been distinct class objects from the `haywire.barn.builtin.*`
   imports used throughout the repo.

   **Fix landed in `packages/haywire-core/src/haywire/core/library/registry.py`:** added
   `LibraryRegistry._bundled_module_path(library_path)`, which detects any library located
   inside the installed `haywire` package tree and returns its real dotted import path
   (e.g. `haywire.barn.builtin`). `_load_module_and_metadata` now uses it as a second
   special-case branch (after the `src/haywire/libraries` one). Verified:
   `discovered.library_cls is haywire.barn.builtin.Library` → `True`, and the end-to-end
   integration test resolves `builtin:type:*` through the fully-bootstrapped registry.

   **Implication for Plans 2/3:** any further bundled libraries under `haywire/barn/` import
   correctly under their dotted name automatically — no extra wiring needed. Do not revert
   this loader change.

4. **`@library` `tags=` kwarg works** (passed through to `LibraryIdentity`), so the
   plan's `tags=["builtin", ...]` was fine.

5. **`registry_key` is computed at decoration time**, not at registration. It works because
   `derive_library_identity` walks `cls.__module__` up to `haywire.barn.builtin` (already in
   `sys.modules` when the type module imports) and reads `Library.class_identity.id`. No
   explicit registration call was needed in the key-assertion unit tests.

6. **End-to-end test uses the `library_system` fixture**, not a bare `TypeRegistry()`. The
   populated registry is obtained via `library_system.get_type_registry()` (the fixture is
   session-scoped, `@pytest.mark.integration`). A bare `TypeRegistry()` is empty.

## Verification status at end of Plan 1
- `ruff check .` — clean
- `ruff format --check .` — clean (694 files)
- full mypy gate (all 7 package roots) — clean (365 files)
- `pytest` (unit + integration) — 1905 passed, 5 skipped, 0 failures
- `uv run haywire` — boots clean; builtin library loads at Priority 1 with all 12
  `builtin:type:*` types and 4 `builtin:adapter:*` adapters registered, no errors.
