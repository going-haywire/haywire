---
status: draft
doc_template: impl-spec
scope: Studio's in-app package-manager surface — the two-tier marketplace files, refresh pipeline, conflict resolution, drift detection, and the editors that drive them
see-also:
  - ../sharing/sharing-arch.md
  - ../library-system/library-system-arch.md
  - ../studio/studio-arch.md
  - ../../components/haybale-package/haybale-package-canon.md
  - ../../guides/sharing-libraries.md
  - ../../guides/subscribing-to-marketplaces.md
  - ../../reference/glossary.md
---

# Library Manager — Architecture

This document describes *how* the library-management surface is built: the file layout it reads and writes, the pipeline that turns subscriptions into a usable catalog, the editors that drive that pipeline, and the boundary between this subsystem and the rest of haywire. For the *why* — the conceptual model behind these mechanics — see [sharing-arch](../sharing/sharing-arch.md).

## 1. Mental model

The Library Manager is a UI layer in `haywire-studio` that aggregates three things behind two editors:

- **uv / pip** — the package layer that installs Python distributions.
- **The [Library System](../library-system/library-system-arch.md)** — the framework infrastructure that loads `Library` classes once installed.
- **The marketplace runtime** — the discovery layer that turns user-opt-in subscriptions into a browsable catalog of installable packages.

