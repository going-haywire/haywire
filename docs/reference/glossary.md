---
status: draft
doc_template: glossary
scope: Canonical haywire vocabulary; ubiquitous language with disambiguation
see-also:
---

# Ubiquitous Language

*Domain glossary for the Haywire visual programming system. Use these terms precisely and consistently across all code, docs, and discussions.*

Where a term has a canonical home in this documentation, the **Definition** column links to it. The **Aliases to avoid** column lists synonyms that mean the same thing but blur the vocabulary — prefer the canonical term.

---

## "Library" — five distinct meanings

The word **library** appears five times in haywire with five different meanings. Always use the disambiguated term.

| # | Term | What it is | Canonical home |
|---|---|---|---|
| 1 | **Library** (`BaseLibrary`, `@library`) | The plugin protocol class authored by a developer | [haybale/library](../haybale/library-canon.md) |
| 2 | **Library System** | Framework infrastructure: `LibraryRegistry`, `LibraryDiscovery`, `LibraryIdentity`, `FileWatcher` | [architecture/library-system](../architecture/library-system/library-system-arch.md) |
| 3 | **Haybale package** | Distribution unit: a Python package containing a `BaseLibrary` subclass | [haybale/haybale-package](../haybale/haybale-package-canon.md) |
| 4 | **Library Manager** | The `haybale-marketplace` plugin — the optional in-app package-manager UI | [haybale/marketplace](../haybale/marketplace/marketplace-canon.md) · [arch](../haybale/marketplace/haybale-marketplace-arch.md) |
| 5 | **LibrarySettings / LibraryState** | Per-library scope for cross-cutting subsystems | Chapters inside [components/settings](../components/settings/setting-canon.md) and [components/states](../components/states/state-canon.md) |

---

## "Haybale" — three distinct meanings *(new — marketstall distribution)*

Once the marketstall-distribution spec lands ([`internals/specs/marketstall-distribution.md`](../../internals/specs/archive/marketstall-distribution.md)), the word **haybale** carries three closely-related but distinct meanings. They cluster around the same concept (a haywire library and its distribution metadata) but project it onto different surfaces.

| # | Term | What it is |
|---|---|---|
| 1 | **Haybale** (naming convention) | The pip-distribution naming convention for a haywire library package (`haybale-core`, `haybale-visiongraph`). Also used loosely as a synonym for the package itself. |
| 2 | **`[[haybales]]`** (TOML section) | The TOML section name in `marketstall.toml` (and optionally inside `marketplace.toml`) that lists one or more published library entries. Replaces the older `[[packages]]` section name. |
| 3 | **`Haybale`** (dataclass) | The runtime dataclass representing one entry from a `[[haybales]]` section. Renamed from `MarketplaceEntry`. Fields: `name`, `min_version`, `label`, `description`, `author`, `source`, `install_spec`, `tags`, `os`, `dependencies`, `source_url`, `docs_url`, plus cache-only fields (`via`, `last_seen`, `stale`). |

The three projections relate as: the **dataclass** (3) represents one entry in the **TOML section** (2), which catalogs the **convention** (1). Disambiguate when discussing schema vs. code vs. package names.

---

## Graph & Structure

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Graph** | A container of nodes and edges that describes a visual program; saved as a `.haywire` JSON file. See [architecture/graph](../architecture/graph/graph-arch.md) | Program, blueprint, scene, diagram |
| **Node** | A discrete processing unit in a graph with declared inlets, outlets, and a worker function. See [components/nodes](../components/nodes/node-canon.md) | Block, component, element |
| **NodeWrapper** | The live runtime instance of a node inside a running graph; wraps the user-defined node class | Node instance (ambiguous — use NodeWrapper for the runtime object, Node for the class) |
| **Edge** | A directed connection between an outlet on one node and an inlet on another. See [architecture/execution/edges](../architecture/execution/edges/edges-arch.md) | Connection, wire, link (use only as a verb: "to link an edge") |
| **EdgeWrapper** | The runtime edge object that owns the `link/unlink/detach` lifecycle and the `is_lazy` flag | — |
| **Port** | A typed, directional connection point on a node — either an inlet or an outlet. See [guides/ports](../guides/ports.md) | Pin (avoid for data ports), socket |
| **Inlet** | A port that receives data or control into a node | Input, sink port |
| **Outlet** | A port that emits data or control from a node | Output, source port |
| **Pin** | Acceptable synonym for an EXEC (control) port specifically | — |

---

## Flow Types & Port Kinds

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **FlowType** | The transport category of a port/edge: `DATA`, `CONTROL` (EXEC), `CALLBACK`, or `NONE` | Port type (ambiguous with data type) |
| **DATA port** | A port that carries typed values; outlets fan-out, inlets accept a single source | Value port |
| **EXEC port** | A control port that carries execution order; outlets single-target, inlets multi-source | Control pin (Pin is acceptable colloquially) |
| **CALLBACK port** | A port used for event-style signalling; no hardcoded multiplicity rules. See [architecture/execution/callbacks](../architecture/execution/callbacks/callbacks-arch.md) | Event port (overloaded) |
| **Pooled inlet** | An inlet that accepts multiple sources and delivers them as a `dict[node_id, value]` to the worker | Multi-inlet |
| **Pipe** | The internal transport object for a connected DATA port pair; handles eager push or lazy pull | Channel, stream |

---

## Node Behaviors

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **NodeType** | The execution role of a node (the `NodeType` enum: DATA, CONTROL, EVENT, OUTPUT, LOOPBACK), determined by its EXEC port configuration. `NodeBehavior` is the dataclass that holds this field — prefer **NodeType** in conversation | Node category |
| **DATA node** | A pure value transformer; has no EXEC ports; runs only when its outputs are demanded | Passive node |
| **CONTROL node** | A sequenced node with both EXEC inlet and EXEC outlet; runs in explicit execution order | Active node |
| **EVENT node** | A node with an EXEC outlet but no EXEC inlet; originates an execution chain (timer, callback source) | Source node (ambiguous with data source) |
| **OUTPUT node** | A terminal node with an EXEC inlet but no EXEC outlet; receives execution, produces no further control | Sink node (ambiguous with data sink) |
| **LOOPBACK node** | A CONTROL node that uses the loopback-stack in the VM to implement loops or sequences | Loop node |

---

## Execution Pipeline

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Assembly** | The process of compiling a Graph into executable Flows; performed by `FlowAssemblyManager`. See [architecture/execution/assembly](../architecture/execution/assembly/assembly-arch.md) | Compilation, build |
| **Flow** | An executable unit produced by assembly, rooted at an EVENT node; contains a control flow DAG + per-node data flows. See [architecture/execution/flow](../architecture/execution/flow/flow-arch.md) | Execution graph, pipeline |
| **Control Flow** | The ordered sequence of CONTROL/EVENT/OUTPUT nodes visited during execution; follows EXEC edges | Execution order |
| **LocalizedDataFlow** | The per-control-node data dependency DAG, backpropagated from that node's inlets; only the nodes needed for that step | Global data flow (does not exist) |
| **VM** | The two-stack virtual machine that interprets a Flow: a done-stack (prevents re-execution) + loopback-stack (loops). See [architecture/execution/virtual-machine](../architecture/execution/virtual-machine/virtual-machine-arch.md) | Runtime (too generic), executor |
| **Interpreter** | A per-graph component that drives the VM; owns scheduling, event dispatch, and graph load/unload; each executing **GraphEntry** creates its own instance | Runner, shared interpreter (deprecated — no longer a singleton) |
| **Worker** | The `worker()` method on a node class; the main execution logic called by the VM per node evaluation | Execute, run, process |
| **Frame** | One full execution pass through a Flow from its entry EVENT node to completion | Tick (reserved for the Tick node event), cycle |
| **Eager push** | Data transport mode where a Pipe immediately propagates a new value downstream on write | Synchronous push |
| **Lazy pull** | Data transport mode where a Pipe defers propagation; downstream calls `pull_lazy()` at execution time to get the latest value | Deferred, on-demand (imprecise) |
| **EVAL_MASK / LAZY_MASK** | Per-inlet / per-control-node bitmasks computed during assembly to determine which DATA nodes actually run each step. See [architecture/execution/lazy-evaluation](../architecture/execution/lazy-evaluation/lazy-evaluation-arch.md) | — |

