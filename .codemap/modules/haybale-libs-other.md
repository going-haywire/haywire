# Module: haybale-libs-other (example / testing / TEST_A)

> Auxiliary haybale plugin libraries: an authoring example, a testing-only library, and a fixture for library-system tests.

**Path:** `barn/haybale-example/`, `barn/haybale-testing/`, `barn/haybale-TEST_A/`
**Language:** Python 3.10+
**Owner:** Various (bundled plugins)
**Tree hashes:** `aac17609a94449af6ac9befb55a8fa33cc41ced0` / `e9c4c353edbb3ebfed55aa128a0155a99207469e` / `07a979e8ef318a2da1210d2f1693d26b0a5a4f57`
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

These libraries exercise and demonstrate the plugin system:

- **`haybale-example`** — minimal reference implementation; the "follow this template" library. Contains adapters, catalog entries, macros, nodes, types and widgets.
- **`haybale-testing`** — nodes, types, panels, settings, state, surfaces, themes and widgets used only by the test suite. Includes `wires.py`.
- **`haybale-TEST_A`** — fixture and regression library for library-system tests (naming collisions, hot-reload). The unusual name is intentional.

To document how to author a haybale library, point readers to `haybale-example` first.

## 2. Folder Architecture

```
barn/
├── haybale-example/
│   └── haybale_example/
│       ├── __init__.py   ← Library subclass
│       ├── adapters/     ← example adapters
│       ├── catalog/      ← catalog entries
│       ├── macros/       ← example macros
│       ├── nodes/        ← example nodes (e.g. math_op)
│       ├── types/        ← example types (Temperature, maps-string)
│       ├── widgets/      ← example widgets
│       └── haybale.toml
│
├── haybale-testing/
│   └── haybale_testing/
│       ├── __init__.py   ← Library subclass
│       ├── adapters/, farmhands/, nodes/, panels/, settings/, states/,
│       │   surfaces/, themes/, types/, widgets/
│       ├── wires.py      ← test wire helpers
│       └── haybale.toml
│
└── haybale-TEST_A/
    └── haybale_test_a/
        ├── __init__.py, nodes/, types/, widgets/
        └── haybale.toml
```

Each library follows the standard layout: `__init__.py` exposes a `Library` subclass that registers components via `register_components()`.

## 3. Always-load vs On-demand

### Always-load

- The relevant library's `__init__.py`, and only the one you are working in.

### On-demand

- `haybale-example/nodes/`, `types/`, `widgets/` — when writing a new node, type or widget from a template.
- `haybale-example/macros/`, `catalog/` — when working on macro or catalog examples.
- `haybale-testing/nodes/` — test-fixture nodes (side-effect probes, deterministic timing, benchmark fixtures). Read the test that uses them first.
- `haybale-testing/settings/`, `states/`, `panels/` — test settings and state fixtures.
- `haybale-TEST_A/` — library-system regression fixtures. Change only with the matching library-system test.

## 4. Rules & Boundaries

- Test-only nodes and fixtures stay in `haybale-testing` and `haybale-TEST_A`. Production libraries must not import them.
- `haybale-example` is documentation by code. Keep it correct and minimal.
- `haybale-TEST_A` names are load-bearing for collision tests. Do not rename them casually; run `check-rename` after any rename.
- Register components through `Library.register_components()`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Authoring template | `haybale-example/haybale_example/__init__.py` | Start point for new libraries |
| Test fixtures | `haybale-testing/haybale_testing/` | Used by `tests/` |
| Collision fixtures | `haybale-TEST_A/haybale_test_a/` | Used by library-system tests |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md).
- [haybale-core](haybale-core.md) — shared types (haybale-example, haybale-testing).

### Depended on by

- [tests](tests.md) — `tests/barn/`, `tests/libraries/`, `tests/execution/`, and others that load these fixtures.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Example library | `haybale-example/haybale_example/__init__.py:Library` | Authoring template |
| Testing library | `haybale-testing/haybale_testing/__init__.py:Library` | Test fixtures |
| Fixture library | `haybale-TEST_A/haybale_test_a/__init__.py:Library` | Collision fixtures |
