# Module: Haywire Studio

> CLI application package that composes `haywire-core` into the `haywire` executable. Owns app bootstrap, global/project TOML config, the file-centric haystack registry, and runtime library install/manage UI.

**Path:** `packages/haywire-studio/src/haywire_studio/`
**Language:** Python 3.10+
**Owner:** Haywire studio team
**Tree hash:** `32290f54f1e21c75972b6712c4e7576c2bbd360f`
**Mapped at:** b2e5340b (2026-05-16)

---

## 1. Scope & Purpose

`haywire-studio` is the end-user application: it provides the `haywire` CLI entry point, boots a NiceGUI server, loads installed haybale libraries, and exposes runtime UI for managing them. It glues `haywire-core` (engine + UI) to user-facing concerns: config files, init scaffolding, share/export, and the workspace that hosts haystack file groups.

## 2. Folder Architecture

```
haywire_studio/
├── __init__.py         ← exposes `main` (CLI entry point)
├── __main__.py         ← `python -m haywire_studio`
├── app.py              ← `HaywireApp` (~500 lines) – top-level orchestrator
├── config.py           ← global + project TOML config readers/writers
├── init.py             ← CLI: `haywire init` scaffolding
├── library_manager.py  ← runtime library install/UI (pip wrap + reload)
├── share.py            ← CLI: `haywire share` (export/share flows)
└── workspace/          ← studio-specific workspace pieces
```

> Note: the file-centric multi-graph registry (`haystack.py`) referenced in `CLAUDE.md` now lives in [haybale-haystack](haybale-haystack.md). The studio focuses on app/config/library-manager.

## 3. Always-load vs On-demand

### Always-load

- `app.py` — `HaywireApp` is the orchestrator; almost every studio task touches it.
- `__init__.py` — `main()` entry point; CLI argument routing.
- `config.py` — global vs project TOML resolution.

### On-demand

- `library_manager.py` — when working on install/uninstall/reload UI for libraries.
- `init.py`, `share.py` — only when modifying the corresponding CLI subcommands.
- `workspace/` — when changing how the studio mounts a workspace differently from core.

## 4. Rules & Boundaries

- This package depends on `haywire-core`, `haybale-core`, `haybale-studio`. Pulling in other haybale libs must go through the library discovery path, not direct imports.
- Keep `app.py` close to its current size (~500 lines). Split into helpers before it grows further.
- Config: global TOML lives under the user config dir; project TOML lives in the project root. Both pass through `config.py` — do not parse TOMLs ad hoc.
- The `haywire` script is the only sanctioned launcher; tests don't spawn it as a subprocess except via `tests/test_init_scaffolding.py`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| CLI `haywire` entry | `__init__.py:main` | Defined in `pyproject.toml [project.scripts]` |
| App orchestrator | `app.py` (`HaywireApp`) | Boots NiceGUI + libraries |
| TOML config | `config.py` | Both global and project schemas |
| Library install UI | `library_manager.py` | Wraps pip + library reload |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md).
- [haybale-core](haybale-core.md), [haybale-studio](haybale-studio.md) — required at runtime.

### Depended on by

- [tests](tests.md) — `tests/studio/` and `tests/test_init_scaffolding.py`.
- End users via the `haywire` CLI command.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| `haywire` CLI | `__init__.py:main` | `pyproject.toml` `[project.scripts]` |
| `python -m haywire_studio` | `__main__.py` | Same as above without script alias |
| App boot | `app.py:HaywireApp` | NiceGUI server + library loading |
| `haywire init` | `init.py` | Scaffolds a new project tree |
| `haywire share` | `share.py` | Export/share flows |
