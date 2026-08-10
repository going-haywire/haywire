---
status: draft
doc_template: canonical-example
scope: The haybale-marketplace plugin — the optional library installer/browser haybale, its editors, its manager + marketplace states, and the optionality contract that lets the studio run without it
see-also:
  - haybale-marketplace-arch.md
  - ../haybale-canon.md
  - ../../architecture/library-system/library-system-arch.md
  - ../../adr/0001-haybale-marketplace-carveout.md
  - ../../reference/glossary.md
---

# Library Marketplace — Canonical Example

## 1. What it solves

**`haybale-marketplace`** is the optional haybale package that gives the studio its in-app *library manager*: the surface where a user browses, installs, enables, disables, inspects, and uninstalls haywire libraries. It is the consumer-facing arm of the marketstall runtime (`haywire.core.marketstall`) — the runtime resolves catalogs; this plugin renders them and drives `uv pip install`.

It is the **Library Manager** of the glossary's "five meanings of library" (meaning **#4**, see [reference/glossary §Library — five distinct meanings](../../reference/glossary.md#library-five-distinct-meanings)). It is *not* the Library System (meaning #2, the runtime that loads `Library` classes) and *not* a `Library` itself in the authoring sense (meaning #1) — though it ships *as* a haybale package and registers like any other plugin.

The plugin was carved out of `haybale-studio` per [ADR-0001](../../adr/0001-haybale-marketplace-carveout.md). The load-bearing property is **optionality**: a derivative project can ship a Haywire build with no marketplace UI, or swap in a different installer, without touching the studio runtime. `haywire init` installs it by default, so the default user experience is unchanged.

## 2. How it fits

```text
haywire.core.marketstall          haybale-marketplace             haybale-studio
────────────────────────          ───────────────────             ──────────────
the runtime:                      the plugin (this doc):          the host studio:
 parse / refresh / resolve        - 3 editors (browser,            provides the editor
 marketplace + marketstall          overview, component)           slots (action/edit/context)
 files into a Haybale catalog       + flow helper modules          into which the editors
                          ◀──────  - MarketplaceState              self-register.
                                    - LibraryManager (+            If haybale-marketplace
                                      LibraryManagerState)         is absent, the ACTION slot
                                  - farmhands (MCP tools)          is simply empty — no
                                  - drives uv pip install          defensive code needed.
       LibraryRegistry  ◀──────── manager.registry.enable/
       (core) owns                 disable_library(id);
       enable/disable              registry persists via
       persistence via HostStore   host.toml
```

The plugin owns **no registry state and no runtime parsing**. It calls `MarketplaceState` for catalog data (which wraps `haywire.core.marketstall`) and `LibraryManager` for install verbs (which shells out to `uv` and asks the Library System to rescan). Enable/disable persistence belongs to the core `LibraryRegistry`, not the plugin.