---

## Edge Lifecycle

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **link** | EdgeWrapper operation: functional edge registers at both ports; may displace an existing edge | connect, attach |
| **unlink** | EdgeWrapper operation: edge loses functionality (e.g. adapter broke); removed from active pipes but stays registered | disconnect |
| **detach** | EdgeWrapper operation: edge is explicitly deleted and fully removed from both port dictionaries | destroy, remove |
| **displacement** | When a newly linked edge takes the slot of an existing edge on a single-connection port; the displaced edge stays in `_all_edges` | override, eviction |
| **re-enablement** | When an active edge is removed and the port scans `_all_edges` FIFO for a functional candidate to restore | fallback restoration |
| **Adapter** | A converter object that transforms values between incompatible DATA port types during transport. See [components/adapters](../components/adapters/adapter-canon.md) | Converter (prefer Adapter), transformer |
| **Adapter chain** | An ordered pipeline of one or more Adapters that converts a source type to a compatible sink type | — |

---

## Library & Plugin System

See also the **"Library" — five distinct meanings** table at the top of this glossary.

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Library** | A Python package that contributes nodes, types, adapters, widgets, skins, and/or themes to Haywire; declared with `@library`. See [haybale/library](../haybale/library-canon.md) | Plugin (Library is the canonical term), extension |
| **Library System** | Framework infrastructure that discovers, loads, and tracks libraries: `LibraryRegistry`, `LibraryDiscovery`, `LibraryIdentity`, `FileWatcher`. See [architecture/library-system](../architecture/library-system/library-system-arch.md) | "Library" alone (ambiguous) |
| **Library Manager** | The in-app UI for installing, inspecting, and uninstalling Haybale packages. Shipped as the optional `haybale-marketplace` plugin. See [haybale/marketplace](../haybale/marketplace/marketplace-canon.md) and its [architecture](../haybale/marketplace/haybale-marketplace-arch.md) | "Library" alone (ambiguous), package manager |
| **Library Browser** | The left-slot editor that lists installed and marketplace-available libraries with filter toggles (REQUIRED, ENABLED, DISABLED, AVAILABLE). Distinct from the Library Manager, which is the broader subsystem. *(new)* | — |
| **Library Overview Editor** | The main-slot editor that shows one library's identity, components, and Edit / Enable / Disable / Uninstall actions; reached by selecting a library in the Library Browser. *(new)* | Library detail editor |
| **Haybale** | The naming convention for a Haywire library package (e.g. `haybale-core`, `haybale-visiongraph`). See [haybale/haybale-package](../haybale/haybale-package-canon.md) | — |
| **Barn** | The monorepo folder containing all local haybale plugin libraries (`barn/`) | Library folder |
| **register_components()** | The required method on `BaseLibrary` that scans subfolders and registers all library contributions | setup, initialize |
| **Hot-reload** | The live reload of a library's components on file change without restarting the app; enabled by `file_watcher=True`. See [architecture/hot-reload](../architecture/hot-reload/hot-reload-arch.md) | Live reload, auto-reload |
| **entry_point** | The `pyproject.toml` declaration under `haywire.libraries` that makes a package discoverable | Registration |
| **Post-install requirements** | Two `@library(...)` flags — `needs_refresh` and `needs_restart` — declared by a library author and surfaced by the install/uninstall flow as a terminal-state prompt. `needs_refresh=True`: installing the library registers new Vue components or JS resources that the running browser tab cannot pick up; user must reload the page. `needs_restart=True`: installing or uninstalling leaves the Python process in a state requiring a Studio restart (typically C-extension modules, haywire-core upgrades, or import-time global mutation); symmetric to uninstall. Both default to False; trust-the-author model — no auto-detection. Read by `LibraryManager.install()`/`.uninstall_streaming()`, unioned across newly-imported and evicted libraries, returned to the install-progress modal as `PostInstallHints`. | `requires_browser_refresh`, `requires_app_restart` (verbose), reload flag |
| **Marketstall** | A TOML file hosted by a library author that lists their published haybale packages (`[[haybales]]`) consumed as a remote feed by haywire projects. Produced by `haywire share`. Lives at `marketstall.toml` in the repo root. Any author can host their own; the haywire monorepo publishes its official one to GitHub Pages. | marketplace snippet, package feed |
| **Marketplace** | The aggregated catalog of haybales visible in the Library Manager's AVAILABLE section; built by merging the project's local `[[heaps]]` with all remote subscriptions (`[[markets]]` + `[[stalls]]`) resolved into `[[caches]]` by refresh. Multiple remote feeds are supported. | package list, library catalog |
| **haybale-marketplace** | The optional haybale package (`barn/haybale-marketplace/`) that owns the Library Manager UI — the library browser/overview/component/source editors, `MarketplaceState`, and the `LibraryManager` install/uninstall service. Carved out of `haybale-studio` per [ADR-0001](../adr/0001-haybale-marketplace-carveout.md); the studio runs without it. The directory `~/.haywire/db/haybale-marketplace/` holds the user's global marketplace file. See [haybale/marketplace](../haybale/marketplace/marketplace-canon.md). | Library Manager (the plugin); marketplace dir (the `~/.haywire/db/` path) |
| **README.md** | Fully generated landing page for a haybale package. Lives at the package root (not shipped in wheel). Content: `NOTES.md` verbatim (if present) followed by the component catalog (identical to `OVERVIEW.md`), plus any `<!-- marketstall:share-url -->` marker blocks preserved verbatim. Rendered by PyPI (`info.description`) and git platforms — the universal pre-install discovery document reachable via every distribution method. Generated by `haywire-gen-docs` in the same pass as `OVERVIEW.md`. The marker blocks are managed by `haywire share --save` (spec §6.6); gen-docs preserves them so the two skills compose. | — |
| **OVERVIEW.md** | Fully generated component catalog for a haybale package. Lives inside the Python module directory (ships in wheel). Read from disk post-install by the Library Manager via `lib.identity.folder_path`. Contains the catalog only — no `NOTES.md` prefix. `docs_url` in the marketstall points here for pre-install discovery. | — |
| **QUICKREF.md** | Fully generated compact reference for a haybale package. Alphabetical, key-value format, no prose. One line per component field. Lives inside the Python module directory (ships in wheel). | — |
| **NOTES.md** | Hand-authored supplement inside the Python module directory (ships in wheel). Design rationale, known quirks, interaction patterns, example graph descriptions. Never touched by `haywire-gen-docs`. Prepended verbatim to the generated `README.md`; appended as "Additional Notes" in `OVERVIEW.md`. | LIBRARY.md (old name, deprecated) |
| **haywire-gen-docs** | The Claude skill that generates `README.md`, `OVERVIEW.md`, `QUICKREF.md`, and per-component `docs/` for a haybale package in one pass. Syncs docstrings first. Uses sha256 hashes to skip unchanged per-component docs. Preserves `<!-- marketstall:share-url -->` marker blocks in the README verbatim (spec §6.6). Never modifies `NOTES.md`. | — |

---

## Marketstall distribution runtime

