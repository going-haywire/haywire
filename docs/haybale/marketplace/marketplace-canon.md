---
status: draft
doc_template: canonical-example
scope: The haybale-marketplace plugin — the optional library installer/browser haybale, its editors, its manager + marketplace states, and the optionality contract that lets the studio run without it
see-also:
  - haybale-marketplace-arch.md
  - library-canon.md
  - haybale-package-canon.md
  - ../architecture/library-system/library-system-arch.md
  - ../adr/0001-haybale-marketplace-carveout.md
  - ../reference/glossary.md
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
 parse / refresh / resolve        - 4 editors (browser,            provides the editor
 marketplace + marketstall          overview, component,           slots (left/main/right)
 files into a Haybale catalog       source) + 1 dialog module      into which the editors
                          ◀──────  - MarketplaceState              self-register.
                                    - LibraryManager (+            If haybale-marketplace
                                      LibraryManagerState)         is absent, the left slot
                                  - drives uv pip install          is simply empty — no
                                                                   defensive code needed.
       LibraryRegistry  ◀──────── manager.registry.enable/
       (core) owns                 disable_library(id);
       enable/disable              registry persists via
       persistence via HostStore   host.toml
```

The plugin owns **no registry state and no runtime parsing**. It calls `MarketplaceState` for catalog data (which wraps `haywire.core.marketstall`) and `LibraryManager` for install verbs (which shells out to `uv` and asks the Library System to rescan). Enable/disable persistence belongs to the core `LibraryRegistry`, not the plugin.

**Boundaries.** *How* the editors, refresh pipeline, two-tier marketplace files, conflict resolution, and `InstallType`-gated actions work — see [haybale-marketplace-arch](marketplace/haybale-marketplace-arch.md). *Why* the marketplace/marketstall trust model is shaped the way it is — see [shari../../architecture/sharing/sharing-arch.mdg-arch.md). What a `BaseLibrary`/`@library` author writes — see [librar../library-canon.md-canon.md). How a haybale is packaged and published — see [haybale-packag../haybale-package-canon.md-canon.md).

## 3. What the plugin ships

`barn/haybale-marketplace/haybale_marketplace/` registers two component categories from its `Library.register_components()`: states (via `LibraryStateRegistry`) and editors (via `EditorTypeRegistry`). **State is scanned before editors** — editor modules transitively import the state classes, and scanning them first keeps a single class object live (the same ordering rule `haybale-studio` follows).

### Editors

| Editor | Default slot | Role |
|---|---|---|
| `LibraryBrowserEditor` | `left` | Lists installed + available libraries, grouped REQUIRED / ENABLED / DISABLED / AVAILABLE. Toolbar: Refresh, Add Source, Edit File. |
| `LibraryOverviewEditor` | `main` | One library's identity, component breakdown, and Edit / Enable / Disable / Uninstall / Install actions. |
| `LibraryComponentEditor` | `right` | Detail view for one component (node/type/widget/…) — import snippet, port-wiring hints. |
| `ComponentSourceEditor` | `right` | Read/edit the component's source file (editable installs only). |

`library_marketplace_dialog` is **not** a registered editor — it is a module of helper functions (`show_add_source_dialog`, conflict-resolution prompts) the Browser's Add Source button calls.

### States

| State | Kind | Owns |
|---|---|---|
| `MarketplaceState` | `AppState` | Marketplace orchestration for one session — wraps `haywire.core.marketstall` (`get_global()`, `get_project_haybales()`, `refresh()`, `remove_stale_haybale()`). The UI never calls marketstall functions directly. |
| `LibraryManagerState` | `AppState` | A thin holder publishing the `LibraryManager` so other editors reach it via `ctx.app_data[LibraryManagerState].manager.X`. |

### The `LibraryManager` service

`LibraryManager` (`library_manager.py`) is a **plain class, not an `AppState`** — it owns the install / uninstall / enable / disable / rename / edit-identity verbs. Composition over inheritance: its constructor takes `(registry, project_dir)`, which an `AppState`'s bare `cls()` instantiation can't supply, so `LibraryManagerState` resolves those from the DI context in `on_enable()` and holds the manager. See [ADR-0001 §Why composition](../../adr/0001-haybale-marketplace-carveout.md).

## 4. Important concepts

**Optionality is the whole point.** Editors self-register into slots via `EditorTypeRegistry`. If `haybale-marketplace` is not installed, the left-slot library browser simply doesn't appear; `haybale-studio` carries no `if marketplace_present:` branches. This is what makes the carve-out worth its one extra `.manager.` indirection — a build can omit or replace the installer cleanly.

**Persistence lives in the core registry, not here.** "Which libraries are disabled" is a property of the `LibraryRegistry`, not the installer. The editors call `manager.registry.enable_library(id)` / `disable_library(id)`; the registry writes through to `HostStore` (`<workspace>/.haywire/host.toml`, `[libraries] disabled`). There is no marketplace-owned persistence and no `AppState` in the enable/disable path. See [ADR-0001 §Why persistence moves out](../../adr/0001-haybale-marketplace-carveout.md).

**It depends on `haybale-studio`, not the reverse.** `haybale-marketplace`'s `pyproject.toml` declares `haywire-core`, `haywire-studio`, and `haybale-studio` as dependencies — it consumes the studio's slots and editor base classes. `haybale-studio` declares no dependency on the marketplace; the relationship is strictly one-directional, which is what preserves optionality.

**`file_watcher=True`.** The plugin enables hot-reload like any editable haybale — edit an editor and the studio re-renders without restart (editable install only).

**Entry point.**

```toml
[project.entry-points."haywire.libraries"]
marketplace = "haybale_marketplace:Library"
```

## 5. Live example from the codebase

Source: [`barn/haybale-marketplace/haybale_marketplace/__init__.py`](../../../barn/haybale-marketplace/haybale_marketplace/__init__.py)

```python
@library(
    label="Library Marketplace",
    id="marketplace",
    version=_pkg_version("haybale-marketplace"),
    description="Library installer + browser editors",
    dependencies=[],
    tags=["marketplace"],
    file_watcher=True,
)
class Library(BaseLibrary):
    def register_components(self):
        base_path = Path(__file__).parent

        # state/ MUST be scanned before editors/. Editor modules transitively
        # import classes from state/ (LibraryManagerState, MarketplaceState);
        # scanning state first keeps a single class object live.
        self.add_folder_to_registry(
            folder_path=str(base_path / "state"),
            registry_cls=LibraryStateRegistry,
        )
        self.add_folder_to_registry(
            folder_path=str(base_path / "editors"),
            registry_cls=EditorTypeRegistry,
        )

    def validate(self) -> bool:
        return True
