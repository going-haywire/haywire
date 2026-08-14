---
status: draft
doc_template: impl-spec
scope: The haybale-marketplace plugin — the catalog lifecycle from Add Source to install, what is cached where, conflict resolution, recovery, and the editors and states that drive them
see-also:
  - marketplace-canon.md
  - ../../reference/files/marketplace-toml.md
  - ../../reference/files/marketstall-toml.md
  - ../../architecture/library-system/library-system-arch.md
  - ../haybale-canon.md
  - ../../guides/subscribing-to-marketplaces.md
---

# haybale-marketplace — Architecture

How the library-management surface is built: the pipeline that turns a pasted URL into an installable catalog, what lands on disk along the way, the editors that drive it, and how to recover when the result is wrong. Why it is shaped this way is [§8](#8-why-the-model-is-shaped-this-way). For what the plugin ships and how it self-registers, see [marketplace-canon](marketplace-canon.md).

**File formats are documented once**, in [`marketplace.toml`](../../reference/files/marketplace-toml.md) and [`marketstall.toml`](../../reference/files/marketstall-toml.md). This page names the sections and says what moves them; it does not restate their fields.

The surface lives in its own optional haybale package, **`haybale-marketplace`** (`barn/haybale-marketplace/`). The studio runs without it: if the package is absent, the left-slot library browser simply doesn't appear — no defensive code in `haybale-studio`. `haywire init` installs it by default.

## 1. Mental model

**The Library Manager decides *which* libraries exist on this machine; the
Library System decides *what they contribute* once they do.** The first is an
optional UI plugin that shells out to `uv pip install`, the second is framework
infrastructure that imports `Library` classes and fills the registries. They
meet at exactly one point: after an install or uninstall, the Library Manager
asks the Library System to rescan.

So the Library Manager never discovers entry points, imports a module, or owns
registry state — below that one call, everything is the Library System's job.
Deleting the whole plugin costs you the UI and nothing else: the libraries
already installed still load.

### Terms on this page

| Term | Is |
| --- | --- |
| **`haybale-marketplace`** | The optional haybale package (`barn/haybale-marketplace/`) holding everything on this page. The studio runs without it |
| **Library Manager** | The subsystem as a whole — what this plugin *is*, informally. Not a class |
| **`LibraryManager`** | The class owning the install / uninstall / enable / disable verbs. A plain class, not an `AppState` |
| **Library Browser** | The ACTION-slot editor listing installed and available libraries, grouped REQUIRED / ENABLED / DISABLED / AVAILABLE |
| **Library Overview Editor** | The EDIT-slot editor showing one library's identity, components and actions |
| **Library Component Editor** | The CONTEXT-slot editor showing one component of one library |
| **`MarketplaceState`** | The `AppState` owning catalog data — parse, refresh, resolve. The UI never calls the marketstall runtime directly |
| **`LibraryManagerState`** | A thin `AppState` publishing the `LibraryManager` to other editors |
| **Marketplace** | The aggregated catalog a user can install *from* — subscriptions resolved into rows |
| **Marketstall** | One author's published feed, the unit a user subscribes to |
| **Library System** | Framework infrastructure — **not part of this plugin**. `LibraryRegistry`, `LibraryDiscovery`, `LibraryIdentity`, `FileWatcher` |
| **`LibraryRegistry`** | The Library System's registry of loaded libraries. Owns enable/disable **persistence**; the plugin calls it and does not duplicate it |

The plugin aggregates three layers behind its editors: **uv / pip** installs
distributions, the
**[Library System](../../architecture/library-system/library-system-arch.md)**
loads them, and the **marketplace runtime**
(`haywire.core.marketstall`) turns subscriptions into a browsable catalog.

The data behind every view comes from two `marketplace.toml` files — a global
one holding the user's subscriptions, and a per-project one holding the resolved
catalog ([§2](#2-the-catalog-lifecycle)).

## 2. The catalog lifecycle

Everything from a pasted URL to an installed library. Five sections in two
files carry the state; each hop below names which one it writes.

```text
  user pastes a URL
        │
        ▼
  ┌───────────────┐  classify the body's shape
  │  Add Source   │  ─────────────────────────────────────────────┐
  └───────┬───────┘                                               │
          │ writes a subscription                                 │
          ▼                                                       │
  ~/.haywire/db/haybale_marketplace/marketplace.toml              │
      [[markets]]  an aggregator's catalog                        │
      [[stalls]]   one author's feed                              │
      [[haybales]] hand-written inline entries                    │
          │                                                       │
          │ auto-refresh once                                     │
          ▼                                                       │
  ┌───────────────┐  the ONLY network operation                   │
  │   refresh()   │                                               │
  └───────┬───────┘                                               │
          │  fetch each subscription ──▶ ~/.haywire/cache/<hash>.toml
          │  parse markets one level deep (their [[stalls]] only)
          │  apply blocked per subscription
          │  apply heaps shadow, then first-come-first-served
          │  diff against the previous cache to mark stale
          ▼
  <project>/.haywire/marketplace.toml
      [[heaps]]   path-based project libraries (written by haywire init)
      [[caches]]  the resolved catalog — rebuilt in full every refresh
          │
          │ the browser's AVAILABLE section reads this; no network
          ▼
  ┌───────────────┐  uv pip install <install_spec>
  │    Install    │  → invalidate caches → Library System rescan
  └───────────────┘
```

### 2.1 The five sections

| Section | File | Written by | What it expresses |
| --- | --- | --- | --- |
| `[[markets]]` | global | Add Source | A subscription to an aggregator that references other stalls |
| `[[stalls]]` | global | Add Source | A subscription to one author's marketstall |
| `[[haybales]]` | global | hand-written | Libraries declared inline, without a subscription |
| `[[heaps]]` | project | `haywire init` | Path-based libraries this project knows about |
| `[[caches]]` | project | refresh | The resolved catalog from the last refresh |

Subscriptions are a user concern, not a project concern: `[[markets]]` and
`[[stalls]]` never appear in the project file, and `[[heaps]]`/`[[caches]]`
never in the global one. Sections in the wrong file are dropped at parse.

`[[markets]]` and `[[stalls]]` are structurally identical. The difference is
only how the fetched body is parsed — a market body may reference further
stalls; a stall body contains `[[haybales]]` and nothing else.

Field-by-field definitions: [`marketplace.toml`](../../reference/files/marketplace-toml.md).

### 2.2 Add Source — what is written where

The dialog takes one field and accepts a blob URL, a raw URL, a plain TOML URL,
or a TOML block pasted directly. The runtime fetches the body, inspects its
shape, and writes the matching subscription:

| Body contains | Written as |
| --- | --- |
| `[[markets]]` or `[[stalls]]` | a `[[markets]]` subscription |
| `[[haybales]]` only | a `[[stalls]]` subscription |
| neither | rejected — the body is not a marketplace or a marketstall |

A **pasted block** is saved to
`~/.haywire/db/haybale_marketplace/stalls/<dist-name>.toml` and subscribed via a
`file://` URL, so it follows exactly the same refresh path as a remote feed
rather than needing a second code path. The file is written only when the user
commits — resolving a source the user then abandons leaves nothing on disk.

Both writers are idempotent on URL match, so re-subscribing an existing source
is a no-op rather than a duplicate entry.

### 2.3 Refresh — the only network operation

Explicit by design: the Refresh button, or once automatically after a successful
Add Source. Never timer-driven.

The pipeline splits into a **fetch** phase and a pure **resolve** phase, so a
caller can fetch once and resolve as often as it likes — which is what lets the
UI preview "3 newly stale, 2 updates available" before committing the write.

1. **Fetch** every `[[markets]]` and `[[stalls]]` subscription.
2. **Parse markets one level deep** — their `[[stalls]]` references and inline
   `[[haybales]]` are consumed; any `[[markets]]` *inside* a fetched market body
   are ignored. This bounds resolution to a single hop, so a subscription cannot
   silently enrol the user in an unbounded graph of feeds.
3. **Fetch the discovered stalls.**
4. **Filter and resolve** ([§2.5](#25-conflict-resolution)).
5. **Mark stale** by diffing against the previous cache.
6. **Write** the project's `[[caches]]`, then GC orphaned cache files.

The pipeline owns no install logic. It produces a catalog; installation runs
separately when the user clicks Install.

### 2.4 What lands on disk

| Path | Holds | Written by |
| --- | --- | --- |
| `~/.haywire/db/haybale_marketplace/marketplace.toml` | Subscriptions | Add Source; created with the official feed on first run |
| `~/.haywire/db/haybale_marketplace/stalls/<dist>.toml` | Pasted-in blocks | Add Source |
| `~/.haywire/cache/<url-hash>.toml` | Raw fetched bodies | Every successful fetch |
| `~/.haywire/cache/docs/<library>/` | Fetched doc bodies | Overview doc fetches |
| `<project>/.haywire/marketplace.toml` | `[[heaps]]` + `[[caches]]` | `haywire init`; refresh |

**The HTTP cache has no TTL.** An entry is valid until a successful fetch
overwrites it. When a fetch fails, the cached body is served instead and the
refresh reports `CACHE_FALLBACK`; only a failure with no cached body counts as
unavailable. At the end of a refresh, cache files whose URL is no longer in any
subscription are deleted.

Note the cache is **not** under the marketplace's own storage directory — it is
`~/.haywire/cache/`, shared infrastructure, and can be deleted wholesale without
touching subscriptions.

### 2.5 Conflict resolution

Two sources offering the same `name`. Four filters, in the order they run — the
first two per subscription while building each batch, the last two across the
combined list:

| Filter | Effect |
| --- | --- |
| `blocked` | Names the user rejected in the install-safety modal. Filtered from the candidate list **and** from the previous cache's stale-rescue pool, so they disappear entirely rather than surviving as stale rows. Un-blockable only by editing the file |
| `preference` | Names *this* source should win when several offer them. Written by the conflict prompt at Add Source time and by the refresh flow's "Use this one"; exclusive, so one write settles the choice |
| Heaps shadow | A candidate whose `name` matches a project `[[heaps]]` entry is dropped — local always wins |
| First-come-first-served | The fallback when no source claims a contested name in `preference`. Every collision is reported on the resolve step, so an unsettled one is visible before it changes a version |

When Add Source detects a collision against already-resolved state, the user
picks which source wins; the loser's subscription gains the name in its
`preference`. Later refreshes honour the choice without re-asking.

### 2.6 The refresh report

Cached on `MarketplaceState.last_report`.

| Field | Meaning |
| --- | --- |
| `sources_fetched` | Read from the network this refresh |
| `sources_from_cache` | Served from the disk cache — network unreachable, prior body reused |
| `sources_unavailable` | Failed to fetch **and** had no cached fallback |
| `unavailable_urls` | The URLs behind that count. Drives the yellow banner |
| `haybales_resolved` | Non-stale entries in the final cache |
| `new_stale` | Entries that became stale on this refresh |
| `updates_available` | Installed haybales whose cache `version` exceeds the installed one |

The first three always partition the active subscription set.

## 3. Recovering a botched database

Every file here is plain TOML and safe to inspect. **No installed package is
ever lost by deleting any of them** — installation is pip state, not marketplace
state, so the worst case is a rebuild plus re-subscribing.

### Symptoms

| Symptom | Cause | Fix |
| --- | --- | --- |
| Red banner; the catalog refuses to render | The global `marketplace.toml` is malformed | Edit File — the parse error names the file. The browser deliberately refuses to render a catalog it cannot trust |
| Yellow banner, "N sources unavailable" | Fetch failed with no cached fallback | Check the URLs in the info modal. Refresh continues; cached sources still fill in |
| A library will not go away | Its name is in a subscription's `blocked` | Remove it from that array in the global file. `blocked` hides it everywhere |
| Rows marked "(stale)" that should be gone | The source stopped listing them | Trash icon on the row when the library is not installed, or clear `[[caches]]` |
| The wrong library wins | A project `[[heaps]]` entry shadows the remote one, or first-come-first-served picked one | Check `[[heaps]]` first — local always wins |
| A source serves old content | Its cached body is being reused | Delete `~/.haywire/cache/` to force a refetch |
| A heap points nowhere | `path` is absolute and machine-specific | Fix or remove the `[[heaps]]` entry; these break when a project is cloned |

### The reset ladder

Smallest blast radius first. Stop as soon as it works.

1. **Delete the project's `[[caches]]` section.** Rebuilt by the next refresh.
   Costs one cycle of stale bookkeeping and nothing else.
2. **Delete `~/.haywire/cache/`.** Forces every source to be refetched.
   Subscriptions are untouched.
3. **Delete `<project>/.haywire/marketplace.toml`.** Loses the project's
   `[[heaps]]` too — re-run `haywire init --dev` to regenerate them.
4. **Delete the global `marketplace.toml`.** Loses every subscription the user
   added; it is recreated with the official feed on next start.

A malformed `[[caches]]` section is already self-healing: the parser discards it
and refetches rather than raising, because a strict parse would block the very
refresh that would repair it. `[[heaps]]` stays strict — it is user-authored, so
a malformed entry is a mistake worth surfacing rather than silently dropping.

## 4. State and ownership

### 4.1 `MarketplaceState` (AppState)

The UI calls **`MarketplaceState`**, not `marketplace_runtime` directly. The state owns marketplace orchestration for one studio session.

| Surface | Returns | Used by |
|---|---|---|
| `get_global()` | `MarketplaceFile \| None` | Library Browser banners; the dialog's conflict-detection step |
| `get_project_haybales()` | `list[Haybale]` | Library Browser's Available section |
| `refresh()` | `RefreshReport` | Refresh button; auto-fire after Add Source |
| `remove_stale_haybale(name)` | `bool` | Trash icon on stale + uninstalled rows |
| `last_report` | property | UI banners read this to render after a refresh |
| `global_marketplace_error` | property | Set when `get_global()` saw a malformed file; surfaces the red banner |

`MarketplaceState` lives in `barn/haybale-marketplace/haybale_marketplace/state/marketplace_state.py`. It self-registers via `LibraryStateRegistry` when the plugin loads; consumers reach it the usual way (`ctx.app_data[MarketplaceState]`).

### 4.2 The editors and the manager state

`haybale-marketplace` registers three editors (`barn/haybale-marketplace/haybale_marketplace/editors/`):

| Editor | Slot | Drives |
|---|---|---|
| **Library Browser** | `ACTION` | Lists installed + available libraries. Filter toggles for REQUIRED / ENABLED / DISABLED / AVAILABLE. Toolbar exposes Refresh, Add Source, Edit File. |
| **Library Overview Editor** | `EDIT` | One library's identity, component breakdown, and Edit / Enable / Disable / Uninstall actions. Reached by clicking a row in the Library Browser. |
| **Library Component Editor** | `CONTEXT` | One component of one library — import snippet, port-wiring hints. |

The multi-step flows (add-source, install, refresh, uninstall) are **not**
editors: they live in `editors/_*_flow/` subpackages and are driven by the
editors above. The full editor/state inventory is in
[marketplace-canon §What it ships](marketplace-canon.md#3-what-the-plugin-ships).

`LibraryManager` (the orchestrator class in `barn/haybale-marketplace/haybale_marketplace/library_manager.py`) owns the install / uninstall / enable / disable / edit-identity verbs. It is a plain class — *not* an `AppState`. It is published to the other editors through a thin `LibraryManagerState(AppState)` holder (composition, not inheritance — see [ADR-0001 §Why composition](../../adr/0001-haybale-marketplace-carveout.md)), so consumers reach it via `ctx.app_data[LibraryManagerState].manager.X`. The state resolves the registry and workspace root from the ambient DI context in `on_enable()`.

Enable/disable **persistence** is not a manager concern: the core `LibraryRegistry` owns it via `HostStore` (`<workspace>/.haywire/host.toml`). The editors call `manager.registry.enable_library(id)` / `disable_library(id)` directly and the registry writes through. See [ADR-0001 §Why persistence moves out of the manager](../../adr/0001-haybale-marketplace-carveout.md).

### 4.3 The Library Browser's filter rules

The Browser groups libraries into four sections, computed at render time:

| Section | Inclusion rule |
|---|---|
| **REQUIRED** | Installed + enabled + some other installed haywire library declares it in its `haybale.toml` `linked_libraries`. The signal comes from `LibraryManager.get_installed_dependents(lib_id)` — the same source the Overview Editor's Disable / Uninstall gating uses. |
| **ENABLED** | Installed + enabled + not in REQUIRED. |
| **DISABLED** | Installed + not enabled. |
| **AVAILABLE** | Anything in the project marketplace's `[[caches]]` OR `[[heaps]]` that isn't already installed. Heaps are surfaced here as `source="local"` entries so they're visible before the user installs them. Blocked haybales never appear — they're filtered out at refresh time. |

Stale entries in AVAILABLE render with a red dot + "(stale)" suffix + last-seen tooltip. If the package isn't installed, a trash icon allows removing it from the project cache.

The Library Browser also shows a **provenance label** on each AVAILABLE row, derived from the `via` cache field:

- **Direct `[[stalls]]` subscription**: "from `{stall-host}`" (e.g. "from github.com/alice").
- **Transitive via `[[markets]]`**: "via `{aggregator-host}`" (e.g. "via going-haywire.github.io"), tooltip identifies both the aggregator and the underlying stall.

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

Uninstall is the inverse: `uv pip uninstall <dist_name>`, then rescan. The Overview Editor refuses Uninstall while any other installed library declares this one in its `linked_libraries`.

### 5.1 InstallType detection

After install, the Library System inspects each library's filesystem location and assigns an `InstallType` (`REGULAR`, `EDITABLE`, `FOLDER` — see [library-system §InstallType](../../architecture/library-system/library-system-arch.md#23-installtype-enum-haywirecorelibraryinstall_typepy)). The Overview Editor uses this to decide which actions are available:

| Action | `EDITABLE` | `REGULAR` | `FOLDER` |
|---|---|---|---|
| Edit identity (label, version, dependencies, etc.) | yes | no | no |
| Save source code | yes | no | no |
| Hot-reload | yes | no | yes |
| Disable / Enable | yes | yes | yes |
| Uninstall | yes (`uv pip uninstall`) | yes | yes |

### 5.2 Framework version gate

Every marketplace install (`dry_run()` and `install()` alike, with identical
flags) passes `uv pip install -c <constraints>` pinning `haywire-core`,
`haywire-studio`, and `nicegui` to their **currently-installed exact versions**
— read from the running venv, because a declared `Requires-Dist` can itself be
stale while what is running cannot.

`uv pip install <spec>` resolves fresh against the requested spec's tree;
already-installed packages are only reuse candidates. Without the constraint
file, taking a haybale update can pull `haywire-core` forward while
`haywire-studio` stays put — old studio + new core is an `ImportError` at
runtime. With it, that resolution simply fails, and the failure names the
shell's "Check for updates" control as the remedy.

The `haybale-*` libraries are deliberately **not** constrained: upgrading them
is exactly what a marketplace install is for.

## 6. Linked-libraries registration at edit time

The Library Overview Editor's Edit dialog can register imported haywire libraries into `haybale.toml`'s `linked_libraries` without going through `haywire share`. It applies the same rule the share pipeline applies, deliberately: **union in what the source provably imports; never remove; never ask.**

**Why this field and no other.** `linked_libraries` is the one dependency-shaped field this editor authors. Every other dependency concern — `[project] dependencies` in the library's pyproject — stays exclusively a `haywire share` concern. The distinction is decision vs. fact: a pip dependency's version floor is an authored choice with real tradeoffs (which floor, whether a lagging version matters). A missing `linked_libraries` entry is provably true — `detect_deps` emits a name only when the source imports it *and* it resolves to an installed, registered haywire library — so there is nothing to decide, only to apply.

That is why the control is a **label and a button**, not an editable field. An input would imply a judgement the author does not have to make, and would invite a hand-typed value that `_validate_linked_libraries` rejects at write time.

### How it works

1. "Linked libraries" renders as a read-only label of the current declared list, read from `haybale.toml` rather than from `LibraryInfo.identity` (identity holds the startup value and would render stale after an in-session save).
2. A **Refresh** button — heap libraries only, the same rule `os` follows — runs `detect_share_drift(lib_root, libraries=manager.registry)`, the same function `haywire share` uses, passed the studio's live `LibraryRegistry` instead of the CLI's entry-point-derived source.
3. Detected entries not already declared are unioned into a staged list and the label re-renders. Nothing else changes: an entry the scan no longer sees is left alone, because a dynamic import the scanner cannot see is indistinguishable from an obsolete one.
4. Refresh writes nothing. Only **Save Changes** writes, through the same `write_haybale_fields` path every other field uses — and only when Refresh actually changed the list, so an untouched dialog never churns a hand-authored file.

### The library-root subtlety

`detect_share_drift` takes the **library root** (the `pyproject.toml` directory) and locates the package itself via `find_module_dir`. Both CLI callers get that path from a filesystem scan — `barn_library_dirs(repo_root)`, which selects non-symlinked children of `barn/` that have a `pyproject.toml`.

The editor has no such scan; it has a `LibraryInfo` whose `identity.folder_path` is the **package** directory (it is what `read_display` and `read_haybale_toml_lenient` are given). The editor therefore passes `folder_path.parent`, which is correct precisely because of the heap gate: `is_project_library` establishes that `folder_path` sits under the workspace's `barn/`, so its parent is the `barn/<lib>/` directory the pipeline would have scanned. For a site-packages wheel the parent is `site-packages/` — no `pyproject.toml`, no valid detection. Passing `folder_path` directly fails silently: `find_module_dir` returns `None` and the button renders permanently disabled, looking like correct behavior.

### One rule, three surfaces

| Surface | How registrations are applied |
| --- | --- |
| `haywire share` CLI | Unconditionally, before the drift branch; each entry printed as it is applied |
| Share wizard | Named on the Review screen, applied by `apply_all` in the single write pass |
| Edit dialog Refresh | Staged into the label on click, written by Save Changes |

All three read the same `DriftReport.linked_registrations` / `linked_missing` and apply the same union. That property is load-bearing and was not always true: the wizard rendered registrations it never wrote, because `_collect` omitted them from the `ShareDecisions` it handed `apply_all`, while the CLI applied the same registrations on identical input. `DriftReport.linked_registrations` exists as a single hoisted property for exactly this reason — its docstring records that the logic "was duplicated in both, divergently, before this property existed."

### Not a return of the old Detect Dependencies button

An earlier version of this dialog had a "Detect Dependencies" button that scanned *both* `linked_libraries` and pip dependencies, offering Union/Replace across both. It was removed because the pip-dependency side created two uncoordinated writers to the same `[project] dependencies` list — this button and the Share wizard's own writer — which is what let the framework floor get silently clobbered. That bug never existed on the `linked_libraries` side: those entries were already "applied automatically, never a choice" even inside the Share flow, so a second surface applying the same provably-true rule does not recreate the conflict. Note also that only Union survives here; Replace was the destructive half and has no equivalent on any surface.

The same detection backs the CLI: step 2 of `SharePipeline` and `haywire deps check` both call `detect_share_drift()` ([share-pipeline-arch §2.2](../../architecture/sharing/share-pipeline-arch.md#22-step-2-dependency-drift)). For the author-facing workflow, see the [sharing-libraries guide §3](../../guides/sharing-libraries.md#63-keeping-the-manifests-honest).

## 7. Failure surfaces

The Library Browser handles three classes of failure with three distinct visual treatments. All use `--hw-*` design tokens; never hardcoded reds or yellows.

| Failure | Trigger | UI |
|---|---|---|
| **Malformed global marketplace** | `MalformedGlobalMarketplaceError` from refresh | Red banner above the list using `--hw-danger` + `--hw-danger-bg`. Edit File button is the recovery path. The Library Browser refuses to render the catalog until the file is parsable. |
| **Sources unavailable** | `RefreshReport.unavailable_urls` non-empty | Yellow banner above the list using `--hw-warning`. Info button opens a modal listing the failed URLs. Refresh continues; cached fallbacks fill in where available. |
| **Stale entries** | `Haybale.stale=True` on an AVAILABLE row | Red dot + "(stale)" sublabel suffix + tooltip showing `last_seen`. Trash icon if uninstalled. |

## 8. Why the model is shaped this way

The mechanics above follow from a few commitments. They are worth stating,
because each one rules out an obvious-looking alternative.

**Haywire aggregates; it does not host.** There is no server, no registry, no
vetting, and no ranking. An author publishes by putting a file somewhere
consumers can fetch it; a consumer subscribes by pointing at that URL. The
official haywire feed travels the same path as everyone else's — there is no
privileged route. The catalog is a *view* computed from one user's subscription
list at refresh time, not a database: there is no canonical list of all haywire
libraries anywhere.

**Two tiers, because two different questions.** "Which feeds do I follow?" is an
answer about the person; "what does this project need?" is an answer about the
project. Mixing them leaks subscriptions into projects and dev-mode libraries
across unrelated work, so the global and project files stay separate
([§2.1](#21-the-five-sections)).

**Refresh is pull-only.** Nothing polls on a timer, because that means network
calls the user did not ask for and failures they cannot time. It is also the
*only* network step: once the cache is written, browsing, inspecting and
installing all work offline. A project that refreshed successfully once keeps
working even when every feed it follows is down.

**Resolution stops after one hop** ([§2.3](#23-refresh-the-only-network-operation)).
Otherwise one subscription could transitively pull in arbitrarily many feeds,
each able to add packages to your catalog, with no protocol-level limit on
recursion. You trust who you follow — not everyone they follow.

**Conflicts are resolved at intake, not at refresh.** Adding a source is a
deliberate act where a question fits; refresh is maintenance a user runs to
*avoid* surprises. Prompting there would punish keeping the catalog fresh
([§2.5](#25-conflict-resolution)).

**Soft signals inform; they do not act.** Unavailable feeds, stale rows and
dependency drift are recorded and surfaced, never auto-resolved. A refresh that
pruned stale entries would destroy information; a publish that hard-failed on
drift would block authors at the wrong moment.

### What the Library Manager is not

- **Not a registry.** The class registries belong to the [Library System](../../architecture/library-system/library-system-arch.md). The Library Manager *triggers* a rescan; it does not own registry state.
- **Not a publisher.** It consumes marketplace and marketstall files; producing one is `haywire share`'s job — see the [sharing-libraries guide](../../guides/sharing-libraries.md).
- **Not a build tool.** It does not build wheels, run `uv build`, or run `uv publish`. Releases go through `/haywire-release` and CI — see [publish_releases](../../reference/publish_releases.md).
- **Not a transitive dep resolver.** When a row's `linked_libraries` names other haybale packages, the Library Manager does not install them automatically. The user installs each library individually; uv handles the actual pip-level resolution.
- **Not a curator.** No source is more authoritative than any other in the data. The official haywire feed is one feed among many.
- **Not a trusted namespace.** Two authors may publish the same package name; the collision surfaces as a conflict for the user to settle. That is the price of letting anyone publish without permission.
- **Not a verifier.** No signing, no checksums, no cryptographic trust chain. A consumer who wants assurance reads the source at the install URL before installing.
- **Not a lockfile.** Reproducibility belongs to the project, through ordinary Python tooling. The catalog is a discovery layer, not a build system.

## 9. Worked example — subscribing to the official feed

The user clicks **Add Source** and pastes one URL. The runtime fetches the body,
sees `[[stalls]]` references, and writes a `[[markets]]` subscription to
`~/.haywire/db/haybale_marketplace/marketplace.toml`:

```toml
[[markets]]
url = "https://going-haywire.github.io/haywire/marketplace.toml"
preference = []
blocked = []
```

Add Source then auto-refreshes. The runtime:

1. fetches that URL, caching the body at `~/.haywire/cache/<hash>.toml`;
2. reads its `[[stalls]]` references **one level deep** and fetches each one,
   caching those too;
3. assembles the candidate list and applies the four filters;
4. stamps `via` on each surviving row with the subscription that resolved it;
5. writes the project's `[[caches]]`.

The Library Browser's AVAILABLE section now lists every official haybale. Each
row carries a provenance label derived from `via`: **"via
going-haywire.github.io"** for these, because they arrived through an
aggregator, versus **"from github.com/alice"** for a stall the user subscribed
to directly.

Nothing here touched the user's project source tree, and nothing is installed
yet — the catalog is a list of what *could* be installed.

For a `haywire init --dev` project's `[[heaps]]`, and the shape of the
marketstall being consumed, see
[`marketplace.toml`](../../reference/files/marketplace-toml.md) and
[`marketstall.toml`](../../reference/files/marketstall-toml.md).

## 10. Open questions

- **Lazy library loading.** Every discovered library loads eagerly at startup (see [library-system §4.2](../../architecture/library-system/library-system-arch.md#42-module-resolution-cost)). Should the Library Browser surface a Defer-loading option for heavy libraries?
- **Cross-feed dep resolution.** When a library's `dependencies` lists another haybale package not yet installed, should the Library Manager offer to install both? Currently the user installs each individually.
- **Auto-refresh on a schedule.** Refresh is explicit by design ([§8](#8-why-the-model-is-shaped-this-way)) — but a "refresh on first open of the day" option may be worth exposing.

> **Resolved:** the `haybale-marketplace` carve-out has landed. The Library Browser, Library Overview Editor, `MarketplaceState`, and `LibraryManager` now live in the standalone `barn/haybale-marketplace/` package — see [ADR-0001](../../adr/0001-haybale-marketplace-carveout.md) and [marketplace-canon](marketplace-canon.md).
