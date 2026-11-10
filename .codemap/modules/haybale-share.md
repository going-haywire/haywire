# Module: haybale-share

> Editor-driven project publish for Haywire: a Share editor that runs the publish flow (dependencies, version, docs, commit, tag, push) for the current project.

**Path:** `barn/haybale-share/haybale_share/`
**Language:** Python 3.10+
**Owner:** Haywire core team (bundled plugin)
**Tree hash:** `c09cf21410b7fbe60c4c4a4380f9259bc5e95a7f`
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

`haybale-share` puts the project publish workflow into the studio UI. Its single Share editor walks the user through publishing the current project. The flow lives in `_flow/`, and the editor in `editors/`. The engine's publishing pipeline (`haywire_core/publishing`, `marketstall` share) and the studio's `haywire share` CLI do the underlying work. This library is the UI face of that pipeline. Removing it leaves publishing available only from the CLI.

## 2. Folder Architecture

```
haybale_share/
├── __init__.py   ← `Library` subclass
├── _flow/        ← publish flow steps and state (underscore: internal to the flow)
├── editors/      ← Share editor surface
├── py.typed
└── haybale.toml  ← library manifest
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` and `register_components()`.
- `editors/` — the Share editor.

### On-demand

- `_flow/` — the publish steps. Changes to publish order or preconditions go here, mirrored in the engine pipeline.

## 4. Rules & Boundaries

- Publish logic belongs in the engine (`haywire.core.publishing`) and the studio CLI, not in this library. This library only drives it.
- Publishing pushes to a remote. Keep every push and tag step behind the explicit user confirmation the flow already asks for.
- Register components through `Library.register_components()`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Publish flow | `_flow/` | Step order and state |
| Share editor | `editors/` | UI entry |
| Publish pipeline | `packages/haywire-core/src/haywire/core/publishing/` | ⚠️ Outside this module; engine owns the logic |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md) — `publishing/`, `marketstall`.
- [haywire-studio](haywire-studio.md) — `haywire share` CLI surface.
- [haybale-studio](haybale-studio.md) — studio editor surfaces.

### Depended on by

- [tests](tests.md) — `tests/share/`, `tests/share_flow/`, `tests/share_pipeline/`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | `haywire.libraries` entry point |
| Share editor | `editors/` | Publish UI |
| Publish flow | `_flow/` | Step pipeline |
