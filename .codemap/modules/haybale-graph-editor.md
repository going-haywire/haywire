# Module: haybale-graph-editor

> Provides the visual graph editor surface (`GraphEditor`) decoupled from any specific graph source. Defines the `GraphContainer` protocol that source libraries implement, and the `GraphAppState` registry that maps `binding_id` → `GraphContainer` so the editor can resolve its tab to a live container.

**Path:** `barn/haybale-graph-editor/haybale_graph_editor/`
**Language:** Python 3.10+
**Owner:** Haywire studio team (bundled plugin)
**Tree hash:** `49ead920cde1cd306348edc762e472529f36cc70`
**Mapped at:** 4e5c1da7 (2026-05-31)

---

## 1. Scope & Purpose

`haybale-graph-editor` is the visual graph editor as a standalone plugin. It owns the `GraphEditor` surface (canvas + chrome + save-as dialog) and exposes a *source-agnostic* contract: any library can host a graph in `GraphEditor` by (a) implementing the `GraphContainer` protocol structurally and (b) registering its open containers into `GraphAppState`. `haybale-haystack`'s `GraphEntry` is the reference implementation, but cloud-graph or alternative storage libraries can register their own containers without touching this library.

Use it when working on the graph editor UI itself, the container/registry contract, or when adding a new source library that needs to drive `GraphEditor`.

## 2. Folder Architecture

```
haybale_graph_editor/
├── __init__.py        ← Library entry, public re-exports
├── protocols.py       ← GraphContainer Protocol
├── editors/           ← GraphEditor (canvas + chrome + save-as dialog)
└── state/             ← GraphAppState registry (binding_id → GraphContainer)
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` and `register_components()`; public re-exports of `GraphContainer`, `GraphAppState`, `GraphEditor`.
- `protocols.py` — `GraphContainer` Protocol; the contract every source library must satisfy.
- `state/graph_app_state.py` — `GraphAppState` registry; `register` / `unregister` / `rekey`.

### On-demand

- `editors/graph_editor.py` — when changing the editor UI, save flow, or canvas wiring.

## 4. Rules & Boundaries

- `GraphAppState` holds *references* only — owning libraries control container lifecycle (create / discard).
- `binding_id` is the persistent identifier (workspace-serializable); the container is the runtime cache and must not be persisted on its behalf.
- This library does not know which source produced any given container — never special-case `GraphEntry` here.
- Must register through `Library.register_components()`; entry point declared in `barn/haybale-graph-editor/pyproject.toml`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Container protocol | `protocols.py` | `binding_id`, `editor`, `path`, `unsaved`, `display_name`, `save()` |
| App-wide registry | `state/graph_app_state.py` | `app_data[GraphAppState]`; keyed by `binding_id` |
| Editor surface | `editors/graph_editor.py` | `GraphEditor` (`opens='on_payload'`) |
| Library entry | `__init__.py` | `graph_editor = "haybale_graph_editor:Library"` |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md) — `BaseEditor`, `AppState`, `Reveal`/`Close` signals, session context.
- [haywire-studio](haywire-studio.md) — workspace metadata for save paths.
- [haybale-studio](haybale-studio.md) — `GraphCanvasManager`, `EditState`.

### Depended on by

- [haybale-haystack](haybale-haystack.md) — registers `GraphEntry` containers; reveals `GraphEditor` for haystack graphs.
- Future graph-management libraries by the same pattern.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | `haywire.libraries` entry point named `graph_editor` |
| Container protocol | `protocols.py:GraphContainer` | Structural contract for graph hosts |
| App registry | `state/graph_app_state.py:GraphAppState` | `binding_id` → `GraphContainer` map |
| Editor | `editors/graph_editor.py:GraphEditor` | The graph editor surface |
