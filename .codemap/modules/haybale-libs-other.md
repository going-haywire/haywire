# Module: haybale-libs-other (example / testing / TEST_A)

> Auxiliary haybale plugin libraries: an authoring example, a testing-only library, and a fixture for library-system tests.

**Path:** `barn/haybale-example/`, `barn/haybale-testing/`, `barn/haybale-TEST_A/`
**Language:** Python 3.10+
**Owner:** Various (bundled plugins)
**Tree hashes:** `ad4b7776cb469462c779abb6fe1e7c89b91c7348` / `41a98cec3ae7197fd5b9af5468533b22aaad211b` / `728840422d66a22446f0321ff9e012baac74a2ea`
**Mapped at:** 19bda1e (2026-07-05)

> ⚠️ `barn/haybale-visiongraph/` is now **gitignored** (`.gitignore:211`) and untracked in HEAD — it exists on disk as a local-only library and is no longer part of the committed repo. It is therefore dropped from this map's hash tracking.

---

## 1. Scope & Purpose

These libraries collectively demonstrate and exercise the library plugin system:

- **`haybale-example`** — minimal reference implementation; the "follow this template" library.
- **`haybale-testing`** — nodes/types used exclusively in the test suite (e.g., side-effect probes, deterministic timing).
- **`haybale-TEST_A`** — fixture/regression library for the library-system tests (e.g., naming collisions, hot-reload). The unusual name is intentional.

If you are documenting how to author a haybale library, point readers to `haybale-example` first.

## 2. Folder Architecture

```
barn/
├── haybale-example/
│   └── haybale_example/
│       ├── __init__.py       ← Library subclass
│       ├── adapters/         ← example adapters
│       ├── nodes/
│       │   ├── emits/        ← callback emitter nodes (custom_callback, emit_callback, merge_callback)
│       │   └── math_op.py
│       ├── skins/example_skin.py ← example skin
│       ├── types/            ← specs.py (Temperature), math.py, maps_string_type.py
│       └── widgets/          ← example_widget.py, knob_widget.py
│
├── haybale-testing/
│   └── haybale_testing/
│       ├── __init__.py       ← Library subclass
│       ├── nodes/
│       │   ├── testbed/      ← test-fixture nodes: settings, event queue-mode, group/section UI
│       │   ├── benchmark/    ← perf benchmark node fixtures
│       │   └── …
│       ├── settings/testing.py ← library-level TestingSettings (mirrored by settings_node.py)
│       └── panels/           ← test node panels
│
└── haybale-TEST_A/
    └── haybale_test_a/       ← library-system test fixture (version-bump only this refresh)
```

Each follows the standard layout: `__init__.py` exposes a `Library` subclass and registers components via `register_components()`.

## 3. Always-load vs On-demand

### Always-load

- The relevant library's `__init__.py` (just one when you know which lib you're working in).
- `haybale-example/README.md` when authoring a new library.

### On-demand

- **`haybale-testing/haybale_testing/nodes/testbed/settings_node.py`** + **`settings/testing.py`** — canonical example of the current `setting[IType]` generic form, `shadow()`/`watch()` mirrors, and the widget_config re-supply gotcha (see Rules).
- **`haybale-testing/haybale_testing/nodes/testbed/custom_callback_node.py`** — reference for wiring per-event-node `queue_mode` (`QueueMode.DROP`/`BLOCK`) into `CallbackEvent` for realtime frame-dropping (ADR 0010).
- **`haybale-example/haybale_example/widgets/`** — reference widgets (no longer declare `compatible_types=[...]` on `@widget()`; see Rules).
- **`haybale-testing/haybale_testing/panels/`** — test node panels with widget patterns.
- Other libraries' internals — only if you're changing a specific node, type, or test fixture.

## 4. Rules & Boundaries

- All three follow the same plugin contract as [haybale-core](haybale-core.md): register via `Library.register_components()`; entry point in `pyproject.toml`.
- `haybale-testing` and `haybale-TEST_A` are **not** for general use — keep production logic out of them.
- `haybale-TEST_A`'s name intentionally exercises identifier normalization; don't "fix" it.
- mypy roots: see root `pyproject.toml` `[tool.mypy]` and the CLAUDE.md mypy command — example/testing/TEST_A are included (visiongraph is no longer tracked/linted by default).
- **Primitive types/widgets import path moved**: `STRING`, `FLOAT`, `BOOL`, `INT`, `COLOR`, `VEC2I`/`VEC3F`/`VEC4F`, `CHOICES` and stock widgets (`TextWidget`, `SelectWidget`, `SwitchWidget`, `NumberWidget`) now live in `haywire.barn.builtin.types` / `haywire.barn.builtin.widgets`, not `haybale_core.types` / `haybale_core.widgets.basic_widgets`. `haybale_core.types` still owns structural types (`EXEC`, `CALLBACK`, `GROUP`, `PooledType`). All three libs updated their imports accordingly; keep new nodes consistent with this split.
- **`widget_key` prefix**: builtin widget keys changed from `core:widget:*` to `builtin:widget:*` (see `display_node.py`).
- **Settings generics**: `setting[str]`/`setting[int]`/etc. (bare Python types) are superseded by `setting[STRING]`/`setting[INT]`/etc. (IType generics); `choices=[...]` is now `widget_config={"options": [...]}`; `widget="color"` and `type_=` overrides are no longer needed/accepted. `shadow()`/`watch()` mirrors inherit the source's `IType` but **not** its `widget_config` — options-style config must be re-supplied at the mirror site (see `settings_node.py::mode`/`mode_ro`).
- `@widget(...)` no longer takes `compatible_types=[...]` — compatibility is resolved elsewhere now; don't add it back to new widgets.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Authoring template | `barn/haybale-example/haybale_example/__init__.py` | The "follow this" library |
| Test-only nodes | `barn/haybale-testing/haybale_testing/__init__.py` | Used by `tests/` |
| Library-system fixture | `barn/haybale-TEST_A/haybale_test_a/__init__.py` | Used by `tests/core/test_libraries` |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md).
- Most depend on [haybale-core](haybale-core.md) for shared types.

### Depended on by

- [tests](tests.md) — library-system and integration tests.
- [haywire-studio](haywire-studio.md) — discovers them as installed plugins when present.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugins | each lib's `__init__.py:Library` | Discovered via `haywire.libraries` entry point |
