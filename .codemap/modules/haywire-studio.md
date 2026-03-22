# Module: haywire-studio

**Path:** `packages/haywire-studio/src/haywire_studio/`
**Import as:** `haywire_studio`
**CLI entry:** `uv run haywire` → `haywire_studio:main`

---

## Scope & Purpose

The application package. Bootstraps the DI container, starts the NiceGUI web server,
manages the per-session page lifecycle, and provides the top-level graph and library
management services. Also exposes CLI subcommands (`init`, `share`).

This package is intentionally thin — it wires together `haywire.core` + `haywire.ui` +
the haybale plugin libraries, but contains no node definitions or UI panel logic itself
(those live in `haybale-studio`).

---

## Folder Architecture

```
haywire_studio/
├── __init__.py
├── __main__.py             # python -m haywire_studio entry
├── app.py                  # HaywireApp — main application class (~500 lines)
│                           # - create_haywire_injector() wiring
│                           # - NiceGUI server setup
│                           # - main_page() per-session setup
│                           # - setup_shared_services()
├── config.py               # Global + project TOML config (paths, startup, etc.)
├── graph_manager.py        # GraphManager + GraphEntry dataclass
│                           # - create_untitled() — '__untitled__' at startup
│                           # - open_graph(path, factory)
│                           # - save_graph(entry, save_as=None)
│                           # - session_attach/detach(entry, session_id)
├── library_manager.py      # Runtime library install + library management UI
├── init.py                 # `haywire init` CLI subcommand (project scaffolding)
└── share.py                # `haywire share` CLI subcommand
```

---

## Always-load vs On-demand

**Always-load**:
- `app.py` — understand `HaywireApp`, `main_page()`, and `setup_shared_services()` before
  touching any wiring or startup behaviour
- `config.py` — understand config file paths and startup options
- `graph_manager.py` — understand `GraphManager`/`GraphEntry` before touching graph lifecycle

**On-demand**:
- `library_manager.py` — only when working on runtime library install/management UI
- `init.py` / `share.py` — only when working on CLI subcommands

---

## Rules & Boundaries

- **DI wiring lives here**: `app.py` calls `create_haywire_injector()` and registers
  app-level editors via `_editor_registry._register_class()` in `setup_shared_services()`.
- **Graph lifecycle**: `GraphManager` is the source of truth for which graphs are open
  and which sessions are attached to them. Never create graph instances outside of it.
- **Untitled graph**: Created as `'__untitled__'` at startup by `create_untitled(factory)`.
  `broadcast_data_mutation(graph_path=None)` broadcasts to all sessions for the untitled graph.
- **Session attachment**: `main_page()` attaches each new browser session to the untitled
  entry at startup. `FileBrowserEditor` detaches from previous and attaches to opened graph.
- **Active graph path**: Tracked in `SessionContext.active_graph_path` (None = untitled).
- **Library paths default to `[]`** — must be explicitly provided in app or test DI config.
- **App-level editors** are registered in `setup_shared_services()`, not via entry points.

---

## Source of Truth

| Concern | File |
|---------|------|
| App bootstrap + DI wiring | `app.py` — `HaywireApp` |
| Config paths | `config.py` |
| Graph open/save/attach | `graph_manager.py` — `GraphManager` |
| Library runtime install | `library_manager.py` |

---

## Depends on

- [core-engine.md](core-engine.md) — DI container, graph, library APIs
- [core-ui.md](core-ui.md) — AppShell, SessionManager, WorkspaceManager, editors/panels

## Depended on by

Nothing — this is the top-level application entry point.
