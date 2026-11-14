# Module: haybale-haystack

> File-centric multi-graph manager plugin. A haystack is a set of related graph files owned by one workspace, with shared persistence, run settings and flow metering. It registers `GraphEntry` containers into `GraphAppState` for the graph editor to show.

**Path:** `barn/haybale-haystack/haybale_haystack/`
**Language:** Python 3.10+
**Owner:** Haywire core team (bundled plugin)
**Tree hash:** `9822bf3beebf6f86833e457b46afac6d293b8989`
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

`haybale-haystack` decides which graph files belong to a workspace and keeps them loaded, persisted and running in an orderly way. `GraphEntry` wraps one graph file as a `GraphContainer` (protocol in [haybale-graph-editor](haybale-graph-editor.md)) so the editor can open it. The library also owns the haystack editor, the haystack and graph-run settings, the flow meter (per-graph execution metering), the signals a haystack emits, and the `graph` and `macro` menu contributions in the graph panels. If this library were removed, the studio would have no multi-graph workspace, but single graphs could still be edited if the editor were opened directly.

## 2. Folder Architecture

```
haybale_haystack/
├── __init__.py          ← `Library` subclass
├── graph_entry.py       ← GraphEntry: GraphContainer implementation for one graph file
├── persistence.py       ← haystack file I/O (single owner of haystack file writes)
├── flow_meter.py        ← per-graph flow metering
├── signals.py           ← haystack signal definitions
├── editors/
│   └── haystack_editor.py ← haystack editor surface
├── panels/
│   ├── haystack_settings_panel.py
│   ├── file_browser/menu/file.py       ← file-browser menu contribution
│   ├── graph/menu/macro.py             ← graph-menu macro entries
│   └── properties/introspect/graph_run_settings_panel.py
├── settings/
│   ├── haystack_settings.py, graph_run_settings.py, flow_meter_settings.py
├── states/
│   └── haystack_state.py  ← haystack runtime state
├── farmhands/
│   └── graph_tools.py     ← Farmhand tools for graphs
└── haybale.toml           ← library manifest
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` and `register_components()`.
- `graph_entry.py` — the container every haystack graph is shown through.
- `persistence.py` — the only write path for haystack files.

### On-demand

- `editors/haystack_editor.py` — haystack editor UI.
- `settings/graph_run_settings.py` and `panels/properties/introspect/graph_run_settings_panel.py` — per-graph run settings.
- `flow_meter.py` and `settings/flow_meter_settings.py` — execution metering.
- `signals.py` — haystack events other libraries subscribe to.
- `panels/graph/menu/macro.py` — macro entries in the graph menu (see haywire-core `macro/`).
- `farmhands/graph_tools.py` — Farmhand tools for listing and operating on graphs.

## 4. Rules & Boundaries

- `persistence.py` is the single owner of haystack file I/O. Editors do not write haystack files directly.
- This library registers its containers through `GraphAppState` (see [haybale-graph-editor](haybale-graph-editor.md)). It does not own the editor.
- Register through `Library.register_components()`; entry point in `barn/haybale-haystack/pyproject.toml`.
- Tests: `tests/studio/test_haystack_editor_remove.py`, `tests/integration/test_haystack_carve_out.py`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Container for a graph file | `graph_entry.py` | `GraphEntry` (GraphContainer) |
| Haystack file I/O | `persistence.py` | Single owner |
| Haystack runtime state | `states/haystack_state.py` | Open files and their status |
| Haystack settings | `settings/haystack_settings.py` | Typed settings |

---

## Dependencies

### Depends on

- [haybale-graph-editor](haybale-graph-editor.md) — `GraphContainer`, `GraphAppState`, `GraphEditor`.
- [haybale-studio](haybale-studio.md) — file surface, file-browser state.
- [haybale-core](haybale-core.md) — shared types and widgets.
- [haywire-core-engine](haywire-core-engine.md) — macro, graph and session model.

### Depended on by

- [tests](tests.md) — `tests/studio/`, `tests/integration/`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | `haywire.libraries` entry point |
| Graph container | `graph_entry.py:GraphEntry` | Wraps one haystack graph file |
| Haystack editor | `editors/haystack_editor.py` | Multi-graph manager surface |
