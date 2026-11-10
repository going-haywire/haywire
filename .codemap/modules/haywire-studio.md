# Module: Haywire Studio

> CLI application package that composes `haywire-core` into the `haywire` executable. Owns app bootstrap, global/project TOML config, init scaffolding, the auth/login gate, network and TLS setup, Farmhand/MCP host wiring, security posture, the docs and rename/share/verify/deps CLIs, and the studio workspace.

**Path:** `packages/haywire-studio/src/haywire_studio/`
**Language:** Python 3.10+
**Owner:** Haywire studio team
**Tree hash:** `81feaf694f950d4b3dfd276b19deb1bec3303f26` (part of packages/haywire-studio)
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

`haywire-studio` is the end-user application. It provides the `haywire` CLI entry point, boots the NiceGUI server through `HaywireApp`, and loads installed haybale libraries. It glues `haywire-core` (engine and UI) to user-facing concerns: config files, project scaffolding, authentication (roster, login gate, cookies, eviction), network and TLS, the Farmhand MCP endpoint, security posture, docs generation, rename, share, verify and deps checks, and volumes. Runtime library install/browse UI is **not** here: it lives in the optional [haybale-marketplace](haybale-marketplace.md) plugin, and the install/share backend lives in engine `core/marketstall` ([haywire-core-engine](haywire-core-engine.md)).

## 2. Folder Architecture

```
src/haywire_studio/
├── __init__.py / __main__.py ← CLI entry (`main`) and `python -m haywire_studio`
├── app.py                    ← HaywireApp: top-level orchestrator (boot, libraries, sessions)
├── config.py                 ← global + project TOML readers/writers
├── init.py                   ← `haywire init` scaffolding
├── playbook.py               ← playbook text/steps
├── publish_workflow.py       ← publish workflow (library directory builds, --dev roots)
├── code_intelligence.py      ← jedi-backed code intelligence for editors
├── error_hooks.py            ← error hooks wired into the ledger
├── auth/                     ← login gate: gate, login, live, operations, passwords, cookies, eviction
├── security/                 ← security document, roster, posture, operations, errors
├── network/                  ← TLS/certs, IP filter, names, tls_operations
├── farmhand/                 ← Farmhand (MCP) host, auth, identity
├── workspace/                ← studio workspace pieces
├── cli/                      ← subcommands: init, docs, rename, share, verify, user, auth,
│                               network, ssl, security, volumes, farmhand, deps, _guards
└── packaging/                ← build/publish-time helpers
    ├── docs/                 ← docs model, extract, generate, render
    ├── rename/               ← rename planner, checks, discovery, execute, graphs, pysource, report
    ├── deps.py, verify.py    ← dependency and verification checks
    └── share_cli.py          ← `haywire share` surface
```

## 3. Always-load vs On-demand

### Always-load

- `app.py` — `HaywireApp`; nearly every studio task touches it.
- `__init__.py` — `main()` CLI routing.
- `config.py` — global vs project TOML resolution.

### On-demand

- `auth/` and `security/` — login, roster, sessions, posture. Read with the auth ADR (0027) in `docs/adr`.
- `network/` — TLS and bind/IP filtering.
- `farmhand/` — MCP endpoint host (see `.insights/INDEX.md` for traps).
- `cli/` — one file per subcommand. Read the subcommand's file and `cli/_guards.py`.
- `packaging/rename/` — `haywire rename`: JSON-aware library rename with dry-run graph patching.
- `packaging/docs/` — `haywire docs` generator.
- `publish_workflow.py` — library publish flow.
- `init.py` — `haywire init` scaffolding.

## 4. Rules & Boundaries

- Depends on `haywire-core`, `haybale-core`, `haybale-studio`. Other haybale libs load through library discovery, never by direct import.
- Library install, uninstall and browse UI belongs in [haybale-marketplace](haybale-marketplace.md).
- Config: global TOML lives in the user config dir, project TOML in the project root. Both go through `config.py`; do not parse TOML ad hoc. App-level state (enabled libs) is `host.toml`, owned by engine `core/host`.
- The `haywire` script is the sanctioned launcher. Tests spawn it as a subprocess only in `tests/test_init_scaffolding.py`.
- Rename CLI logic belongs under `packaging/rename/`, not the marketplace editor.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| CLI `haywire` entry | `__init__.py:main` | Declared in `pyproject.toml [project.scripts]` |
| App orchestrator | `app.py` (`HaywireApp`) | Boots NiceGUI and libraries |
| TOML config | `config.py` | Global and project schemas |
| Login roster | `security/roster.py`, `auth/operations.py` | Who may log in |
| Security posture | `security/posture.py`, `security/document.py` | Startup-read controls |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md).
- [haybale-core](haybale-core.md), [haybale-studio](haybale-studio.md) — required at runtime.
- [haybale-marketplace](haybale-marketplace.md) — optional plugin discovered at runtime.

### Depended on by

- [tests](tests.md) — `tests/studio/`, `tests/farmhand/`, `tests/test_init_scaffolding.py`.
- End users via the `haywire` CLI.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| `haywire` CLI | `__init__.py:main` | `[project.scripts]` |
| `python -m haywire_studio` | `__main__.py` | Same as above without the script alias |
| App boot | `app.py:HaywireApp` | NiceGUI server and library loading |
| `haywire init` | `init.py` | Scaffolds a project tree |
| `haywire rename` | `cli/rename.py` → `packaging/rename/` | Library rename with graph patching |
| `haywire share` | `cli/share.py` → `packaging/share_cli.py` | Export and share flows |
| `haywire docs` | `cli/docs.py` → `packaging/docs/` | Library docs generator |
| Farmhand MCP host | `farmhand/host.py` | Serves `/mcp` |
