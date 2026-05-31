# Module: haybale-haystack

> File-centric multi-graph manager for Haywire — lets a single workspace own a "haystack" of related graph files with shared persistence and signals.

**Path:** `barn/haybale-haystack/haybale_haystack/`
**Language:** Python 3.10+
**Owner:** Haywire studio team (bundled plugin)
**Tree hash:** `73d73f00b120b5140f992547f83004cd5e047c28`
**Mapped at:** a08a6931 (2026-05-31)

---

## 1. Scope & Purpose

`haybale-haystack` is the bundled plugin that handles multi-graph file management. It replaces the old in-studio `haystack.py` and isolates persistence, the graph-file registry, and haystack-specific editors/panels from the studio shell. Use it when working on opening/saving multiple graphs, the haystack editor, or persistence semantics.

It is a **source library** for `GraphEditor`: `GraphEntry` is the haystack-flavoured implementation of the `GraphContainer` protocol, and the library `register`s / `unregister`s / `rekey`s its open entries into [`GraphAppState`](haybale-graph-editor.md) so `GraphEditor` (which lives in `haybale-graph-editor`) can resolve a `binding_id` to a live container. Haystack does not own the editor — it owns the containers.

## 2. Folder Architecture

```
haybale_haystack/
├── __init__.py       ← Library entry (BaseLibrary subclass)
├── graph_entry.py    ← per-file graph entry model
├── persistence.py    ← read/write haystack files
├── signals.py        ← haystack-scoped signal vocabulary
├── editors/          ← haystack editor
├── panels/           ← haystack-related panels
├── settings/         ← haystack settings
└── state/            ← haystack state container
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library.register_components()`.
- `persistence.py` — canonical read/write surface; almost every haystack task touches it.
- `graph_entry.py` — the per-file model used by editors and panels.

### On-demand

- `editors/` — when changing the haystack editor UI; pair with `haywire/ui/editor/wrapper.py`.
- `signals.py` — when emitting/listening to haystack-scoped events.
- `state/` — when modifying mutable haystack state.

## 4. Rules & Boundaries

- Persistence path is the single owner of haystack file I/O — do not write haystack files from editors directly.
- Must register through `Library.register_components()`; entry point declared in `barn/haybale-haystack/pyproject.toml`.
- Test reference: `tests/studio/test_haystack_editor_remove.py`, `tests/integration/test_haystack_carve_out.py`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Haystack file format | `persistence.py` | Read/write entry point |
| Per-file model | `graph_entry.py` | `GraphContainer` implementation; registered into `GraphAppState` |
| Haystack signals | `signals.py` | Scoped vocabulary |
| Library entry | `__init__.py` | `haystack = "haybale_haystack:Library"` |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md).
- [haybale-core](haybale-core.md), [haybale-studio](haybale-studio.md).
- [haybale-graph-editor](haybale-graph-editor.md) — `GraphAppState` registry, `GraphContainer` protocol, `GraphEditor` surface; `GraphEntry` implements the protocol and the library registers entries on open/close.

### Depended on by

- [haywire-studio](haywire-studio.md) — uses haystack as default multi-graph manager.
- [tests](tests.md) — `tests/integration/test_haystack_carve_out.py`, `tests/studio/test_haystack_*`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | `haywire.libraries` entry point named `haystack` |
| File I/O | `persistence.py` | Read/write a haystack file |