```

What this example exercises:

| Concept | Where |
|---|---|
| A standalone optional plugin registering studio UI | the whole package |
| `version` sourced from `importlib.metadata.version(...)` — pyproject is the source of truth | `version=_pkg_version("haybale-marketplace")` |
| Two registry categories: states + editors | two `add_folder_to_registry` calls |
| State-before-editors scan ordering | comment in `register_components` |
| Hot-reload for an editable plugin | `file_watcher=True` |
| `dependencies=[]` on the `@library` decorator (studio deps are in `pyproject.toml`, not here) | decoration |

---

## Quick reference

### What lives where

| Thing | Path |
|---|---|
| `Library` (entry point) | `barn/haybale-marketplace/haybale_marketplace/__init__.py` |
| `LibraryManager` service | `…/library_manager.py` |
| `MarketplaceState`, `LibraryManagerState` | `…/state/` |
| Browser / Overview / Component / Source editors | `…/editors/` |
| Add-Source + conflict dialogs (helper module) | `…/editors/library_marketplace_dialog.py` |

### Reaching the manager from another editor

```python
state = ctx.app_data[LibraryManagerState]
state.manager.install(entry)            # uv pip install
state.manager.registry.disable_library(lib_id)   # registry persists via host.toml
```

### Common pitfalls

| Pitfall | Why it matters |
|---|---|
| Adding a `haybale-marketplace` dependency from `haybale-studio` | Breaks optionality — the dependency must stay one-directional |
| Making `LibraryManager` inherit `AppState` | Constructor-shape mismatch; the plugin publishes it via `LibraryManagerState` instead |
| Persisting disabled-state in the plugin | Persistence belongs to the core `LibraryRegistry` / `HostStore`, not the marketplace |
| Scanning `editors/` before `state/` | Editor modules import state classes; wrong order leaves stale class objects |

For *how* the surface is built (refresh pipeline, two-tier files, conflict resolution, install gating), see [haybale-marketplace-arch](marketplace/haybale-marketplace-arch.md). For the architectural rationale of the carve-out, see [A../../adr/0001-haybale-marketplace-carveout.mdrveout.md).
