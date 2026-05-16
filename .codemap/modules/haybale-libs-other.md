# Module: haybale-libs-other (example / testing / visiongraph / TEST_A)

> Auxiliary haybale plugin libraries: an authoring example, a testing-only library, a vision/graph integration, and a fixture for library-system tests.

**Path:** `barn/haybale-example/`, `barn/haybale-testing/`, `barn/haybale-visiongraph/`, `barn/haybale-TEST_A/`
**Language:** Python 3.10+
**Owner:** Various (bundled plugins)
**Tree hashes:** see [META.md](../META.md)
**Mapped at:** b2e5340b (2026-05-16)

---

## 1. Scope & Purpose

These libraries collectively demonstrate and exercise the library plugin system:

- **`haybale-example`** — minimal reference implementation; the "follow this template" library.
- **`haybale-testing`** — nodes/types used exclusively in the test suite (e.g., side-effect probes, deterministic timing).
- **`haybale-visiongraph`** — integration with visiongraph / OpenCV-based vision processing nodes.
- **`haybale-TEST_A`** — fixture/regression library for the library-system tests (e.g., naming collisions, hot-reload). The unusual name is intentional.

If you are documenting how to author a haybale library, point readers to `haybale-example` first.

## 2. Folder Architecture

```
barn/
├── haybale-example/      haybale_example/     ← README + nodes/types
├── haybale-testing/      haybale_testing/     ← test-only nodes
├── haybale-visiongraph/  haybale_visiongraph/ ← visiongraph integration
└── haybale-TEST_A/       haybale_test_a/      ← library-system test fixture
```

Each follows the standard layout: `__init__.py` exposes a `Library` subclass and registers components via `register_components()`.

## 3. Always-load vs On-demand

### Always-load

- The relevant library's `__init__.py` (just one when you know which lib you're working in).
- `haybale-example/README.md` when authoring a new library.

### On-demand

- Other libraries' internals — only if you're changing a specific node, type, or test fixture there.

## 4. Rules & Boundaries

- All four follow the same plugin contract as [haybale-core](haybale-core.md): register via `Library.register_components()`; entry point in `pyproject.toml`.
- `haybale-testing` and `haybale-TEST_A` are **not** for general use — keep production logic out of them.
- `haybale-TEST_A`'s name intentionally exercises identifier normalization; don't "fix" it.
- mypy roots: see root `pyproject.toml` `[tool.mypy]` and the CLAUDE.md mypy command — all four are included.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Authoring template | `barn/haybale-example/haybale_example/__init__.py` | The "follow this" library |
| Test-only nodes | `barn/haybale-testing/haybale_testing/__init__.py` | Used by `tests/` |
| Library-system fixture | `barn/haybale-TEST_A/haybale_test_a/__init__.py` | Used by `tests/core/test_libraries` |
| Vision integration | `barn/haybale-visiongraph/haybale_visiongraph/__init__.py` | OpenCV-touching code |

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