Users see the **Library Browser** (left slot, lists installed and available libraries) and the **Library Overview Editor** (main slot, shows one library's identity / components / actions). The data behind both comes from two `marketplace.toml` files following a two-tier scheme.

The Library Manager is not the Library System. It does not discover entry points, load classes, or own registry state — it issues `uv pip install / uninstall` commands and asks the Library System to rescan. Below the wrapper, everything is the Library System's job.

## 2. The two-tier marketplace

Two files cooperate. Their concerns are deliberately separated.

### 2.1 Global marketplace

**Path:** `~/.haywire/marketplace.toml`.
**Owner:** the user (per-machine).
**Purpose:** records what the user has opted into following.

| Section | Schema | What it expresses |
|---|---|---|
| `[[marketplaces]]` | `url`, `ignores`, `doubles` | A subscription to a remote marketplace feed (a file aggregating packages and/or marketstall references). |
| `[[marketstalls]]` | `url`, `ignores`, `doubles` | A subscription to a remote marketstall feed (a single-author publish file). |
| `[[packages]]` | full `MarketplaceEntry` schema | A package the user has pasted in directly, bypassing any feed. |
| `[[locals]]` | `name`, `path`, optional `label` / `description` | A path-based library the user wants visible across every project. *Not* written by `haywire init`. Hand-curated for cross-project use cases. |

### 2.2 Project marketplace

**Path:** `<project>/.haywire/marketplace.toml`.
**Owner:** the project (travels with the source tree).
**Purpose:** records the project's own dependencies plus the latest refresh cache.

| Section | Schema | What it expresses |
|---|---|---|
| `[[locals]]` | `name`, `path`, optional metadata | Path-based libraries this project knows about. Written by `haywire init` (the project's own scaffolded library) and `haywire init --dev` (additionally, every dev-repo sibling library). |
| `[[packages]]` | full `MarketplaceEntry` with `via`, `last_seen`, `stale` extensions | The resolved catalog from the last refresh. Rebuilt on every refresh; consulted by the UI's "Available" filter. |

The project marketplace **never** contains `[[marketplaces]]` or `[[marketstalls]]` sections — those live only in the global file. Subscriptions are a user concern, not a project concern.

### 2.3 The `MarketplaceEntry` schema

All `[[packages]]` entries (in both files, plus what marketplaces / marketstalls deliver remotely) share one schema.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Pip distribution name (e.g. `haybale-visiongraph`). |
| `min_version` | string | yes | Minimum required version; not "latest available". |
| `label` | string | no | Human display name. |
| `description` | string | no | One-line description. |
| `author` | string | no | Author name(s). |
| `source` | string | no | `"pypi"`, `"git"`, or `"local"`. Drives install routing and version-fetching strategy. |
| `install_spec` | string | yes | Passed verbatim to `uv pip install`. |
| `tags` | list[str] | no | Filter tags. |
| `dependencies` | list[str] | no | Distribution names of other haybale libraries this one needs. |
| `source_url` | string | no | URL to the repo or source location. |
| `docs_url` | string | no | URL or local path to the docs directory. |

Cache-only fields (project marketplace `[[packages]]` only, never authored upstream):

| Field | Description |
|---|---|
| `via` | URL of the source that resolved this entry during refresh. |
| `last_seen` | ISO timestamp; set when the entry first goes stale. |
| `stale` | True when the most recent refresh did not re-resolve this name. |

## 3. The refresh pipeline

Refresh is the only operation that talks to the network. It is **explicit** — triggered by the user via the Library Browser's Refresh button, or automatically once after a successful Add Source. It is never timer-driven.

```text
[Global marketplace]                          [Project marketplace]
       │                                              ▲
       ├── parse                                      │
       │                                              │
       ├── for each [[marketplaces]] subscription:    │
       │     fetch → parse → collect packages         │
       │     and one-level-deep marketstall refs      │
       │                                              │
       ├── for each [[marketstalls]] subscription     │
       │     (direct + discovered):                   │
       │     fetch → parse → collect packages         │
       │                                              │
       ├── candidate list =                           │
       │     global [[packages]] ∪                    │
       │     global [[locals]] (path-named) ∪         │
       │     resolved remote packages                 │
       │                                              │
       ├── conflict resolution:                       │
       │     apply ignores → drop first occurrences   │
       │     apply locals shadow → locals win         │
       │     apply first-come-first-served → dedup    │
       │                                              │
       ├── stale marking:                             │
       │     diff against previous project cache      │
       │     entries dropped from sources but         │
       │     present in the prior cache → stale=True  │
       │                                              │
       └── serialize and write ──────────────────────►│
                                                      │
                                                      ▼
                                            project [[packages]] cache
```

The pipeline owns no install logic. It produces a catalog; installation runs separately when the user clicks Install on a catalog entry.

### 3.1 One-level-deep resolution

When a remote marketplace's body lists its *own* `[[marketplaces]]` subscriptions, those are ignored. Only the remote's `[[marketstalls]]` references and `[[packages]]` are consumed. This bounds the resolution to a single hop and keeps the trust model legible — see [sharing-arch §Bounded resolution](../sharing/sharing-arch.md#bounded-resolution).

### 3.2 HTTP cache and fallback

Every fetched URL is cached on disk at `~/.haywire/cache/<url-hash>.toml`. If a refresh fetch fails (network error, 404), the runtime falls back to the cached body. If neither succeeds, the URL is recorded in the `RefreshReport.unavailable_urls` list. Cache invalidation happens only on the next successful fetch — there is no TTL.

### 3.3 Conflict resolution

Conflicts come from two sources providing the same `name`. The runtime applies three filters in sequence:

| Filter | What it does |
|---|---|
| `ignores` | Each subscription has an `ignores` array recording names the user has explicitly chosen to skip from that source. Populated by the conflict-resolution prompt at Add Source time. |
| Locals shadow | Any package whose `name` matches an entry in either the global or project `[[locals]]` is dropped from the remote-resolved candidates — locals always win. |
| First-come-first-served | After the above, if any name still appears twice (e.g. from a user hand-edit), the runtime deterministically keeps the first occurrence. Safety net only — every conflict that flows through the UI is supposed to land in `ignores`. |

The user-prompt path: when Add Source fetches the new URL and detects a name collision against the existing resolved state, the user is shown one row per conflict and asked which source to keep. The losing side's subscription gets the name added to its `ignores` array. Subsequent refreshes honor the choice without re-asking.

### 3.4 The refresh report

Each refresh produces a `RefreshReport` cached on `MarketplaceState.last_report`:

| Field | Type | Meaning |
|---|---|---|
| `sources_fetched` | int | How many subscriptions were successfully read (cache hits count). |
| `sources_unavailable` | int | How many subscriptions failed to fetch AND had no cached fallback. |
| `unavailable_urls` | list[str] | The specific URLs in the previous count. Drives the yellow banner. |
| `packages_resolved` | int | Non-stale entries in the final cache. |
| `new_stale` | int | Entries that became stale on this refresh (previously fresh). |

## 4. State and ownership

### 4.1 `MarketplaceState` (AppState)

The UI calls **`MarketplaceState`**, not `marketplace_runtime` directly. The state owns marketplace orchestration for one studio session.

| Surface | Returns | Used by |
|---|---|---|
| `get_global()` | `GlobalMarketplace \| None` | Library Browser banners; the dialog's conflict-detection step |
| `get_project_packages()` | `list[MarketplaceEntry]` | Library Browser's Available section |
| `refresh()` | `RefreshReport` | Refresh button; auto-fire after Add Source |
| `remove_stale_package(name)` | `bool` | Trash icon on stale + uninstalled rows |
| `last_report` | property | UI banners read this to render after a refresh |
| `global_marketplace_error` | property | Set when `get_global()` saw a malformed file; surfaces the red banner |

`MarketplaceState` is designed for an eventual carve-out: when `haybale-marketplace` becomes its own package, this state object moves with the editors.

### 4.2 The two editors

| Editor | Slot | Drives |
|---|---|---|
| **Library Browser** | left | Lists installed + available libraries. Filter toggles for REQUIRED / ENABLED / DISABLED / AVAILABLE. Toolbar exposes Refresh, Add Source, Edit File. |
| **Library Overview Editor** | main | One library's identity, component breakdown, and Edit / Enable / Disable / Uninstall actions. Reached by clicking a row in the Library Browser. |

`LibraryManager` (the orchestrator class in `haywire-studio/src/haywire_studio/library_manager.py`) is shared by both editors and owns the install / uninstall / enable / disable / rename / edit-identity verbs.

### 4.3 The Library Browser's filter rules

The Browser groups libraries into four sections, computed at render time:

| Section | Inclusion rule |
|---|---|
| **REQUIRED** | Installed + enabled + some other installed haywire library declares it in its `@library(dependencies=[...])`. The signal comes from `LibraryManager.get_installed_dependents(lib_id)` — the same source the Overview Editor's Disable / Uninstall gating uses. |
| **ENABLED** | Installed + enabled + not in REQUIRED. |
| **DISABLED** | Installed + not enabled. |
| **AVAILABLE** | Anything in the project marketplace's `[[packages]]` cache OR `[[locals]]` that isn't already installed. Locals are surfaced here as `source="local"` entries so they're visible before the user installs them. |

Stale entries in AVAILABLE render with a red dot + "(stale)" suffix + last-seen tooltip. If the package isn't installed, a trash icon allows removing it from the project cache.

## 5. The install / uninstall pipeline

Selecting an Available entry in the Library Browser opens its overview; the user clicks Install in the Library Overview Editor.

```text
User clicks Install in the Library Overview Editor
  │
  ├── LibraryManager.install(entry) reads entry.install_spec
  ├── Subprocess: uv pip install <install_spec>
  │     - local path  → uv pip install -e <path>
  │     - pypi spec   → uv pip install <name>>=<version>
  │     - git spec    → uv pip install <name> @ git+<url>#subdirectory=<path>
  ├── On success:
  │     - importlib invalidate_caches()
  │     - re-process .pth files for editable installs
  │     - Library System rescan (LibraryRegistry.scan_for_libraries)
  ├── New components register via @library / @node / @type / @adapter / etc.
  └── UI refreshes: entry moves from AVAILABLE to ENABLED
```

Uninstall is the inverse: `uv pip uninstall <dist_name>`, then rescan. The Overview Editor refuses Uninstall while any other installed library declares this one in its `@library` dependencies.

### 5.1 InstallType detection

After install, the Library System inspects each library's filesystem location and assigns an `InstallType` (`REGULAR`, `EDITABLE`, `FOLDER` — see [library-system §InstallType](../library-system/library-system-arch.md#23-installtype-enum-haywirecorelibraryinstall_typepy)). The Overview Editor uses this to decide which actions are available:

| Action | `EDITABLE` | `REGULAR` | `FOLDER` |
|---|---|---|---|
| Edit identity (label, version, dependencies, etc.) | yes | no | no |
| Detect Dependencies button | yes | no | no |
| Save source code | yes | no | no |
| Hot-reload | yes | no | yes |
| Disable / Enable | yes | yes | yes |
| Uninstall | yes (`uv pip uninstall`) | yes | yes |

## 6. Drift detection at edit time

A separate but related pipeline lives in the Library Overview Editor's **Edit dialog**: the **Detect Dependencies** button.

When the user clicks Detect:

1. The runtime statically scans the library's source via `detect_deps(lib_dir, libraries=manager.registry)`.
2. It computes two diffs: the current `@library(dependencies=[...])` value vs detected, and the current `[project] dependencies` in the library's `pyproject.toml` vs detected.
3. A diff modal previews both, offering **Union** (merge, never remove) or **Replace** (detected only).
4. On apply, the `@library` deps update the dialog's input field (the user still has to click Save Changes to persist); the pyproject.toml is written immediately.

The corresponding CLI gate lives in `haywire share` — see [sharing-libraries guide](../../guides/sharing-libraries.md).

## 7. Failure surfaces

The Library Browser handles three classes of failure with three distinct visual treatments. All use `--hw-*` design tokens; never hardcoded reds or yellows.

| Failure | Trigger | UI |
|---|---|---|
| **Malformed global marketplace** | `MalformedGlobalMarketplaceError` from refresh | Red banner above the list using `--hw-danger` + `--hw-danger-bg`. Edit File button is the recovery path. The Library Browser refuses to render the catalog until the file is parsable. |
| **Sources unavailable** | `RefreshReport.unavailable_urls` non-empty | Yellow banner above the list using `--hw-warning`. Info button opens a modal listing the failed URLs. Refresh continues; cached fallbacks fill in where available. |
| **Stale entries** | `MarketplaceEntry.stale=True` on an AVAILABLE row | Red dot + "(stale)" sublabel suffix + tooltip showing `last_seen`. Trash icon if uninstalled. |

## 8. Boundary — what the Library Manager is not

- **Not a registry.** The class registries belong to the [Library System](../library-system/library-system-arch.md). The Library Manager *triggers* a rescan; it does not own registry state.
- **Not a publisher.** It consumes marketplace and marketstall files; producing one is `haywire share`'s job — see the [sharing-libraries guide](../../guides/sharing-libraries.md).
- **Not a build tool.** It does not build wheels, run `uv build`, or run `uv publish`. Releases go through `/haywire-release` and CI — see [publish_releases](../../reference/publish_releases.md).
- **Not a transitive dep resolver.** When a library's `MarketplaceEntry.dependencies` lists other haybale packages, the Library Manager does not install them automatically. The user installs each library individually; uv handles the actual pip-level resolution.
- **Not a curator.** No source is more authoritative than any other in the data. The official haywire feed is one feed among many — see [sharing-arch §The aggregator, not the publisher](../sharing/sharing-arch.md#the-aggregator-not-the-publisher).

## 9. Examples

### 9.1 Subscribing to the official feed

User edits `~/.haywire/marketplace.toml` via the Library Browser's **Edit File** button (or clicks Add Source → Marketplace tab):

```toml
[[marketplaces]]
url = "https://maybites.github.io/haywire/marketplace.toml"
ignores = []
doubles = []
```

Click Refresh. The runtime fetches the URL, parses its `[[marketstalls]]` references one level deep, fetches those, assembles the candidate list, applies conflict resolution, and writes the project's `[[packages]]` cache. The Library Browser's AVAILABLE section now lists every official package.

### 9.2 A project-scaffolded library after `haywire init --dev`

Running `haywire init --dev my-project` creates `<my-project>/.haywire/marketplace.toml`:

```toml
[[locals]]
name = "haybale-my-project"
path = "/abs/path/to/my-project/barn/haybale-my-project"
label = "My Project"
description = "Local library for the my-project project"

[[locals]]
name = "haybale-core"
path = "/abs/path/to/haywire-repo/barn/haybale-core"
label = "Core"
description = "Core library for Haywire node system..."

# ...one [[locals]] per dev-repo sibling library
```

The user's `~/.haywire/marketplace.toml` is left untouched. The dev-repo libraries are scoped to this project only; opening a different project doesn't see them.

### 9.3 What `haywire share --save` produces

Running `haywire share --save` at a repo root with a `barn/` containing libraries writes `<repo-root>/marketstall.toml`:

```toml
# marketstall.toml — share this file's raw URL so others can subscribe
# Run: haywire share --save  to update this file

[[packages]]
name         = "haybale-my-lib"
label        = "My Lib"
min_version  = "0.1.0"
description  = "..."
author       = "Your Name"
source       = "git"
install_spec = "haybale-my-lib @ git+https://github.com/you/repo.git#subdirectory=barn/haybale-my-lib"
tags         = []
dependencies = ["haybale-core"]
source_url   = "https://github.com/you/repo"
docs_url     = "https://raw.githubusercontent.com/you/repo/main/barn/haybale-my-lib/haybale_my_lib/"
```

A consumer subscribes to the raw URL of that `marketstall.toml` via a `[[marketstalls]]` entry in their global marketplace, then refreshes.

## 10. Open questions

- **Lazy library loading.** Every discovered library loads eagerly at startup (see [library-system §4.2](../library-system/library-system-arch.md#42-module-resolution-cost)). Should the Library Browser surface a Defer-loading option for heavy libraries?
- **Cross-feed dep resolution.** When a library's `dependencies` lists another haybale package not yet installed, should the Library Manager offer to install both? Currently the user installs each individually.
- **Auto-refresh on a schedule.** Refresh is explicit by design — see [sharing-arch §The refresh cycle](../sharing/sharing-arch.md#the-refresh-cycle) — but a "refresh on first open of the day" option may be worth exposing.
- **`haybale-marketplace` carve-out.** The current Library Browser + Library Overview Editor + `MarketplaceState` are all in `haybale-studio`. The plan is to extract them as a standalone haybale package once the surface stabilizes.
