# Module: Haywire Studio

> CLI application package that composes `haywire-core` into the `haywire` executable. Owns app bootstrap, global/project TOML config, init scaffolding, the share CLI, and the studio workspace. Runtime library install/manage UI has moved out to the optional `haybale-marketplace` plugin.

**Path:** `packages/haywire-studio/src/haywire_studio/`
**Language:** Python 3.10+
**Owner:** Haywire studio team
**Tree hash:** `087438af63732dd1bd342783491c55fa978d07ea`
**Mapped at:** a08a6931 (2026-05-31)

---

## 1. Scope & Purpose

`haywire-studio` is the end-user application: it provides the `haywire` CLI entry point, boots a NiceGUI server, and loads installed haybale libraries. It glues `haywire-core` (engine + UI) to user-facing concerns: config files, init scaffolding, the share CLI, and the workspace that hosts haystack file groups. Note: runtime library install/browse UI is **no longer here** — it moved to the [haybale-marketplace](haybale-marketplace.md) plugin, and the install/share backend lives in engine `core/marketstall`.

## 2. Folder Architecture

```
haywire_studio/
├── __init__.py         ← exposes `main` (CLI entry point)
├── __main__.py         ← `python -m haywire_studio`
├── app.py              ← `HaywireApp` – top-level orchestrator
├── config.py           ← global + project TOML config readers/writers
├── init.py             ← CLI: `haywire init` scaffolding
├── share.py            ← CLI: `haywire share` (thin wrapper over core/marketstall/share)
└── workspace/          ← studio-specific workspace pieces
```

> Notes: the file-centric multi-graph registry now lives in [haybale-haystack](haybale-haystack.md); `library_manager.py` moved to [haybale-marketplace](haybale-marketplace.md); the share *backend* lives in [core/marketstall/share.py](haywire-core-engine.md) (this `share.py` is the CLI surface).

## 3. Always-load vs On-demand

### Always-load

- `app.py` — `HaywireApp` is the orchestrator; almost every studio task touches it.
- `__init__.py` — `main()` entry point; CLI argument routing.
- `config.py` — global vs project TOML resolution.

### On-demand

- `init.py`, `share.py` — only when modifying the corresponding CLI subcommands (`share.py` delegates to `core/marketstall/share.py`).
- `workspace/` — when changing how the studio mounts a workspace differently from core.

## 4. Rules & Boundaries

- This package depends on `haywire-core`, `haybale-core`, `haybale-studio`. Pulling in other haybale libs must go through the library discovery path, not direct imports.
- Library install/uninstall/browse UI belongs in [haybale-marketplace](haybale-marketplace.md), not here.
- Config: global TOML lives under the user config dir; project TOML lives in the project root. Both pass through `config.py` — do not parse TOMLs ad hoc. App-level state (enabled libs) is host.toml, owned by engine `core/host`.
- The `haywire` script is the only sanctioned launcher; tests don't spawn it as a subprocess except via `tests/test_init_scaffolding.py`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| CLI `haywire` entry | `__init__.py:main` | Defined in `pyproject.toml [project.scripts]` |
| App orchestrator | `app.py` (`HaywireApp`) | Boots NiceGUI + libraries |
| TOML config | `config.py` | Both global and project schemas |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md).
- [haybale-core](haybale-core.md), [haybale-studio](haybale-studio.md) — required at runtime.
- [haybale-marketplace](haybale-marketplace.md) — optional plugin discovered at runtime for library UI.

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
