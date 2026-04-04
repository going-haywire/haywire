# Module: haywire-studio

**Path:** `packages/haywire-studio/src/haywire_studio/`
**Import as:** `haywire_studio`
**CLI entry:** `uv run haywire` → `haywire_studio:main`

---

## Scope & Purpose

The CLI application package. Wires together `haywire.core` (DI, graph engine) and `haywire.ui`
(NiceGUI shell), provides the `haywire` CLI command, and manages global config, multi-graph
file registry, and runtime library installation. Also owns workspace defaults.

---

## Folder Architecture

```
haywire_studio/
├── __init__.py
├── __main__.py                 # python -m haywire_studio entry
├── app.py                      # HaywireApp — main application class
├── config.py                   # Global + project TOML config
├── graph_manager.py            # GraphManager — file-centric multi-graph registry
├── library_manager.py          # LibraryManager — runtime library install/UI
├── init.py                     # `haywire init` CLI subcommand
├── share.py                    # `haywire share` CLI subcommand
└── workspace/
    ├── __init__.py
    └── defaults.py             # WorkspaceDefaults — default layout/editor config
```

---

## Always-load vs On-demand

**Always-load**:
- `app.py` — understand HaywireApp bootstrap, DI wiring, NiceGUI startup
- `config.py` — where/how TOML settings are loaded (global vs project)
- `graph_manager.py` — multi-graph file system model

**On-demand**:
- `library_manager.py` — only when working on runtime library install/UI
- `init.py` / `share.py` — only when working on CLI subcommands
- `workspace/defaults.py` — only when working on default workspace layouts

---

## Rules & Boundaries

- **CLI entry point only** — this package should not export reusable library APIs.
- **Config hierarchy**: global (`~/.haywire/settings.toml`) → project (`.haywire/settings.toml`).
  Managed by `config.py`; do not bypass this for settings resolution.
- **GraphManager is file-centric** — each open graph corresponds to a `.haywire` file; the
  manager handles load/save/close lifecycle.
- **workspace/defaults.py** owns the default editor/panel layout for new sessions —
  change here when adding new default-visible editors.
- No direct NiceGUI import in `config.py` or `graph_manager.py` — only `app.py` and `workspace/`
  should touch NiceGUI directly.

---

## Source of Truth

| Concern | File |
|---------|------|
| App bootstrap & DI wiring | `app.py` |
| TOML config resolution | `config.py` |
| Multi-graph file registry | `graph_manager.py` |
| Runtime library install | `library_manager.py` |
| Default workspace layout | `workspace/defaults.py` |

---

## Depends on

- [core-engine.md](core-engine.md) — DI container, graph engine, library registry
- [core-ui.md](core-ui.md) — HaywireAppShell, editor/panel/workspace registries

## Depended on by

Nothing — this is the top-level application package.