**Boundaries.** *How* the editors, refresh pipeline, two-tier marketplace files, conflict resolution, and `InstallType`-gated actions work — see [haybale-marketplace-arch](haybale-marketplace-arch.md). *Why* the marketplace/marketstall trust model is shaped the way it is — see [haybale-marketplace-arch §8](haybale-marketplace-arch.md#8-why-the-model-is-shaped-this-way). What a haybale author writes, and how one is packaged and published — see [haybale-canon](../haybale-canon.md).

## 3. What the plugin ships

`barn/haybale-marketplace/haybale_marketplace/` registers three component categories from its `Library.register_components()`: states (via `LibraryStateRegistry`), farmhands (via `FarmhandRegistry`), and editors (via `EditorTypeRegistry`). **State is scanned first** — both the farmhand tools and the editor modules transitively import the state classes, and scanning them first keeps a single class object live (the same ordering rule `haybale-studio` follows).

### Editors

| Editor | Default slot | Role |
|---|---|---|
| `LibraryBrowserEditor` | `ACTION` | Lists installed + available libraries, grouped REQUIRED / ENABLED / DISABLED / AVAILABLE. Burger menu: Refresh, Add Source…, Edit File…. |
| `LibraryOverviewEditor` | `EDIT` | One library's identity, component breakdown, and Edit / Enable / Disable / Uninstall / Install actions. |
| `LibraryComponentEditor` | `CONTEXT` | Detail view for one component (node/type/widget/…) — import snippet, port-wiring hints. |

The multi-step flows each live in their own subpackage beside the editors
(`_add_source_flow/`, `_install_flow/`, `_refresh_flow/`, `_uninstall_flow/`),
with `_overview_actions.py`, `_overview_edit_dialog.py` and
`_overview_install_flow.py` holding the Overview editor's verbs. None of these
are registered editors — they are helper modules the editors call.

### Farmhands (MCP tools)

`farmhands/` registers into `FarmhandRegistry`: `catalog_tools.py` (list
available, refresh, fetch library docs) and `install_tools.py` (dry-run
install, install, uninstall). These are the marketplace verbs exposed to an
agent over MCP.

### Publishing a project — not this plugin

**Publishing lives in `haybale-share`'s `ShareEditor`, not here.** This plugin
*consumes* feeds; producing one is a different concern, and project-scoped
publishing (ADR 0023) has nothing to do with the per-library view the browser
presents. There is no Share Project item in the burger menu — its items are
Refresh, Add Source…, and Edit File….

What a subscriber needs to know about the other side: `haywire share` publishes
the whole project — every `barn/*` library bumped to the same version
(lockstep), docs regenerated, `marketstall.toml` rebuilt, committed, tagged
`v<version>`, and pushed. The commands are in
[haybale-canon](../haybale-canon.md#quick-reference); the pipeline is in
[share-pipeline-arch](../../architecture/sharing/share-pipeline-arch.md).

The share URL is always branch-live — it tracks whatever branch you published
from, because `marketstall.toml` is a subscription feed and a frozen, tag-pinned
URL would lock subscribers to whatever version they first subscribed to.

### States

| State | Kind | Owns |
|---|---|---|
| `MarketplaceState` | `AppState` | Marketplace orchestration for one session — wraps `haywire.core.marketstall` (`get_global()`, `get_project_haybales()`, `refresh()`, `remove_stale_haybale()`). The UI never calls marketstall functions directly. |
| `LibraryManagerState` | `AppState` | A thin holder publishing the `LibraryManager` so other editors reach it via `ctx.app_data[LibraryManagerState].manager.X`. |

### The `LibraryManager` service

`LibraryManager` (`library_manager.py`) is a **plain class, not an `AppState`** — it owns the install / uninstall / enable / disable / edit-identity verbs. Composition over inheritance: its constructor takes `(registry, project_dir)`, which an `AppState`'s bare `cls()` instantiation can't supply, so `LibraryManagerState` resolves those from the DI context in `on_enable()` and holds the manager. See [ADR-0001 §Why composition](../../adr/0001-haybale-marketplace-carveout.md).

## 4. Important concepts

**Optionality is the whole point.** Editors self-register into slots via `EditorTypeRegistry`. If `haybale-marketplace` is not installed, the left-slot library browser simply doesn't appear; `haybale-studio` carries no `if marketplace_present:` branches. This is what makes the carve-out worth its one extra `.manager.` indirection — a build can omit or replace the installer cleanly.

**Persistence lives in the core registry, not here.** "Which libraries are disabled" is a property of the `LibraryRegistry`, not the installer. The editors call `manager.registry.enable_library(id)` / `disable_library(id)`; the registry writes through to `HostStore` (`<workspace>/.haywire/host.toml`, `[libraries] disabled`). There is no marketplace-owned persistence and no `AppState` in the enable/disable path. See [ADR-0001 §Why persistence moves out](../../adr/0001-haybale-marketplace-carveout.md).

**It depends on `haybale-studio`, not the reverse.** `haybale-marketplace`'s `pyproject.toml` declares `haywire-core`, `haywire-studio` and `haybale-studio` (plus `nicegui`, `toml`, `packaging`) as dependencies — it consumes the studio's slots and editor base classes. `haybale-studio` declares no dependency on the marketplace; the relationship is strictly one-directional, which is what preserves optionality.

**`file_watcher=True`.** The plugin enables hot-reload like any editable haybale — edit an editor and the studio re-renders without restart (editable install only). Its entry point, `marketplace = "haybale_marketplace:Library"`, is declared like any other haybale's.

## 5. Live example from the codebase

Source: `barn/haybale-marketplace/haybale_marketplace/__init__.py` — pulled in
live, so it cannot drift from the code:

```python
--8<-- "barn/haybale-marketplace/haybale_marketplace/__init__.py:marketplace_library"
```

It registers like any other haybale, and its descriptive metadata lives beside
it in `haybale.toml` — see [haybale-canon](../haybale-canon.md) for the
authoring surface both share.

What this example exercises, beyond the ordinary:

| Concept | Where |
|---|---|
| A standalone optional plugin registering studio UI | the whole package |
| Three registry categories: states, farmhands, editors | three `add_folder_to_registry` calls |
| State-before-farmhands-before-editors scan ordering | comment in `register_components` |
| Hot-reload for an editable plugin | `file_watcher=True` |

---

## Quick reference

### What lives where

| Thing | Path |
|---|---|
| `Library` (entry point) | `barn/haybale-marketplace/haybale_marketplace/__init__.py` |
| Descriptive metadata (`label`, `description`, `tags`) | `…/haybale.toml` |
| `LibraryManager` service | `…/library_manager.py` |
| `MarketplaceState`, `LibraryManagerState` | `…/state/` |
| Browser / Overview / Component editors | `…/editors/` |
| Multi-step flows (add-source, install, refresh, uninstall) | `…/editors/_*_flow/` |
| MCP tools (catalog + install) | `…/farmhands/` |

### Reaching the manager from another editor

```python
state = ctx.app_data[LibraryManagerState]
await state.manager.install(entry)               # uv pip install — async
state.manager.registry.disable_library(lib_id)   # registry persists via host.toml
```

`install` / `uninstall` are coroutines (there are `_streaming` variants that
report progress); `enable_library` / `disable_library` on the registry are
plain calls.

### Common pitfalls

| Pitfall | Why it matters |
|---|---|
| Adding a `haybale-marketplace` dependency from `haybale-studio` | Breaks optionality — the dependency must stay one-directional |
| Making `LibraryManager` inherit `AppState` | Constructor-shape mismatch; the plugin publishes it via `LibraryManagerState` instead |
| Persisting disabled-state in the plugin | Persistence belongs to the core `LibraryRegistry` / `HostStore`, not the marketplace |
| Scanning `editors/` before `state/` | Editor modules import state classes; wrong order leaves stale class objects |

For *how* the surface is built (refresh pipeline, two-tier files, conflict resolution, install gating), see [haybale-marketplace-arch](haybale-marketplace-arch.md). For the architectural rationale of the carve-out, see [ADR-0001](../../adr/0001-haybale-marketplace-carveout.md).