The runtime that backs the Library Browser's Refresh / Add Source / Edit File flow. Spec: [`internals/specs/marketstall-distribution.md`](../../internals/specs/archive/marketstall-distribution.md). Code: `haywire.core.marketstall`.

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Global marketplace** | The user-scoped `~/.haywire/db/haybale-marketplace/marketplace.toml`. Holds the user's opt-in subscriptions (`[[markets]]`, `[[stalls]]`) and optionally inline `[[haybales]]`. Per-machine, never project-scoped. The `db/haybale-marketplace/` subdirectory is a forward reference to the planned **haybale-marketplace** library carve-out. | user marketplace |
| **Project marketplace** | The project-scoped `<project>/.haywire/marketplace.toml`. Holds the project's own `[[heaps]]` (written by `haywire init`, including dev-repo libraries under `--dev`) and the `[[caches]]` populated by refresh. Never has `[[markets]]` or `[[stalls]]`. | project file |
| **`[[markets]]`** | TOML section in the global marketplace declaring subscriptions to *remote marketplace feeds*. Each entry: `url`, `ignores`, `doubles`, `blocked`. Renamed from `[[marketplaces]]` (spec §14). | `[[marketplaces]]` (legacy schema) |
| **`[[stalls]]`** | TOML section declaring subscriptions to *remote marketstall feeds* (single-author publish files). Each entry: `url`, `ignores`, `doubles`, `blocked`. Renamed from `[[marketstalls]]`. | `[[marketstalls]]` (legacy schema) |
| **`[[haybales]]`** | TOML section listing one or more publishable library entries. Lives in `marketstall.toml` files; may also appear inline in `marketplace.toml` (PyPI-only / aggregator-publisher case). Replaces the older `[[packages]]` section name. | `[[packages]]` (legacy schema) |
| **`[[heaps]]`** | TOML section in the project marketplace declaring path-based libraries (always installed editably). Written by `haywire init`; manually editable. Renamed from `[[locals]]`. | `[[locals]]` (legacy schema) |
| **`[[caches]]`** | TOML section in the project marketplace holding the refresh result. Each entry is a fully-formed `Haybale` plus cache-only fields (`via`, `last_seen`, `stale`). Renamed from `[[packages]]` (project shape). | `[[packages]]` (project shape; legacy schema) |
| **Subscription** | A `[[markets]]` or `[[stalls]]` entry in the global marketplace — the user's opt-in to follow a remote feed. Identified by URL. Idempotent: re-adding the same URL is a no-op. | feed, source (overloaded) |
| **`ignores`** | Per-subscription array of names skipped from that source. Populated by the conflict-resolution prompt at Add Source time. Soft preference — the user picked another source. | skip list |
| **`blocked`** | Per-subscription array of names the user actively rejected via the install-safety modal (§7.4). Stronger than `ignores`: blocked haybales are hidden from the Library Browser entirely and filtered out of the stale-rescue step so they never survive as `stale=True`. Un-blockable only by editing the marketplace file. | denylist (don't use — it's not a denylist, it's per-subscription) |
| **`doubles`** | Per-subscription array of names that two `[[markets]]` entries silently dedup to. Diagnostic only. | — |
| **Refresh** | The orchestrator (`haywire.core.marketstall.refresh`) that fetches every subscribed feed, resolves the candidate haybale list, applies `blocked`/`ignores`/heaps shadow/FCFS, and writes the result to the project `[[caches]]`. Triggered by Refresh button or auto-fires after Add Source. | sync, update |
| **One-level-deep resolution** | The hard limit on remote-marketplace chains: a remote marketplace's own `[[markets]]` entries are ignored — only its `[[stalls]]` URLs and inline `[[haybales]]` are consumed. Prevents infinite recursion and bounds the refresh blast radius. | recursive resolution |
| **Haybale (dataclass)** | The canonical dataclass for one entry available to install. Fields: `name`, `min_version`, `label`, `description`, `author`, `source` (`"pypi"` / `"git"` / `"local"`), `install_spec`, `tags`, `os`, `dependencies`, `source_url`, `docs_url`, plus cache-shape fields (`via`, `last_seen`, `stale`) and source-tagging fields. Code: `haywire.core.marketstall.types`. Renamed from `MarketplaceEntry`. | `MarketplaceEntry` (legacy name) |
| **Subscription (dataclass)** | The frozen dataclass for one `[[markets]]` or `[[stalls]]` entry: `url`, `ignores`, `doubles`, `blocked`. Renamed from `RemoteSubscription`; gained the `blocked` field. | `RemoteSubscription` (legacy name) |
| **Conflict resolution** | The four-filter rule applied during refresh: `blocked` per subscription, then `ignores` per subscription, then heaps shadow (heaps always win), then first-come-first-served as the final safety net. Spec §8.2. | — |
| **Stale** | Flag set on a project `[[caches]]` entry when a subsequent refresh did NOT re-resolve it. Renders as a red dot + "(stale)" suffix in the Library Browser. Stale + uninstalled entries are user-removable via the trash icon; stale + installed entries are locked until uninstalled. | outdated, expired |
| **`os` field** | Per-haybale list of supported platforms. Declarable values: `"macos"`, `"windows"`, `"linux"`. Source: each library's `pyproject.toml [tool.haywire].os`; copied into marketstalls by `haywire share`. Absent = "all platforms." `"other"` is the runtime sentinel for unmapped `platform.system()` results; never a declarable value. | — |
| **RefreshOutcome** | Tri-state per-subscription refresh result: `FRESH` (HTTP 200, cache overwritten), `CACHE_FALLBACK` (HTTP failed, served from cache), `UNAVAILABLE` (HTTP failed, no cache). | — |
| **RefreshReport** | Dataclass returned by `refresh()`: `sources_fetched`, `sources_from_cache`, `sources_unavailable`, `unavailable_urls`, `haybales_resolved`, `new_stale`, `updates_available`. The three `sources_*` counters partition the active subscription set. | — |
| **MarketplaceState** | The `AppState` that owns marketplace orchestration. The UI calls `state.refresh()`, `state.get_global()`, `state.get_project_haybales()`, `state.remove_stale_haybale()` — never `haywire.core.marketstall` functions directly. | — |
| **MalformedMarketplaceError** | Raised when a marketplace or marketstall file is invalid (TOML parse or schema violation). Library Manager surfaces this with an Edit File banner; the UI does not recover automatically. Renamed from `MalformedGlobalMarketplaceError`. | — |
| **HTTP cache** | `~/.haywire/cache/<url-hash>.toml`, one file per subscribed URL. Populated on successful fetch; consulted on fetch failure as a fallback. No TTL. Orphan cache files (no matching active subscription) are GC'd at end of each refresh. | — |
| **Host provider** | One git host's URL conventions. Protocol with `parse_blob_url` / `parse_raw_url` / `raw_url` / `blob_url` methods. GitHub and GitLab ship in the first cut; Bitbucket and Gitea are deferred. Self-hosted instances declare themselves in `~/.haywire/config.toml`. | — |
| **Blob URL** | The browser-friendly URL to a file on a git host (e.g. `https://github.com/alice/cool-libs/blob/main/marketstall.toml`). Canonical persisted form for `[[markets]]` and `[[stalls]]` subscriptions. | — |
| **Raw URL** | The fetch-friendly URL to a file's content (e.g. `https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml`). What the runtime actually HTTP-fetches. | — |
| **Marketstall** | A TOML file hosted by a library author that lists their published haybale packages; consumed as a remote feed by haywire projects. Produced by `haywire share`. Lives at `marketstall.toml` in the repo root (single-author) or `stalls/<dist-name>.toml` (aggregator layout). | marketplace snippet, package feed |
| **Marketplace** | The aggregated catalog of haybales visible in the Library Manager's AVAILABLE section. Built by merging the project's local `[[heaps]]` with all remote subscriptions (`[[markets]]` + `[[stalls]]`) resolved into `[[caches]]` by refresh. | package list, library catalog |
| **Install-safety modal** | Three-button modal (Cancel / Block source / Install) interposing between every Install click and the actual `uv pip install`. Spec §7.4. Shows the haybale's `source_url` as a clickable link; Block writes the haybale's name to the resolving subscription's `blocked` array. Fires on every Install — there's no first-time-only suppression. | first-install modal (legacy term) |
| **Drift gate** | The `detect_share_drift()` check that runs at `haywire share` time. Three checks: `pyproject_missing` (imports not declared in `pyproject.toml`), `decorator_missing` (imports not declared in `@library(dependencies=[...])`), `pyproject_version_lag` (declared haybale floors lagging the installed version). `--strict` exits non-zero on drift; `--fix` auto-rewrites. Spec §12. | — |
| **`pyproject_version_lag`** | Field on `DepDrift` carrying `(dist_name, declared_floor, installed_version)` tuples for declared haybale-* deps whose `~=`/`>=`/`>` floor is below the installed version. Haybale-only by design — third-party deps are not lag-checked because the installed-version-as-truth assumption breaks outside the lockstep haybale ecosystem (spec §12.1). | — |
| **`updates_available`** | `RefreshReport` field counting installed haybales whose cache `min_version` exceeds the installed distribution version. Drives the post-refresh toast count and the per-row ▲ indicator + "v0.X.X available" hint in the Library Browser. Informational only — nothing auto-updates. | update count |
| **Aggregator layout** | The two-tier feed shape used by the official haywire marketplace (spec §11): a top-level `marketplace.toml` with one `[[stalls]]` entry per library, plus a `stalls/` subdirectory with one marketstall file per library. Consumers can subscribe to the full feed (via the marketplace URL) or to a single library (via that stall's URL). Produced by `scripts/generate_marketstall.py`. | per-haybale stall layout |
| **Bare-repo URL rejection** | Add Source refuses URLs that are just a repo (`https://github.com/alice/cool-libs`) with no file path — the resolver can't know whether to fetch `marketstall.toml` or a `marketplace.toml` from such a URL. The dialog asks for the blob/raw URL to the specific file. Spec §4.2. | — |

---

## Dependency manifests & drift *(new)*

A haybale library's dependencies live across three manifests with different audiences. They can drift; haywire provides tools to detect and reconcile.

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Project pyproject** | `<project>/pyproject.toml`. Audience: uv (workspace resolution). Lists what the *project* needs to run during dev. Never travels with a published library. | root pyproject (acceptable, less precise) |
| **Library pyproject** | `<library>/pyproject.toml`, e.g. `barn/haybale-foo/pyproject.toml`. Audience: pip / PyPI / `haywire share` consumers. The `[project] dependencies` here is what travels with the published library and what pip resolves at install time. | package pyproject |
| **`@library(dependencies=[...])`** | The decorator parameter inside a library's `__init__.py`. Audience: haywire's runtime (LibraryManager). Lists which *other haywire libraries* must be enabled for this one to enable; gates Disable / Uninstall buttons via `get_installed_dependents()`. Uses underscore module names (e.g. `"haybale_core"`), NOT distribution names. | library deps (ambiguous), runtime deps |
| **Three manifest layers** | The conceptual triple — source imports / `@library` decorator / library pyproject — that must agree for a library to ship cleanly. When they diverge (drift), `haywire share` may publish a package whose declared deps lie about what it needs. | — |
| **detect_deps()** | Pure function in `haywire.core.library.dep_detect`. Statically AST-scans a library's source, resolves imports to distributions, and returns a `DetectedDeps` with one list shaped for the `@library` decorator and another shaped for the library's pyproject. | — |
| **DetectedDeps** | Frozen dataclass returned by `detect_deps`. Fields: `library_decorator` (underscored module names of registered haywire libraries imported from source), `pyproject` (distribution names + version specifiers — framework, registered libraries, and third-party), `resolved` (module → distribution map), `unresolved` (imports that couldn't be mapped). | — |
| **HaywireLibrarySource** | Protocol with `list_names()` and `get_library_distribution_name(id)`. The authoritative answer to "is this distribution a haywire library?" — by registration, not by name pattern. Live registry satisfies it; tests pass a fake. | — |
| **EntryPointLibrarySource** | `HaywireLibrarySource` implementation backed by `importlib.metadata.entry_points(group="haywire.libraries")`. Used by CLI flows (`haywire share`) that don't bootstrap the haywire runtime. | — |
| **Detect Dependencies button** | The magnifying-glass button next to the Dependencies field in the Library Overview Editor's Edit dialog. Runs `detect_deps`, opens a diff modal showing what would change, offers Union or Replace as the apply mode. | Scan deps button |
| **Drift gate** | The pre-publish check inside `haywire share` / `haywire share --save`. Default: warn-only on stderr. `--strict`: exit non-zero if any library has missing manifest entries. `--fix`: auto-correct by writing the missing entries to disk. | — |
| **DepDrift** | Dataclass from `haywire_studio.share` recording one library's missing entries. Fields: `lib_dir`, `pyproject_missing`, `decorator_missing`, `unresolved`. `has_drift` is True iff either missing-list is non-empty. The gate flags missing entries only; extra (declared but unused) deps are not flagged. | — |
| **DriftError** | Raised by `share_save_repo` in `--strict` mode when any library has drift. Aborts before any `marketstall.toml` is written. | — |
| **Diff modal** | The `haywire.ui.modals.diff_modal` Popup that previews proposed changes and offers up to two action buttons + Cancel. Used by Detect Dependencies (Union / Replace). Generic — any "preview changes, choose how to apply" surface can reuse it. | — |
| **DiffSection** | One labelled block inside a diff modal: title + additions (green `+`) + removals (red `−`) + unchanged (dim) + optional note. | — |
| **Union (apply mode)** | The additive apply: current ∪ detected for each manifest. Never removes; safe against false positives from dynamic imports. | merge |
| **Replace (apply mode)** | The destructive apply: detected only. Drops anything not detected. Useful for cleaning up obsolete declarations; risky against dynamic imports. | overwrite |

---

## Settings System

See [architecture/settings](../architecture/settings/settings-arch.md) for the resolution chain and registry mechanics; see [components/settings](../components/settings/setting-canon.md) for authoring.

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **NodeSettings** | Base class for node-local settings; subclassed as an inner class on a `@node` class; class name becomes the accessor (`self.filter`, `self.output`, etc.); never registered with the global registry | Config, options, Bag, Settings (avoid bare Settings for node inner classes) |
| **FrameworkSettings** | Base class for framework/app-defined settings schemas; subclassed with `namespace=`; auto-registers via `_pending_global` at registry init; `cls._registry` is set by the registry so instances need no explicit injection | — |
| **LibrarySettings** | Base class for library plugin-defined settings schemas; subclassed with `namespace=`; registered via `BaseRegistry` hot-reload machinery; same `cls._registry` auto-wiring as `FrameworkSettings` | — |
| **setting()** | The descriptor that declares a typed, serializable field within any `Settings` subclass | option, param, prop |
| **mirrors** | A `setting()` parameter that links a node field to a `FrameworkSettings` or `LibrarySettings` field, inheriting its default with per-node override capability | shadow, reference |
| **read_only** | A `setting()` parameter (used with `mirrors=`) that makes a field a silent cache of a global value: invisible in panel, never stored, never writable per-instance | watch (avoid), computed |
| **accessor name** | The inner `NodeSettings` class name as it appears on the node instance (e.g. `class filter` → `self.filter`); must not collide with existing `BaseNode` attributes | settings name, bag name |
| **SettingsRegistry** | The central registry that holds all global setting schemas and their TOML-sourced values; used for the full resolution chain; inherits `BaseRegistry` hot-reload machinery | — |
| **Three-tier resolution** | The precedence chain for a settings value: global TOML override → workspace TOML override → local instance value → workspace TOML set → global TOML set → descriptor default | — |
| **cache** | Transient, non-serialized per-node storage for computation buffers or memoization | temp, scratch |
| **store** | Persistent, serialized per-node internal state not shown in the UI | private state |

---

## Graph Management

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **GraphEntry** | A runtime container for one open graph: holds the **Graph**, **Editor**, file path, unsaved flag, session set, and per-graph **Interpreter**. Concrete implementation of the **GraphContainer** protocol in `haybale-haystack` | Graph slot, graph handle |
| **GraphContainer** | A protocol implemented by anything that can host a graph in **GraphEditor**: requires `binding_id`, `editor`, `path`, `unsaved`, `display_name`, and `save()`. **GraphEntry** is the haystack-flavoured implementation. See [haybale-graph-editor](../../barn/haybale-graph-editor/) | Graph host, graph holder |
| **GraphAppState** | The app-wide registry mapping `binding_id` → **GraphContainer**. Source libraries (haystack, future cloud-graph libraries) `register` / `unregister` / `rekey` their containers here; **GraphEditor** reads from it on every render. Lives at `app_data[GraphAppState]` | Graph registry, graph index |
| **Haystack** | A named, curated selection of **GraphEntry**'s stored as a TOML file in `haystacks/`; records which graphs are open and which should auto-execute on load. See [architecture/graph](../architecture/graph/graph-arch.md) | Session (overloaded with browser sessions), workspace (overloaded with layout), setlist, graphset |
| **HaystackEditor** | The left-slot editor that lists all open graphs, provides play/stop per row, and save/load haystack actions in the header | GraphManagerEditor (renamed) |

---

## UI / Workspace System

See [architecture/studio](../architecture/studio/studio-arch.md) for the studio as a product; [components/editors](../components/editors/editor-canon.md), [components/panels](../components/panels/panel-canon.md), [components/themes](../components/themes/theme-canon.md), [components/skins](../components/skins/skin-canon.md) for authoring.

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Editor** | A full-slot UI component occupying one workspace Slot (Left, Main, Right, Bottom); one instance per slot per session | Panel (Panels are sub-components of editors), view |
| **Panel** | A context-sensitive sub-section rendered inside a panel-aware editor (e.g. Properties); appears/disappears based on `poll()`; always wrapped in `.hw-panel` container | Tab, widget (too generic) |
| **Scope** | A named tab within a panel-aware editor that groups panels (e.g. `node`, `graph`, `edge`) | Context (overloaded), category |
| **Slot** | One of the four named positions in the AppShell where an editor is mounted: Left, Main, Right, Bottom; each slot = bar + area | Area (deprecated), pane, region, zone |
| **Bar** | The control strip attached to a Slot; either a tab bar (horizontal, for Main/Bottom) or an icon bar (vertical, for Left/Right) | — |
| **default_slot** | The `@editor()` decorator parameter and `EditorIdentity` field that declares which Slot an editor occupies by default; one of `'left'`, `'main'`, `'right'`, `'bottom'` | canvas_area (deprecated) |
| **SlotState** | Dataclass representing the persisted state of the Left or Right slot: `active_tab_key`, `visible`, `size` | AreaState (deprecated) |
| **MainSlotState** | Dataclass representing the Main slot's persisted state: a list of `TabState` tabs plus `active_tab_key` | MiddleAreaState (deprecated) |
| **BottomSlotState** | Dataclass representing the Bottom slot's persisted state: tab list, `active_tab_key`, `visible`, `size` | BottomAreaState (deprecated) |
| **TabState** | Dataclass for one tab within a tabbed slot (Main or Bottom): `editor_key`, `label`, `metadata` | — |
| **active_tab_key** | The unified field on all slot state dataclasses that stores which editor is currently shown in that slot | editor_key (on slot state — deprecated), left_bar_active, right_bar_active (removed) |
| **AppShell** | The top-level layout component composed of: TopBar + ActivityBar + Left/Main/Right/Bottom Slots + ContextBar + StatusBar. See [architecture/studio/app-shell](../architecture/studio/app-shell/app-shell-arch.md) | Shell, frame |
| **TopBar** | The 48px bar along the top edge of the AppShell; contains the app name, workspace switcher, and global actions | Header, navbar |
| **StatusBar** | The 24px bar along the bottom edge of the AppShell; shows session info and status messages | Footer, info bar (Info Bar is a Panel pattern, not the StatusBar) |
| **ActivityBar** | The 48px icon bar on the left edge; switches editors in the Left Slot; styled with `hw-slot-bar hw-slot-bar-icons` | Left sidebar, toolbar |
| **ContextBar** | The 48px icon bar on the right edge; switches editors in the Right Slot; styled with `hw-slot-bar hw-slot-bar-icons` | Right sidebar |
| **MainTabBar** | The horizontal tab bar above the Main Slot; switches between tabbed main editors; styled with `hw-slot-bar hw-slot-bar-tabs` | Middle tabs |
| **BottomTabBar** | The horizontal tab bar above the Bottom Slot; switches between tabbed bottom editors; styled with `hw-slot-bar hw-slot-bar-tabs` | Bottom tabs (use only for the metadata key) |
| **hw-slot-bar** | CSS base class for all slot bars (both icon bars and tab bars) | hw-tabs (deprecated) |
| **hw-slot-bar-tabs** | CSS modifier for horizontal tabbed slot bars (MainTabBar, BottomTabBar) | hw-tabs (deprecated) |
| **hw-slot-bar-icons** | CSS modifier for vertical icon slot bars (ActivityBar, ContextBar) | — |
| **ScopeToolbar** | The vertical strip of 36×36px square buttons inside the PropertiesEditor that switches the active Scope | Scope bar, scope selector |
| **Session** | A per-browser-connection state object; one per connected client. See [architecture/session-and-state](../architecture/session-and-state/session-and-state-arch.md) | Connection, client |
| **SessionContext** | The state bag passed to every editor and panel render call; contains active graph, node, edge, and theme references | Context (acceptable shorthand), state |
| **Workspace** | A named layout preset that records which editor occupies each slot; saved to `.haywire/workspace_state.json`. See [architecture/studio/workspace](../architecture/studio/workspace/workspace-arch.md) | Layout, perspective |
| **Skin** | A `BaseSkin` subclass that renders the visual shape of a node on the Graph Canvas; operates outside the `.hw-panel` cascade and uses only `--hw-node-*` and `--hw-canvas-*` tokens. See [components/skins](../components/skins/skin-canon.md) | Renderer (Skin is canonical in code), style |
| **Widget** | An inline UI control rendered inside a port on the node card, bound to the port's value. See [components/widgets](../components/widgets/widget-canon.md) | Control, field input |
| **Theme** | A named set of CSS tokens (`WorkbenchTheme`) or per-node-type colour rules (`NodeTheme`); session-scoped for workbench. See [components/themes](../components/themes/theme-canon.md) | Style, skin (Skin is distinct) |
| **Graph Canvas** | The Vue/NiceGUI hybrid component where nodes and edges are visually displayed and edited. See [architecture/studio/canvas](../architecture/studio/canvas/canvas-arch.md) | Canvas (acceptable shorthand), viewport |
| **hui** | The `haywire.ui.elements` wrapper module; encodes design-system rules into reusable Python functions; prefer `hui.*` over raw NiceGUI/Quasar calls for any pattern it covers | haywire.ui.elements (use `hui` as the import alias) |
| **CSS token** | A `--hw-*` CSS custom property that encodes a design-system value (colour, size, shadow); every structural colour in the app must reference a token, never a hardcoded value | CSS variable (CSS token is the project term) |
| **Compact-fields** | A container-query–based responsive layout system for dense settings/property panels; activated by the `compact-fields` CSS class on the outer column | Dense layout, settings layout |
| **Ghost pin** | The visual indicator (low-opacity colour via `--hw-ghost-pin`) on a port that is unconnected; rendered by node skins | Unconnected pin, empty pin |

### Modals *(new)*

`haywire.ui.modals` — the canonical set of reusable Popup-based modal dialogs. Use these instead of inline `ui.dialog()` for any new modal UI; the per-modal helpers carry the design-guide chrome (`--hw-popup-shadow`, `--hw-bg-elevated`, `--hw-border-strong`) and stack above legacy Quasar dialogs at z-index 7000/7001.

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Popup** | The shared Vue component all haywire modals are built on. Centered or position-fixed, with optional backdrop, escape-close, and backdrop-click-close. Internal — modal authors use the helper functions below. | — |
| **info_modal** | Single icon + title + message + OK button. Non-destructive notifications, blocked actions, status reports. | — |
| **confirm_modal** | Title + message + Confirm/Cancel. Use `danger=True` for destructive confirms. | — |
| **pick_modal** | Title + single-select dropdown + Confirm/Cancel. Pre-populated to the first option. | — |
| **rename_modal** | Title + single name input with live classification (same / changed / existing collision) + Confirm/Cancel. The confirm button relabels per state. | — |
| **save_as_modal** | The path-prompt variant of rename_modal: directory + filename input with extension control. | — |
| **diff_modal** | Title + sectioned diff body (DiffSection blocks) + up to two action buttons + Cancel. Used by Detect Dependencies; reusable for any "preview changes, pick how to apply" surface. *(new)* | — |

### Editor instance-mode terms

- **`OpenBehavior`** — Enum on `EditorIdentity` declaring how an editor's
  tabs come into being. Three values (members are uppercase; `.value`
  strings are lowercase):
  - **`REQUIRED`** (`"required"`): exactly one tab, always present,
    auto-populated at startup, uncloseable.
  - **`ON_CONTEXT`** (`"on_context"`): singleton tab, on-demand. Content
    mirrors a slice of session context; the tab has no binding_id.
    Closeable. Not persisted.
  - **`ON_PAYLOAD`** (`"on_payload"`): per-binding_id tab, on-demand. The
    `binding.binding_id` is both the tab's identity and its content source.
    N tabs allowed. Closeable. Persisted across restart.
- **`on_focus`** — `BaseEditor` lifecycle hook called by `Slot._activate` when a
  binding transitions from not-active to active. Editors that own a slice of
  session state (e.g. `GraphEditor` owns `active_graph`) override it to mutate
  the context and broadcast the corresponding event. Replaces the shell-side
  `context_field` / `OPEN_GRAPH_REQUESTED` dispatch.
- **`binding_id` (tab)** — A `str` that disambiguates per-binding_id tabs of
  the same editor class. For GraphEditor the binding_id is the graph path;
  for FileViewer it is the file path. Stored in `TabState.metadata.binding_id`
  and mirrored in `EditorWrapper.binding_id`. The same string is the key used
  in `GraphAppState`, the workspace-persisted identity in `slot.to_snapshot`,
  and the disambiguator in `EditorWrapper.editor_binding_id`.

---

## Signals

See [guides/signals.md](../guides/signals.md) for authoring patterns; [architecture/studio](../architecture/studio/studio-arch.md) §2.5 for the bus dispatch model.

| Term | Definition | Aliases to avoid |
| ---- | ---------- | ---------------- |
| **Signal** | The base class for everything dispatched on the per-session bus. Frozen dataclass with `kw_only=True`; `cross_session: ClassVar[bool] = False` controls broadcast routing. See [`session/signals/signal.py`](../../packages/haywire-core/src/haywire/core/session/signals/signal.py) | Event (deprecated; was the old base class), message |
| **CommandSignal** | A `Signal` subclass for imperatives — "do X" rather than "X happened". Concrete commands include `Reveal`, `Close`, `BroadcastClose` | LifecycleCommand (deprecated; was the old name) |
| **SignalBus** | Per-session typed pub/sub. One instance per **Session**; subscribers register a handler for an exact `Signal` subclass; publishes fan out by `type(signal)` exact match. See [`session/signals/bus.py`](../../packages/haywire-core/src/haywire/core/session/signals/bus.py) | EventBus (deprecated) |
| **SignalSource** | Abstract base class that hosts of `signal_field`s must inherit. Concrete implementors: `SessionContext`, `SessionState`, `AppState`. Declares the `@abstractmethod _signal_emit(signal)` contract | — |
| **signal_field** | Descriptor declaring a reactive field on a `SignalSource` subclass. Writes emit a synthetic `Signal` subclass keyed by the field reference; reads return the stored value via bare attribute access. See [`session/signals/descriptor.py`](../../packages/haywire-core/src/haywire/core/session/signals/descriptor.py) | reactive_field (deprecated) |
| **Synthetic signal class** | The `Signal` subclass generated by `signal_field` at class-definition time, one per (host_class, attr_name) pair. Accessed via class-level attribute (`SessionContext.active_file`). Used as the subscription key | — |
| **Hand-authored signal** | A `Signal` (or `CommandSignal`) subclass declared explicitly by a library or framework author. Carries payload fields. Emitted via `session.publish(signal_instance)` | Custom event class (use "hand-authored signal") |
| **`_signal_emit`** | The publish method on `SignalSource` subclasses. `SessionContext` forwards to `self.session.publish`; `SessionState` derefs `self.session()` weakref; `AppState` derefs `self._session_manager()` and calls `broadcast`. Internal — never called directly by author code | — |
| **`cross_session`** | `ClassVar[bool]` on a `Signal` subclass; when `True`, `Session.publish` routes via `SessionManager.broadcast` so every session receives the signal. Auto-set to `True` for synthetic signals on `AppState` hosts | — |
| **`@redraw_on(*signal_types)`** | Editor / panel handler decorator. Subscribes the method to each signal type; after dispatch, the framework calls `wrapper.redraw()` exactly once per pass. Accepts both synthetic-signal class references (`SessionContext.active_file`) and hand-authored `Signal` subclasses | `@redraw_on(*event_types)` (parameter renamed) |
| **`@react_on(*signal_types)`** | Editor / panel handler decorator for pure side-effects without redraw. Same subscription model as `@redraw_on`; only differs in that the framework does not call `redraw()` after | — |
| **Reactive field** *(historical)* | The pre-unification term for what is now a **signal_field**. The old `Reactive[T]` wrapper, `.value` accessor, and `iter_reactive_fields` helper were deleted in the signal-field unification | Use **signal_field** going forward |
| **Signal-defining library** | The library that declares a `Signal` subclass (or hosts a `signal_field`). Subscribers in other libraries must list it in their own `LibraryIdentity.dependencies` so hot-reload reloads them as a pair — otherwise `isinstance` checks after a reload spuriously return `False` | — |

---

## Relationships

- A **Graph** contains zero or more **Nodes** and **Edges**; it is serialized as a `.haywire` file.
- An **Edge** connects exactly one **Outlet** to exactly one **Inlet**; they must share the same **FlowType** or can be cast to a different type with the help of an **Adapter chain**.
- A **Node** (class) defines **Ports** in `init()`; the **NodeWrapper** holds the live runtime state.
- Each connected DATA port pair owns exactly one **Pipe**; the Pipe's `is_lazy` flag comes from the **EdgeWrapper**, not the port.
- **Assembly** produces one **Flow** per **EVENT node** in the graph.
- A **Flow** contains one global **Control Flow** DAG and one **LocalizedDataFlow** DAG per CONTROL node.
- A **Library** scans folders in `register_components()` to populate registries (nodes, types, adapters, widgets, skins, themes).
- A **Haybale** package is always a **Library**; not all Libraries are distributed as haybale packages.
- An **Editor** occupies one **Slot** in the **AppShell**; an **Editor** may host many **Panels** filtered by **Scope**.
- The **AppShell** is composed of: **TopBar**, **ActivityBar**, **ContextBar**, **StatusBar**, and the four **Slots** (Left, Main, Right, Bottom).
- Each **Slot** has a **Bar** and an area: Left and Right slots have icon bars (**ActivityBar**, **ContextBar**); Main and Bottom slots have tab bars (**MainTabBar**, **BottomTabBar**).
- The **ActivityBar** switches editors in the Left **Slot**; the **ContextBar** switches editors in the Right **Slot**; the **ScopeToolbar** (inside the PropertiesEditor) switches the active **Scope**.
- Each slot's state is tracked by a **SlotState** (Left/Right), **MainSlotState** (Main), or **BottomSlotState** (Bottom); all use **active_tab_key** to identify the currently-shown editor.
- A **Panel** is always rendered inside a `.hw-panel` container and must use `hui.*` wrappers for any pattern covered by the design guide.
- A **Skin** renders on the **Graph Canvas** and must use only `--hw-node-*` / `--hw-canvas-*` **CSS tokens**; it must not use `hui.*` panel wrappers.
- Every structural colour reference in the app must use a **CSS token** (`--hw-*`); hardcoded hex or rgba values are a design violation.
- A **Node** may declare one or more **NodeSettings** inner classes; each is accessible via its **accessor name** on the node instance.
- A **NodeSettings** field may `mirrors=` a **FrameworkSettings** or **LibrarySettings** field; the value resolves through the **SettingsRegistry** via **Three-tier resolution**.
- **FrameworkSettings** classes auto-register at registry init; **LibrarySettings** classes register via the **BaseRegistry** hot-reload path when their **Library** loads.
- A **GraphEntry** wraps exactly one **Graph**, one **Editor** and one **Interpreter** when it is executing; these are created/destroyed by `start_execution()` / `stop_execution()`.
- A **GraphEntry** structurally implements the **GraphContainer** protocol; source libraries register their containers into **GraphAppState** so **GraphEditor** can resolve `binding_id` → container on render.
- A **Haystack** references zero or more **GraphEntries** by relative file path; it also records which graph is active and which graphs should auto-execute on load.
- `workspace_state.json` stores the last-loaded **Haystack** name; on startup, **HaywireApp** auto-loads it if present.
- The **HaystackEditor** displays a **Haystack**'s entries and provides save/load **Haystack** actions and per-entry execution controls.
- A **Signal** travels on the **SignalBus**; one **SignalBus** per **Session**.
- A **signal_field** lives on a **SignalSource** subclass (**SessionContext**, **SessionState**, **AppState**); writes emit a **synthetic signal class** keyed by the field reference.
- **Hand-authored signals** (`Signal` / `CommandSignal` subclasses) and synthetic ones from **signal_field** travel the same bus and use the same `@redraw_on` / `@react_on` subscription.
- A **Signal** subclass with `cross_session: ClassVar[bool] = True` routes through `SessionManager.broadcast` and is received by every active **Session**.
- A library that subscribes to another library's **Signal** must list the **signal-defining library** in its own `LibraryIdentity.dependencies`.
- The **Global marketplace** holds only what the user opts into (`[[markets]]` and `[[stalls]]` subscriptions, optional inline `[[haybales]]`); the **Project marketplace** holds the project's own `[[heaps]]` plus the refresh `[[caches]]`. `haywire init` writes only the project marketplace. *(new)*
- **Refresh** reads the **Global marketplace**, fetches every **Subscription** (one-level-deep), and writes the resolved candidates to the **Project marketplace**'s `[[caches]]`. **Conflict resolution** applies `blocked`, then `ignores`, then heaps shadow, then first-come-first-served. *(new)*
- The Library Browser's **REQUIRED** filter and the Library Overview Editor's Disable/Uninstall gating both use `LibraryManager.get_installed_dependents()` — the `@library(dependencies=...)` graph. The two surfaces always agree. *(new)*
- A library's published manifest survives `haywire share` only if the **Three manifest layers** agree. The **Drift gate** detects divergence; **detect_deps** + the Detect Dependencies button reconcile it inside the Edit dialog. *(new)*

---

## Example dialogues

### Adding a node

> **Dev:** "I want to add a node that reads from a camera and fires a new frame event."
> **Domain expert:** "That's an **EVENT node** — it has an EXEC **outlet** but no EXEC **inlet**. It originates the **Flow**."
> **Dev:** "So the camera frames go out of a DATA **outlet** on the same node?"
> **Domain expert:** "Yes — the DATA **outlet** connects via an **Edge** to downstream **CONTROL nodes**. The **Pipe** on that **Edge** can be eager or lazy depending on whether you want immediate push or always-latest pull."
> **Dev:** "When I add this to a **Library**, how does it get discovered?"
> **Domain expert:** "Declare it in `register_components()` with `scan_nodes(...)`, and the **entry_point** in `pyproject.toml` makes the whole **Library** discoverable at startup."
> **Dev:** "And if the user is in the **Graph Canvas** and selects the node, what shows in the right **Slot**?"
> **Domain expert:** "The **Properties Editor** queries the **PanelRegistry** for all **Panels** whose `poll()` returns `True` for the `node` **Scope**. Each matching **Panel** renders inside a collapsible section. The **ContextBar** icon tells you which editor is active in the right **Slot**."

### Haystack

> **Dev:** "I want to save the set of graphs I'm working on so I can come back to it later."
> **Domain expert:** "Save a **Haystack** — it's a named TOML file in `haystacks/` that records which graphs are open. Use the save button in the **HaystackEditor** header."
> **Dev:** "What if one of my graphs is currently executing? Does the **Haystack** capture that?"
> **Domain expert:** "Yes — each graph entry in the **Haystack** has an `execute` flag. When you load the **Haystack** later, any graph marked `execute = true` will auto-start its **Interpreter**."
> **Dev:** "And unsaved graphs — do they go into the **Haystack**?"
> **Domain expert:** "No. A **Haystack** only stores paths to saved `.haywire` files. Unsaved **GraphEntries** (ones with no file path) are ephemeral — save the graph to disk first if you want it in a **Haystack**."
> **Dev:** "When I load a **Haystack**, what happens to the graphs I already have open?"
> **Domain expert:** "It's a full replace. If any current **GraphEntries** have unsaved changes, you'll get a confirmation dialog before they're discarded."

### Signals — subscribing and emitting

> **Dev:** "I want my editor to refresh when the user picks a different file. What should I subscribe to?"
> **Domain expert:** "`SessionContext.active_file` is a **signal_field**. Decorate your handler with `@redraw_on(SessionContext.active_file)` — the field reference IS the subscription key."
> **Dev:** "And if I want the handler to fire but NOT trigger a redraw — just a side-effect?"
> **Domain expert:** "Use `@react_on(SessionContext.active_file)` instead. Same subscription model; the framework just doesn't call `redraw()` after."
> **Dev:** "I also need to emit a coarse event when calibration finishes — carrying device ID, quality score, duration. That's not a single field changing."
> **Domain expert:** "That's a **hand-authored signal**. Declare `class CalibrationCompleted(Signal):` as a frozen dataclass with those payload fields, then `ctx.session.publish(CalibrationCompleted(...))` from the calibration worker. Subscribers wire it the same way: `@redraw_on(CalibrationCompleted)`."
> **Dev:** "If my library defines that **Signal** and another library subscribes, anything special?"
> **Domain expert:** "Yes — the subscriber must list your library in its `LibraryIdentity.dependencies`. Otherwise hot-reload of your library can leave the subscriber holding a stale class reference, and `isinstance` checks return `False`."

### Settings

> **Dev:** "I want my node to respect the library's default quality setting, but let users override it per-node."
> **Domain expert:** "Declare a **NodeSettings** inner class with a field that `mirrors=` the **LibrarySettings** field. The **accessor name** is whatever you call the inner class — `self.output`, say."
> **Dev:** "What if I just want to read a global flag silently, without showing it in the panel?"
> **Domain expert:** "Add `read_only=True` to the same `mirrors=` field. It becomes a silent cache — invisible in the panel, never stored, never writable per-instance. The value updates automatically when the **FrameworkSettings** source changes."
> **Dev:** "Where does the actual value come from when the node runs?"
> **Domain expert:** "**Three-tier resolution**: global TOML override wins, then workspace TOML override, then the node's local instance value, then workspace SET, then global SET, then the descriptor default. The **SettingsRegistry** owns that chain."
> **Dev:** "And the framework's own `ExecutionSettings` — does it need to be registered manually?"
> **Domain expert:** "No — **FrameworkSettings** subclasses self-register via `_pending_global` at registry init. **LibrarySettings** come in through the **BaseRegistry** hot-reload machinery when the **Library** loads."

### Subscribing to a marketplace *(new)*

> **Dev:** "I want my project to see haybales from a colleague's published feed. How?"
> **Domain expert:** "Click **Add Source** in the **Library Browser** and paste the URL on the Marketplace tab. That writes a `[[markets]]` entry to the **Global marketplace** — your `~/.haywire/db/haybale-marketplace/marketplace.toml`."
> **Dev:** "Will it fetch immediately?"
> **Domain expert:** "Yes — Add Source auto-fires **Refresh**. The fetch is one-level-deep: the runtime reads the remote's `[[stalls]]` URLs and inline `[[haybales]]`, but ignores its own `[[markets]]` to bound the resolution. Resolved candidates land in the **Project marketplace**'s `[[caches]]`."
> **Dev:** "What if two feeds advertise the same haybale name?"
> **Domain expert:** "You get a **Conflict resolution** prompt at Add Source time: pick which feed wins. The losing feed's `ignores` array gains that name so future refreshes silently skip it from that source."
> **Dev:** "And if a feed I'm subscribed to goes offline?"
> **Domain expert:** "Refresh falls back to the **HTTP cache** at `~/.haywire/cache/`. The Library Browser shows a yellow 'N sources unavailable' banner so you know what's not fresh. Cached entries that don't re-resolve get marked **Stale** with a red dot and a (stale) suffix; if they're uninstalled, a trash icon lets you drop them from the cache."

### Publishing a library cleanly *(new)*

> **Dev:** "I added a new import to my library. What do I need to update before `haywire share`?"
> **Domain expert:** "Two manifests: the `@library(dependencies=...)` decorator in your `__init__.py` (haywire DI runtime), and the `[project] dependencies` in the **library pyproject** (pip / consumer install). Source imports are the third layer — these are the **Three manifest layers** that have to agree."
> **Dev:** "I keep forgetting one of them. Anything that helps?"
> **Domain expert:** "Open the **Library Overview Editor** for your library, hit Edit, then the magnifying-glass **Detect Dependencies** button next to the dependencies field. It runs **detect_deps** and shows a **diff modal** with Union or Replace — Union is safe, never removes; Replace drops anything not detected."
> **Dev:** "And at publish time?"
> **Domain expert:** "`haywire share --strict` runs the **Drift gate**. If any of your barn libraries are missing manifest entries the source actually imports, it refuses to emit. `--fix` auto-corrects both manifests in place; default mode is warn-only on stderr."
> **Dev:** "What's the difference between `detect_deps` finding something for `library_decorator` versus `pyproject`?"
> **Domain expert:** "`library_decorator` is registered haywire libraries only — what the authoritative `HaywireLibrarySource` (the registry, or `EntryPointLibrarySource` in CLI flows) confirms is a haywire library. `pyproject` is wider: framework (`haywire-core`, `haywire-studio`), registered libraries, AND third-party (numpy, requests, etc.). Naming convention `haybale-*` is a hint, not a contract."

---

## Flagged ambiguities

- **"library"** has five distinct meanings (see top of this glossary). Always disambiguate.
- **"pin"** appears in the codebase and docs as both the colloquial name for the icon port and a general synonym for any port. Canonical terms are **Inlet** / **Outlet**; **Pin** is acceptable only for EXEC ports.
- **"connection"** is used loosely to mean both the act of connecting (verb) and the edge itself (noun). Prefer **Edge** for the object, and **link** for the action.
- **"context"** is overloaded: `ExecutionContext` (passed to worker), `SessionContext` (UI state), and `context=` string in older panel decorators (now replaced by **Scope**). Always qualify: ExecutionContext, SessionContext, or Scope.
- **"flow"** appears as both the general concept (data flow, control flow) and the specific assembled object (`LocalizedDataFlow`, `Flow`). Capitalize **Flow** when referring to the assembled execution unit.
- **"NodeBehavior" vs "NodeType"**: `NodeType` is the enum (`DATA`, `CONTROL`, `EVENT`, `OUTPUT`, `LOOPBACK`); `NodeBehavior` is the dataclass that holds `node_type: NodeType` plus other flags. The glossary term **NodeType** is canonical for the execution role. "Node type" (lowercase) is used consistently in docs and code for this concept only.
- **"sidebar"** is overloaded: the CSS token prefix `--hw-sidebar-*` refers specifically to the **ActivityBar** and **ContextBar** (the narrow 48px icon strips). It does NOT refer to the Left or Right **Slots** (the wider editor panels). Always qualify: use **ActivityBar**, **ContextBar**, or **Slot** for structural names; "sidebar" only appears as a CSS token prefix.
- **"info bar"** appears in two distinct senses: `hui.info_bar()` is a Panel-level metadata bar pattern; **StatusBar** is a shell-level bar at the bottom of the AppShell. They are different things — never use "info bar" to mean the StatusBar.
- **"panel"** in CSS token names (`--hw-panel-*`) refers to the `.hw-panel` editor container, not the **Panel** sub-component concept. The CSS token `--hw-panel-bg` is the background of the editor container, not a per-Panel background.
- **"area" vs "slot"**: **Slot** is the canonical term for workspace positions. **Area** and **canvas_area** are deprecated. The term "area" now refers only to the content region within a slot (the part next to the bar). Each slot = bar + area; use **Slot** for the whole position, "area" (lowercase, informal) only for the content pane if disambiguation is needed.
- **"middle" vs "main"**: The slot formerly called "middle" is now **Main**. Use `default_slot='main'` in code. "Middle" is deprecated and will cause deserialization failures in `workspace_state.json`.
- **"hw-tabs" vs "hw-slot-bar-tabs"**: The CSS class `hw-tabs` is deprecated. Use `hw-slot-bar` (base) + `hw-slot-bar-tabs` (horizontal tab bars) or `hw-slot-bar-icons` (vertical icon bars).
- **"session" vs "haystack"**: "Session" in Haywire means a per-browser-connection state object (**Session**, **SessionContext**). A named selection of graphs to work on is a **Haystack**, not a "session" — despite IDE conventions. Do not use "session" to mean a saved graph selection.
- **"interpreter"**: Each **GraphEntry** owns its own **Interpreter** instance. References to "the interpreter" should be qualified: "the graph's Interpreter" or "entry.interpreter". The app-level `self.interpreter` is removed.
- **"signal" vs "Signal"**: lowercase "signal" is the generic concept (a thing on the bus). Uppercase **Signal** is the base class. `Session.publish` previously had a `Session.signal = publish` alias — that alias was deleted; use `publish` only. `session.signal(...)` is no longer valid.
- **"event" vs "signal"**: **Signal** is the canonical term for anything on the session bus. The old `Event`/`ContextSignal`/`LifecycleCommand` vocabulary was deleted in the signal-field unification. **Event** survives only in unrelated contexts: `NodeType.EVENT` (execution-engine role), `EVENT node` (a node category), `LifeCycleEvent` (registry batch events), `ContextChangedEvent` (slot context-change signal, distinct from session-bus signals). Never use "event" to mean a session-bus signal.
- **"reactive field" vs "signal field"**: historical name for the same concept. The pre-unification `Reactive[T]` wrapper with `.value` accessor was deleted; **signal_field** is the canonical term. "Reactive field" appears only in historical design docs under `internals/speculatives/`.
- **"Signal class" overloaded**: a **synthetic signal class** is generated by `signal_field` at class-definition; a **hand-authored signal** is a `Signal` subclass declared explicitly. Both inherit `Signal` directly and dispatch identically. Disambiguate when discussing implementation details.
- **"marketplace" overloaded** *(new)*: refers to three distinct things — the runtime concept (the **Marketplace** catalog visible in the Library Manager's AVAILABLE section), the file (**Global marketplace** `~/.haywire/db/haybale-marketplace/marketplace.toml` or **Project marketplace** `<project>/.haywire/marketplace.toml`), and the TOML section type (**`[[markets]]`** subscriptions to remote marketplace feeds). Always qualify which sense — file vs section vs catalog.
- **"marketplace" vs "marketstall"** *(new)*: a **Marketstall** is a single-author publish file listing `[[haybales]]` (produced by `haywire share`). A **Marketplace** in the file-shape sense (`marketplace.toml`) aggregates `[[markets]]` subscriptions, `[[stalls]]` subscriptions, optional inline `[[haybales]]`, and (project-only) `[[heaps]]` + `[[caches]]`. A `[[markets]]` URL points at another `marketplace.toml`; a `[[stalls]]` URL points at a `marketstall.toml`. Different schemas, different recursion rules.
- **"heaps" location** *(new)*: `haywire init` writes `[[heaps]]` to the **Project marketplace**, NOT the Global marketplace. The Global marketplace has no `[[heaps]]` section in the new schema (the legacy `[[locals]]` cross-project case is unsupported; users with that need declare each project's heaps in its own project marketplace).
- **"dependencies" — three meanings** *(new)*: (1) project pyproject `dependencies` (what uv resolves in dev), (2) library pyproject `dependencies` (what pip ships with the published package), (3) `@library(dependencies=[...])` (the haywire runtime DI graph). The **Three manifest layers** must agree at publish time; **detect_deps** and the **Drift gate** keep them honest. Never use bare "dependencies" without qualifying which manifest you mean.
- **"required" vs "dependent"** *(new)*: a library is **required** if some installed haywire library lists it in `@library(dependencies=[...])`. The reverse-direction term is **dependent** — the library that *has* that declaration. Computed via `LibraryManager.get_installed_dependents(lib_id)`. Note: this is the **`@library`** graph, NOT pip's `Requires-Dist`. The pip-walk path (`is_required_by_another_package`) was removed in commit `f09c8558`.
- **"refresh" vs "scan"** *(new)*: **Refresh** is the orchestration pipeline that fetches subscriptions, applies conflict resolution, and writes the project `[[caches]]`. "Scan" usually means file-watcher reload or library-registry rescan — different subsystem. Use **Refresh** for the marketplace pipeline.
- **"stale"** *(new)*: in the marketplace runtime, **stale** means a project-marketplace `[[caches]]` entry that a subsequent **Refresh** did not re-resolve from any source. It does NOT mean "out of date" in the version sense. Stale + installed entries are locked from removal; stale + uninstalled entries are trash-icon removable.
- **"dialog" vs "modal" vs "popup"** *(new)*: in the haywire codebase, **Popup** is the Vue component all canonical modals are built on. The helpers in `haywire.ui.modals` (info_modal, confirm_modal, pick_modal, rename_modal, save_as_modal, diff_modal) wrap Popup with task-specific bodies. "Dialog" is the legacy NiceGUI/Quasar surface (`ui.dialog()`) — being migrated to Popup; legacy dialogs sit at Quasar's default z-index 6000, Popup at 7000/7001 so haywire modals always stack on top.
