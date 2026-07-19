# Wrappable Operations Inventory (for Farmhand MCP server design)

Survey of operations the Haywire codebase ALREADY exposes that MCP tools could wrap, plus gaps.
Code is ground truth; docs cited where they add context. Flags per operation:

- **sync/async** — Python call convention.
- **loop affinity** — `loop-free` (callable from any thread, no NiceGUI loop needed), `main-loop` (must/should run on the NiceGUI event loop), or `loop-adjacent` (works off-loop but schedules follow-up work onto the loop).
- **signals** — whether the call broadcasts cross-session signals (`GraphDataMutated`, `HaystackTeardown`, `HaystackReloaded`, `LibraryCatalogChanged`) so open browser UIs update.

> **TL;DR**
>
> - **Marketplace**: `LibraryManager` (install/uninstall/dry-run are `async` + stream via `on_output` callback; the rest sync/loop-free) and `MarketplaceState` (catalog = TOML files on disk; `refresh()` is synchronous blocking network I/O) cover install/list/query almost completely. Per-library component listing is a registry-key prefix scan (`{lib_id}:{type}:{name}`), already used by the Library Overview editor. Docs (OVERVIEW.md etc.) are plain files under `lib.identity.folder_path`.
> - **Haystack**: `HaystackState` is a complete open/save/rename/remove/start/stop surface, every mutator broadcasts `GraphDataMutated` itself. Haystack TOMLs live in `<workspace>/haystacks/*.toml` with a pure-I/O `persistence` module (`list_haystacks`, `dump`, `load`, `delete`, `rename`). There is **no** API to list `.haywire` files on disk — the file browser walks directories generically in UI code.
> - **Graph mutation**: `Editor` (core) is the undoable mutation surface — create/paste/move/remove nodes, create/split/dissolve edges, undo/redo — all **sync**, addressed by string ids. **It has no set-property / set-port-value operation and no transaction API beyond `add_fence()`**. Reading a graph = `BaseGraph.to_dict()`. Validation is debounced through an injected scheduler (ADR 0002): graphs made by `HaystackState` use `LoopScheduler` (NiceGUI loop); headless graphs can use `SyncScheduler`. Editor calls do NOT broadcast signals — the debounced validation pass (via `HaystackState._on_entry_validation`) does.
> - **Node authoring**: the only scaffolding is `haywire init` (CLI subcommands are exactly `init` / `share` / `rename`), which creates a project-local barn library with **nine empty component folders and no example node** — there is NO per-node scaffold command or template API. Hot-reload: a brand-new `.py` file dropped into a `file_watcher=True` library folder IS picked up live (watchdog `on_created` → 0.5s debounce → module import + class scan → `CLASS_ADDED` lifecycle events to subscribers), but the whole pipeline runs on **watchdog/timer threads**, not the NiceGUI loop.
> - **Biggest gaps**: no list-`.haywire`-files API; no node-file scaffolding API; no set-node-property/port-value primitive on `Editor` (settings-bag writes and `port.set_value` bypass undo and are not id-addressable); no read-only structural query API besides full `to_dict()`; no headless "app context" entry point (all major surfaces hang off `AppState`s created by the DI/library container inside a running app — an out-of-process MCP server has nothing to connect to); core `Editor` mutations don't broadcast `GraphDataMutated` (caller's job); `MarketplaceState.refresh()` blocks on network.

---

## 1. haybale-marketplace + core marketstall

### 1.1 `LibraryManager` — full public surface

Class: `barn/haybale-marketplace/haybale_marketplace/library_manager.py:160`.
Constructed by `LibraryManagerState.on_enable()` (`barn/haybale-marketplace/haybale_marketplace/state/library_manager_state.py:35`) and published app-wide as an `AppState` attribute; constructor is `__init__(self, library_registry: LibraryRegistry, venv_path: str | None = None, project_dir: str | None = None)` (`library_manager.py:167`).

| Operation | Signature | sync/async | loop affinity | signals | Citation |
|---|---|---|---|---|---|
| Dry-run resolve | `async dry_run(install_spec: str) -> list[str]` — returns pip dist names that would be removed/upgraded; raises `RuntimeError` on resolver failure | async (spawns `uv` subprocess, streams via internal callback) | loop-free (uses `asyncio` subprocess/thread offload; needs a running event loop, not the NiceGUI one specifically) | none | `library_manager.py:273` |
| Install | `async install(install_spec: str, on_output: Callable[[str], None], source_pkg: Haybale \| None = None) -> tuple[bool, str, PostInstallHints]` — pre-evicts to-be-upgraded libraries from the registry, runs `uv pip install`, invalidates import caches, `registry.scan_for_libraries()` in `asyncio.to_thread`, `enable_all_libraries()`, syncs pyproject.toml | async, **streams** every output line through `on_output` | loop-free for the uv part; registry re-scan imports library modules (side-effectful) | none directly (UI layer broadcasts `LibraryCatalogChanged` itself; see 1.4) | `library_manager.py:307-383` |
| Install (alias) | `async install_streaming(...)` — deprecated alias for `install()` | async, streams | as above | none | `library_manager.py:385-392` |
| Uninstall | `async uninstall_streaming(library_id: str, on_output: Callable[[str], None]) -> tuple[bool, str, PostInstallHints]` — `registry.disable_library`, `uv pip uninstall`, cache invalidation, re-scan, pyproject sync | async, **streams** via `on_output` | loop-free (same caveats as install) | none directly | `library_manager.py:394-431` |
| List installed | `list_installed() -> list[LibraryInfo]` | sync | loop-free | none | `library_manager.py:483` |
| Get one installed | `get_installed_library(library_id: str) -> LibraryInfo` (identity, enabled, `InstallType`, distribution name) | sync | loop-free | none | `library_manager.py:490` |
| Is installed | `is_installed(library_id: str) -> bool` | sync | loop-free | none | `library_manager.py:504` |
| Installed version | `get_installed_version(package_name: str) -> str \| None` (importlib.metadata) | sync | loop-free | none | `library_manager.py:508` |
| Dependents | `get_installed_dependents(lib_id: str) -> list[LibraryInfo]` — installed libs whose `@library(dependencies=[...])` include `lib_id` | sync | loop-free | none | `library_manager.py:533` |
| Missing deps | `get_missing_dependencies(lib_id: str, require_enabled: bool) -> list[str]` | sync | loop-free | none | `library_manager.py:566` |
| Fetch versions | `async fetch_versions(pkg: Haybale) -> list[str]` — **network**: PyPI JSON API or GitHub tags API, wrapped in `asyncio.to_thread`, 10s timeout, empty list on failure | async | loop-free | none | `library_manager.py:585-644` |

`InstallType` enum (`REGULAR`/`EDITABLE`/`FOLDER`): `packages/haywire-core/src/haywire/core/library/install_type.py:8`.
`PostInstallHints` carries `needs_refresh`/`needs_restart` derived from `LibraryIdentity` flags (`library_manager.py:258`, identity flags at `packages/haywire-core/src/haywire/core/library/identity.py:26-27`).

### 1.2 `MarketplaceState` — the AVAILABLE (not-installed) catalog

Class: `barn/haybale-marketplace/haybale_marketplace/state/marketplace_state.py:24` (an `AppState`; `on_enable` at `:48` resolves the workspace root and auto-refreshes once if subscriptions exist but the project cache is empty, `:61-84`).

Catalog model (all plain TOML files, parsed fresh on every read — no in-memory catalog object):

- Global subscriptions file: `~/.haywire/db/haybale_marketplace/marketplace.toml` (`_global_path`, `marketplace_state.py:90-94`), sections `[[markets]]`, `[[stalls]]`, `[[haybales]]` → `MarketplaceFile` (`packages/haywire-core/src/haywire/core/marketstall/types.py:83`).
- Project cache file: `<workspace>/.haywire/marketplace.toml` (`_project_path`, `marketplace_state.py:96-99`), sections `[[heaps]]` (local path libraries, written by `haywire init`) and `[[caches]]` (refresh result) → `ProjectMarketplaceFile` (`types.py:100`).
- One catalog row = `Haybale` dataclass (`types.py:15-64`): name, min_version, label, description, author, source (`pypi`/`git`), install_spec, tags, os, dependencies, source_url, docs_url, plus cache-only `via`/`last_seen`/`stale`.

| Operation | Signature | sync/async | loop affinity | signals | Citation |
|---|---|---|---|---|---|
| Read global subscriptions | `get_global() -> MarketplaceFile \| None` (None + `global_marketplace_error` set on malformed TOML) | sync | loop-free | none | `marketplace_state.py:105-118` |
| Read available catalog | `get_project_haybales() -> list[Haybale]` — parses project `[[caches]]` | sync | loop-free | none | `marketplace_state.py:120-126` |
| Refresh catalog | `refresh() -> RefreshReport` — **synchronous blocking network** (see pipeline below); caches result on `self.last_report` | sync (blocking urllib fetches!) | loop-free but **blocks the calling thread** — UI callers run it as-is today (potential loop stall); an MCP wrapper should offload to a thread | none | `marketplace_state.py:132-144` |
| Drop stale entry | `remove_stale_haybale(name: str) -> bool` | sync | loop-free | none | `marketplace_state.py:146-151` |
| Fetch remote docs | `async fetch_overview(pkg: Haybale) -> str \| None` — OVERVIEW.md/QUICKREF.md via explicit `docs_url`, GitHub-raw heuristic, or PyPI long_description; network in `asyncio.to_thread` | async | loop-free | none | `marketplace_state.py:157-256` |

**What `refresh()` actually does** — `refresh(*, global_path, project_path, cache_dir=None) -> RefreshReport` (`packages/haywire-core/src/haywire/core/marketstall/refresh.py:200-313`):
parse global + previous project file → HTTP-fetch each `[[markets]]` URL (one level deep: collects referenced stall URLs + inline haybales) → fetch each `[[stalls]]` URL (direct + discovered) → apply per-subscription `blocked`/`ignores` filters → heaps shadow + first-come-first-served dedup → stale-mark against previous `[[caches]]` → **write the project marketplace.toml** → GC orphan HTTP-cache files. Yes, it is network: `fetch_with_cache_fallback` (`packages/haywire-core/src/haywire/core/marketstall/cache.py:63-84`) does `urllib.request.urlopen` (5s timeout) with fallback to `~/.haywire/cache/<url-hash>.toml`; tri-state outcome per source (`RefreshOutcome`, `types.py:114`). `RefreshReport` fields: sources fetched/from-cache/unavailable (+urls), haybales_resolved, new_stale, updates_available (`types.py:132-148`).

Parsing entry points (pure, loop-free, sync): `parse_global_marketplace(path) -> MarketplaceFile` (`packages/haywire-core/src/haywire/core/marketstall/parsing.py:85`), `parse_project_marketplace(path)` (`parsing.py:106`), `parse_marketstall_body(body)` (`parsing.py:139`), `parse_remote_marketplace_body(body)` (`parsing.py:156`).

### 1.3 Library docs & per-component metadata

- `LibraryIdentity` (`packages/haywire-core/src/haywire/core/library/identity.py:5`) carries: `label, version, description, url, help_url, author, author_url, folder_path, module_name, id, dependencies (Python package names — see .insights/project_library_dependencies_use_package_names.md), tags, file_watcher, needs_refresh, needs_restart`.
- **Docs at runtime are plain files inside `lib.identity.folder_path`**: the Library Overview editor renders `Path(lib.identity.folder_path) / "OVERVIEW.md"` directly (`barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:670-678`). For marketplace-only (not-installed) packages it falls back to the network fetch `MarketplaceState.fetch_overview` (`library_overview_editor.py:626`, `marketplace_state.py:157`). README.md / QUICKREF.md / NOTES.md are the same pattern — files in the library folder (generated by the `haybale-gen-docs` skill); no dedicated docs API exists beyond this. Reading them for MCP = `Path(identity.folder_path) / <name>.md`. (NOTES.md: UNVERIFIED that any runtime code reads it — only OVERVIEW.md and QUICKREF.md appear in reader code paths.)
- **Per-library component enumeration** — there is no "components of library X" API; the convention is **registry-key prefix scanning**. Registry keys are `"{lib_id}:{type_segment}:{name}"` (segments: `node`, `widget`, `type`, `adapter`, `skin`, `setting`, `theme`, `panel`, `editor`, `state`). The Library Overview editor counts and lists per-type components with `sum(1 for k in registry.list_names() if k.startswith(f"{lib_id}:{seg}:"))` (`library_overview_editor.py:332-335`, `:576-585`) and `_registry_items(registry, prefix) -> [(key, cls)]` (`library_overview_editor.py:651-655`). The ten registries come from DI (`svc.get_node_registry()` … `svc.get_state_registry()`, `library_overview_editor.py:281-290`). All sync, loop-free reads; no signals.
- Node-level metadata beyond the class: `NodeFactory.get_node_info(registry_key) -> NodeInfo` (identity + library identity) — see §3.4.

### 1.4 Who broadcasts library-change signals

`LibraryManager` itself broadcasts nothing. The cross-session signal is `LibraryCatalogChanged` (`packages/haywire-core/src/haywire/core/session/signals/vocabulary.py:81-95`, `cross_session=True`), emitted by UI flows after install/uninstall/enable/disable. An MCP wrapper performing installs must broadcast it itself (via `SessionManager.broadcast` or an `AppState._signal_emit`) or open UIs won't refresh their library views.

---

## 2. haybale-haystack

### 2.1 `HaystackState` — full public surface

Class: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py:26` (an `AppState`; one per app, shared across sessions). `on_enable` (`:55`) resolves workspace root, node factory, `GraphAppState`, `HaystackSettings`, then rehydrates the last haystack; `on_disable` (`:99-131`) broadcasts `HaystackTeardown(entry_ids=...)`, stops execution on every entry, unregisters from `GraphAppState`, clears entries.

All mutators funnel their UI notification through `_broadcast_data_mutated()` (`:137-155`), which calls `SessionManager.broadcast(GraphDataMutated())` — so **every row below marked "GDM" updates all open browser sessions automatically**.

| Operation | Signature | sync/async | loop affinity | signals | Citation |
|---|---|---|---|---|---|
| New untitled graph | `create_new() -> GraphEntry` — binding_id `"__unsaved_N__"` from `HaystackSettings.new_counter`; registers in `GraphAppState` | sync | loop-adjacent: constructs `BaseGraph` with `LoopScheduler` (needs the NiceGUI loop importable; inline fallback pre-loop) | GDM | `haystack_state.py:210-234` |
| Open file | `open_graph(path: Path) -> GraphEntry` — idempotent per path; `load_from_file` + `force_validation` before subscribing the validation handler | sync (file I/O + full graph build) | loop-adjacent (same as above); safe off-loop at startup | GDM | `haystack_state.py:236-261` |
| Save | `save_graph(entry: GraphEntry, save_as: Path \| None = None) -> bool` (protocol-shaped wrapper over `_save_entry`) | sync | loop-free (JSON write via `graph.save_to_file`) | GDM (via `_save_entry`) | `haystack_state.py:263-270`, `_save_entry :272` |
| Rename | `rename_graph(entry: GraphEntry, new_name: str) -> bool` — renames the file on disk and rekeys | sync | loop-free | GDM | `haystack_state.py:312` |
| Close/remove entry | `remove_entry(entry: GraphEntry) -> bool` — stops execution, unregisters, `graph.cleanup()`; **does NOT delete the file** | sync | loop-free | GDM | `haystack_state.py:338-356` |
| Start execution | `start_execution(entry: GraphEntry) -> CompileResult` | sync (spawns interpreter scheduler threads) | loop-free | none directly (marks haystack dirty) | `haystack_state.py:363-366` |
| Stop execution | `stop_execution(entry: GraphEntry) -> None` | sync (bounded 2s grace, joins threads) | loop-free | none directly | `haystack_state.py:368-370` |
| Lookup by id | `get_by_id(binding_id: str) -> GraphEntry \| None` | sync | loop-free | none | `haystack_state.py:376` |
| Lookup by path | `get_by_path(path: Path) -> GraphEntry \| None` | sync | loop-free | none | `haystack_state.py:379` |
| Lookup by graph | `get_by_graph(graph: object) -> GraphEntry \| None` | sync | loop-free | none | `haystack_state.py:382` |
| List open entries | `all_entries() -> list[GraphEntry]` | sync | loop-free | none | `haystack_state.py:388` |
| Dirty queries | `has_unsaved() -> bool`, `unsaved_entries() -> list[GraphEntry]` | sync | loop-free | none | `haystack_state.py:396`, `:400` |
| Save haystack | `save_haystack(name: str, active_path: Path \| None = None) -> Path` — writes TOML, persists `last_haystack_name`, clears dirty | sync | loop-free | GDM | `haystack_state.py:408-430` |
| Load haystack | `load_haystack(name: str) -> Path \| None` — opens all listed graphs (merge semantics: does NOT clear existing entries), autostarts `execute=true` ones; returns stored active-graph path | sync | loop-adjacent (opens graphs → LoopScheduler) | GDM per opened graph | `haystack_state.py:432-457` |

Validation coupling: `_subscribe_validation` (`:520`) wires each entry's graph to `_on_entry_validation(entry, result)` (`:161-183`), which stops (and optionally autorestarts, per `entry.run_settings.autorestart`) execution when `ChangeReason.requires_graph_reassembly()`, sets `entry.unsaved = True`, and broadcasts GDM. Because graphs use `LoopScheduler`, this handler runs **on the NiceGUI main loop** in the live app (ADR 0002, `docs/adr/0002-validation-scheduler-injection.md`; injection site `haystack_state.py:189-204`).

### 2.2 `GraphEntry`

Dataclass: `barn/haybale-haystack/haybale_haystack/graph_entry.py:30` — fields `graph, editor, path, unsaved, interpreter, _unsaved_id, haystack, run_settings: GraphRunSettings` (`:48-55`).

| Operation | Signature | sync/async | loop affinity | signals | Citation |
|---|---|---|---|---|---|
| Identity | `binding_id -> str` (str(path) or `__unsaved_N__`), `display_name -> str`, `is_executing -> bool` | sync props | loop-free | none | `graph_entry.py:57-85` |
| Compile only | `compile() -> CompileResult` — builds `Interpreter`, `interpreter.load_graph(graph)`, does not start | sync | loop-free (pure assembly) | none | `graph_entry.py:87-102` |
| Start (compiled) | `start() -> None` — dispatches BEGIN_PLAY | sync | loop-free | none | `graph_entry.py:104-109` |
| Compile+start | `start_execution() -> CompileResult` | sync | loop-free | none | `graph_entry.py:111-118` |
| Stop | `stop_execution() -> None` — dispatches SHUTDOWN, scoped grace on Shutdown flows, force teardown (`Interpreter.stop_execution`, `packages/haywire-core/src/haywire/core/execution/interpreter.py:155-198`) | sync (may block up to grace timeout) | loop-free | none | `graph_entry.py:120-131` |
| Save (protocol) | `save(save_as: Path \| None = None) -> str \| None` — delegates to `HaystackState._save_entry`; returns new binding_id on rename else None | sync | loop-free | GDM (via haystack) | `graph_entry.py:133-150` |

### 2.3 Haystack TOML persistence (`persistence.py`)

Pure I/O helpers, all **sync, loop-free, no signals** (`barn/haybale-haystack/haybale_haystack/persistence.py`). Files live in `<workspace_root>/haystacks/<name>.toml` (`haystack_dir :44`, `haystack_path :49`). Format: `[haystack]` (name, optional `active_graph` rel path) + `[[graphs]]` (path rel to workspace, `execute` bool, optional `[graphs.run]` run-settings table) — docstring at `persistence.py:12-15`.

| Operation | Signature | Citation |
|---|---|---|
| List haystacks | `list_haystacks(workspace_root: Path) -> list[str]` — sorted stems of `haystacks/*.toml` | `persistence.py:59-72` |
| Dump | `dump_haystack(state, workspace_root, name, active_path=None) -> Path` — only file-backed entries written | `persistence.py:75-144` |
| Load | `load_haystack(state, workspace_root, name) -> Path \| None` — calls `state.open_graph` per entry, autostarts `execute=true`; does NOT clear existing entries | `persistence.py:147-206` |
| Delete | `delete_haystack(workspace_root, name) -> bool` | `persistence.py:209` |
| Rename | `rename_haystack(workspace_root, old_name, new_name) -> bool` | `persistence.py:227` |

### 2.4 Listing "existing graphs": open entries vs. files on disk

- **Open entries** = `HaystackState.all_entries()` (§2.1).
- **Files on disk**: there is **no programmatic ".haywire file listing" API anywhere**. The workspace file browser is a generic lazy tree UI, `LazyFileBrowserEditor` (`barn/haybale-studio/haybale_studio/editors/file_browser.py:58`), which walks from `app.workspace_root` with `path.iterdir()` (`file_browser.py:208-241`) — it doesn't filter for graphs. The only ".haywire" awareness is the context-menu panel `OpenInHaystackMenuPanel` with `_GRAPH_EXTS = frozenset({".haywire"})` (`barn/haybale-haystack/haybale_haystack/panels/file_browser/menu/file.py:32-51`), which calls `HaystackState.open_graph` on click. An MCP "list graphs" tool has nothing to wrap — see Gaps.

### 2.5 Haystack cross-session signals

`barn/haybale-haystack/haybale_haystack/signals.py`: `HaystackTeardown(entry_ids=...)` (`:22`, emitted from `on_disable` before clearing — receivers close tabs) and `HaystackReloaded` (`:37`, emitted from `on_enable` after rehydration — receivers re-render lists). Both `cross_session=True`.

---

## 3. haybale-graph-editor + core graph mutation

### 3.1 `GraphAppState` and the `GraphContainer` protocol

`GraphAppState` (`barn/haybale-graph-editor/haybale_graph_editor/state/graph_app_state.py:29`) is the app-wide identity router `binding_id -> GraphContainer`; holds references only. All methods sync, loop-free, no signals:
`register(container)` (`:40`), `unregister(binding_id)` (`:44`), `get(binding_id)` (`:48`), `get_by_graph(graph)` (`:52`), `rekey(old_id, new_id)` (`:65`), `all_containers()` (`:82`).

`GraphContainer` protocol (`barn/haybale-graph-editor/haybale_graph_editor/protocols.py:17`): properties `binding_id: str`, `editor: Editor`, `path: Path | None`, `unsaved: bool`, `display_name: str`; method `save(save_as: Path | None = None) -> str | None` (`:46-59`). `GraphEntry` satisfies it structurally (with a documented read-only-property mismatch noted at `haystack_state.py:227-230`).

**For an MCP server**: `GraphAppState.get(binding_id).editor` is the sanctioned route from "a graph id" to the mutation API, source-agnostic (haystack or any future source).

### 3.2 `Editor` — FULL public method surface (core mutation API)

Class: `packages/haywire-core/src/haywire/core/graph/editor.py:24`; `__init__(self, graph: BaseGraph, node_factory: NodeFactory, undo_config: UndoConfig | None = None)` (`:33`). Every mutator wraps an undo `Action` and executes it via `history_manager.add_action(...)` — mutations are **immediately applied and undoable**. All methods **sync**. None broadcast signals directly; structural changes mark the graph dirty and the debounced validation pass notifies subscribers (see 3.5/3.6 for affinity).

| Operation | Signature | Preconditions / notes | Citation |
|---|---|---|---|
| Create node | `create_wrapper(registry_key: str, position: tuple[float, float] = (3750, 3750)) -> NodeWrapper \| None` | registry_key like `"haybale_core:node:add"`; unknown keys instantiate the registered error node (never None for that reason) | `editor.py:55-79` |
| Paste | `paste_clipboard(payload: dict, paste_x: float, paste_y: float) -> tuple[list[str], list[str]] \| None` — returns (new node ids, new edge ids); unknown node types paste as placeholder error nodes | payload = clipboard dict shape (`core/graph/clipboard.py`) | `editor.py:81-103` |
| Move (delta) | `move_nodes(nodes: list[str], deltaX: float, deltaY: float) -> bool` | node ids must exist | `editor.py:105-130` |
| Move (absolute) | `move_nodes_to(positions: dict[str, dict[str, float]]) -> bool` | | `editor.py:132-143` |
| Remove | `remove_elements(nodes: list[str], edges: list[str]) -> bool` — validates ALL ids exist first, else returns False without mutating | node/edge ids | `editor.py:145-182` |
| Get node | `get_node_wrapper(node_id: str) -> NodeWrapper \| None` | | `editor.py:184-186` |
| List nodes | `list_node_wrappers() -> list[NodeWrapper]` | | `editor.py:188-190` |
| List node types | `get_available_node_regkeys() -> list[str]` | delegates to `node_factory.node_registry.list_names()` | `editor.py:192-194` |
| Connect | `create_edge(source_node_id: str, outlet_pin: str, sink_node_id: str, inlet_pin: str) -> bool` | pins are port-id strings on the node | `editor.py:200-229` |
| Split w/ reroute | `split_edge_with_reroute(edge_id: str, position: tuple, registry_key: str) -> str \| None` | caller supplies reroute node's registry key | `editor.py:231-261` |
| Dissolve reroute | `dissolve_reroute(node_id: str) -> bool` | | `editor.py:263-279` |
| List edges | `list_edges() -> list[EdgeWrapper]` | | `editor.py:281-283` |
| Undo / redo | `undo() -> bool`, `redo() -> bool`, `can_undo() -> bool`, `can_redo() -> bool` | | `editor.py:289-323` |
| Undo grouping | `add_fence() -> None` — groups subsequent operations | the ONLY "transaction" primitive; there is no begin/commit/rollback API | `editor.py:325-327` |
| Validity | `is_valid() -> bool` | | `editor.py:329-331` |

Disconnect = `remove_elements([], [edge_id])` — there is no dedicated `disconnect` method. Undo action classes live in `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` (AddNodeAction `:27`, AddEdgeAction `:99`, MoveNodesAction `:173`, MoveNodesToAction `:258`, RemoveElementsAction `:293`, DuplicateNodeAction `:426`, PasteClipboardAction `:471`, SplitEdgeWithRerouteAction `:628`, DissolveRerouteAction `:718`).

**No set-property operation exists on `Editor`.** Node settings are mutated by writing the node's settings-bag descriptors directly (`self.filter.threshold = 0.8` pattern, `packages/haywire-core/src/haywire/core/node/data.py:121-135`); port values by `NodeData.out(...)`/`DataPort.set_value` (`data.py:500-532`) or widget events. Neither path is undoable or routed through `Editor` — see Gaps.

**UI-side wrapper**: `GraphEditor` (the editor UI) publishes `GraphDataMutated` after undo/redo itself (`barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py:302-310`) — i.e., signal emission after core `Editor` calls is the CALLER's responsibility.

### 3.3 Addressing model

- **Node ids**: strings minted by `BaseGraph.generate_unique_node_id(prefix)` → `f"{prefix}_{uuid4().hex[:8]}"` (`packages/haywire-core/src/haywire/core/graph/base.py:259-271`); prefix derives from the registry key. Stable across save/load (serialized as dict keys, `base.py:912-915`).
- **Registry keys** (node types): `"{lib_id}:node:{name}"` (see §1.3).
- **Edge ids**: uuid strings keying `graph.edge_wrappers` (`base.py:112`, serialization `base.py:916`).
- **Ports/pins**: string port ids unique within a node (`NodeData.ports: Dict[str, DataPort]`, `packages/haywire-core/src/haywire/core/node/data.py:63`); edges reference `(node_id, port_id)` pairs (`base.py:993-996`).

### 3.4 `NodeFactory` — node-type lookup & discovery

Class: `packages/haywire-core/src/haywire/core/node/factory.py:21`; `__init__(node_registry: NodeRegistry)`. All sync, loop-free, no signals.

| Operation | Signature | Citation |
|---|---|---|
| Resolve class | `get_node(registry_key: str) -> tuple[type[BaseNode], HaywireException \| None]` — falls back to registered error node; raises only if no error node registered | `factory.py:61-114` |
| Menu structure | `get_menu_structure() -> dict[str, list[NodeInfo]]` (visible nodes grouped by `identity.menu` path) | `factory.py:217-242` |
| Search | `search_nodes(query: str) -> list[NodeInfo]` (label/description/search_tags substring) | `factory.py:244-273` |
| List all keys | `list_all_nodes() -> list[str]` | `factory.py:275-282` |
| Node metadata | `get_node_info(registry_key: str) -> NodeInfo \| None` (node identity + library identity) | `factory.py:284-295` |
| Alternates | `get_alternate_node_registry_keys(registry_key) -> list[str]` | `factory.py:49-59` |
| Hot-reload hooks | `add_batch_listener(cb)`, `add_event_subscriber(registry_key, cb)` (+removers) | `factory.py:149-192` |

Node *instantiation* from a key is graph-owned, not factory-owned: `BaseGraph.create_node_wrapper(registry_key, position=(3750,3750), node_data=None, node_id=None) -> NodeWrapper | None` builds a `NodeWrapper`, calls `wrapper.build(node_data or {})`, adds it and marks validation dirty (`base.py:273-308`). `Editor.create_wrapper` goes through `AddNodeAction` → this path.

### 3.5 Reading a graph as structured data / serialization

| Operation | Signature | sync/async | loop affinity | signals | Citation |
|---|---|---|---|---|---|
| Serialize | `BaseGraph.to_dict(include_data: bool = True) -> dict` — keys: graph_id, name, description, version, author, created_at, modified_at, `nodes` (node_id → wrapper.serialize), `edges`, `variables`, `props` | sync | loop-free | none | `base.py:894-919` |
| Deserialize | `load_from_dict(data) -> bool` — clears + rebuilds in place; applies ADR-0005 compatibility warnings | sync | loop-free (but triggers validation marks) | none | `base.py:921-1023` |
| Save file | `save_to_file(filepath: str, include_data: bool = True) -> bool` — JSON, atomic tmp-write + `os.replace` | sync | loop-free | none | `base.py:1107-1154` |
| Load file | `load_from_file(filepath: str) -> bool` | sync | loop-free | none | `base.py:1156-1189` |

A read-only structural query would use `to_dict(include_data=False)` (structure without field values) or walk `graph.node_wrappers` / `graph.edge_wrappers` directly — there is no dedicated query API (see Gaps). A `.haywire` file is this JSON on disk, so pure-read MCP tools can also parse the file without instantiating a graph.

### 3.6 `BaseGraph` validation (ADR 0002) and `ValidationResult`

- Constructor: `BaseGraph(graph_id, name, validation_delay_ms=50.0, validation_scheduler=None)` (`base.py:88-104`). The scheduler decides WHERE the debounced validation batch runs: `ValidationScheduler` protocol / `SyncScheduler` (inline, deterministic — tests/headless) / `ThreadingTimerScheduler` (default, background daemon thread) in `packages/haywire-core/src/haywire/core/graph/scheduler.py:24,43,56`; `LoopScheduler` (NiceGUI event loop; handles off-loop callers via `call_soon_threadsafe`, runs inline pre-loop) in `barn/haybale-studio/haybale_studio/loop_scheduler.py:48`. The live app injects LoopScheduler via `HaystackState._make_graph_and_editor` (`haystack_state.py:189-204`). ADR: `docs/adr/0002-validation-scheduler-injection.md` (validation is pure sync CPU work; the scheduler is only a debounce).
- `subscribe_to_validation(cb)` / `unsubscribe_from_validation(cb)` (`base.py:153-179`); `force_validation()` flushes the queue **synchronously on the calling thread** (`base.py:190-198`) — per CLAUDE.md, use it when you need the `ValidationResult` synchronously or on timer-scheduler graphs.
- Non-mutating refresh requests: `request_node_redraw/revalidation/reset`, `request_edge_*`, `request_full_*` (`base.py:204-253`).
- `ValidationResult` (`packages/haywire-core/src/haywire/core/graph/types.py:161-216`): `graph: ChangeReason | None`, `nodes: dict[node_id, ChangeReason]`, `edges: dict[edge_id, ChangeReason]`, `canvas_size: (w,h) | None`, `validation_time_ms`, plus helpers (`has_changes`, `get_removed_nodes`, `get_nodes_requiring_redraw`, …).

**Loop-affinity consequence for MCP**: mutating a live (Haystack-owned, LoopScheduler) graph from an MCP thread is safe for the mutation itself (sync CPU), but the debounced validation + `GraphDataMutated` broadcast will be marshalled onto the NiceGUI loop by LoopScheduler (`loop_scheduler.py:48`, off-loop `schedule` hops via `call_soon_threadsafe` per ADR 0002). Calling `force_validation()` from a non-loop thread would run subscribers (including UI redraw + broadcast) **on that thread** — the exact hazard ADR 0002 removed. Prefer letting the debounce fire, or marshal onto the loop first.

---

## 4. Local node authoring

### 4.1 What exists for creating a new node class file

The `haywire` CLI (`[project.scripts] haywire = "haywire_studio:main"`, `packages/haywire-studio/pyproject.toml:24-25`) has exactly three subcommands — `init`, `share`, `rename` (`packages/haywire-studio/src/haywire_studio/app.py:266-355`). **There is no `new-node` / per-component scaffold command and no node template generator anywhere in the codebase.**

| Operation | Signature | sync/async | loop affinity | signals | Citation |
|---|---|---|---|---|---|
| Scaffold project + local library | `init_project(name: str, auto_sync: bool = True, dev_repo: str \| None = None)` — creates `<cwd>/<name>/` with `graphs/`, `barn/haybale-<name>/haybale_<name>/` containing **nine empty component folders** (`nodes, types, widgets, skins, adapters, settings, themes, panels, editors`, each with empty `__init__.py`), a generated library `__init__.py`, pyprojects, READMEs, `.haywire/marketplace.toml` `[[heaps]]` entry, then `uv sync --refresh` | sync (subprocess for uv); importable and callable programmatically, but calls `sys.exit(1)` if the dir exists and `print`s progress | loop-free (CLI-time; runs before/outside the app) | none | `packages/haywire-studio/src/haywire_studio/init.py:479-589`, folders `:508-522` |
| Generated library | `@library(..., file_watcher=True)` with `register_components()` calling `add_folder_to_registry(folder, registry_cls)` per component folder — so any `.py` later dropped into `nodes/` is in scope | n/a (generated source) | n/a | n/a | `init.py:272-382` (watcher flag `:320`, nodes folder `:364-367`) |
| Share library | `haywire share [library_path] [--save --strict --fix --ref --tag --bump]` — emits marketplace.toml snippet / aggregates `marketstall.toml`; not node authoring | sync CLI | loop-free | none | `app.py:289-345` |
| Rename library | `haywire rename old new [--apply]` — dry-run by default; studio must be stopped | sync CLI | loop-free (requires app NOT running) | none | `app.py:346-355`, impl `packages/haywire-studio/src/haywire_studio/rename.py` |
| Edit library metadata (UI) | marketplace Overview "Edit" dialog `build_edit_dialog(...)` — edits identity fields + pyproject dependencies (`detect_dependencies`, `write_pyproject_deps`); NOT node source | sync UI flow (async `_save`) | main-loop (NiceGUI dialog) | UNVERIFIED (UI refresh handled locally) | `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py:51`, `:177`, `:309` |
| Edit component source (UI) | `ComponentSourceEditor` — CodeMirror editor following `context.active_component` (a registry key); resolves the file via `Path(inspect.getfile(cls))`; **editing gated on `InstallType.EDITABLE`**; saving writes the file and lets the watcher hot-reload. Cannot create NEW files | sync UI | main-loop (session-bound editor) | none (hot-reload pipeline notifies) | `barn/haybale-studio/haybale_studio/editors/component_source_editor.py:53`, path `:137`, gate `:152-162` |

So "create a node" today = write a `.py` file into `<library>/nodes/` by hand (or via the ComponentSourceEditor for edits to existing ones). The de-facto template is the canon's live example `barn/haybale-example/haybale_example/nodes/math_op.py` (referenced from `docs/components/nodes/node-canon.md:116`).

### 4.2 Hot-reload pickup of a NEW file in a watched library

Wiring: each `BaseLibrary` owns one `FileWatcher(watch_path=identity.folder_path)` (`packages/haywire-core/src/haywire/core/library/base.py:53`). When `identity.file_watcher` is True (or watching is enforced), `_register_folder` pairs `registry.add_folder(...)` with `file_watcher.add_watch(folder, identity, registry, debounce)` (`base.py:245-259`), plus a root fallback routing non-component files to all registries as dependency events (`base.py:229-243`).

Pipeline for a brand-new `nodes/foo.py` (all steps verified in source):

1. watchdog `Observer` (recursive) delivers `on_created` for `*.py` on a **watchdog thread** (`packages/haywire-core/src/haywire/core/library/file_watcher.py:342-350`, `:126-137`; a CREATE for an already-known file — atomic write — is downgraded to MODIFIED).
2. Per-(file, registry) debounce via `threading.Timer`, default 0.5s (`file_watcher.py:188-227`); the debounced callback runs `registry.event_dispatcher(event)` on the **timer thread** (`file_watcher.py:229-241`).
3. `HotReloadRegistry.event_dispatcher` resolves the module name, syntax-validates the file, and routes `CREATED` → `_on_creation` (`packages/haywire-core/src/haywire/core/registry/base.py:366-435`, dispatch `:422-423`).
4. `_on_creation` imports/scans the module for managed classes, registers each, and queues a `LifeCycleEventType.CLASS_ADDED` event per class (`registry/base.py:498-547`, event `:536-543`; enum `packages/haywire-core/src/haywire/core/registry/lifecycle_event.py:23`), then notifies registry + batch subscribers (`:433-435`).
5. `NodeFactory._listen_on_lifecycle_event` fans the batch out to menu/UI listeners and per-registry-key subscribers (`packages/haywire-core/src/haywire/core/node/factory.py:116-141`).

**Yes — adding a brand-new node `.py` to a watched library folder registers it live and fires `CLASS_ADDED`.** Failure path: a broken file yields `CLASS_RELOAD_FAILED` events and keeps the class registered in an error state for consumers (`registry/base.py:437-467`). Rename = DELETED + CREATED (`file_watcher.py:152-186`).

Loop affinity caveat: everything above runs off-loop; downstream consumers must marshal to the NiceGUI loop themselves (ADR 0002 explicitly designs `LoopScheduler.schedule` to accept off-loop hot-reload callers, `docs/adr/0002-validation-scheduler-injection.md`, `barn/haybale-studio/haybale_studio/loop_scheduler.py:48`).

Note the trap: a NEW file in an EXISTING watched library is live-registered; a NEW *library folder* is not — that requires `LibraryRegistry.scan_for_libraries()` + `enable_all_libraries()` (the path `LibraryManager.install` runs, `library_manager.py:368-371`; `scan_for_libraries` at `packages/haywire-core/src/haywire/core/library/registry.py:330`).

### 4.3 What the node canon prescribes for a minimal node

`docs/components/nodes/node-canon.md`: subclass `BaseNode`, decorate with `@node(label=..., description=..., menu=..., search_tags=..., node_type=NodeType.DATA/CONTROL, hidden=...)` (`node-canon.md:46-48`), declare ports in `init()` via `self.add(FLOAT.as_inlet('x'))` etc., implement `worker(self, context: ExecutionContext, *args, **kwargs) -> str | None` where **worker parameter names bind to inlet ids** (`node-canon.md:74`, binding rule `:154`); optional lifecycle hooks `post_init`, `on_startup`, `on_frame_start`, `on_validate`, `on_frame_end` (`:54`, `:156-166`). Canonical value accessors are `self.value('inlet_id')` / `self.out('outlet_id', v)` — code confirms at `packages/haywire-core/src/haywire/core/node/data.py:458-532`; port declaration/rejig API at `data.py:189-452`. Registration is automatic via the library's folder scan — a node file needs no manual registration step (`node-canon.md:18`).

Doc/code divergence noted by the docs themselves: older docs mention `self.inlet(...)` / `self.set_outlet(...)`; those accessors do not exist in code (`node-canon.md:87`) — code wins with `value()`/`out()`.

---

## Gaps

Operations Farmhand's MCP surface would need that do NOT exist yet, or exist awkwardly:

1. **No "list `.haywire` files" API.** Graph-file discovery lives only in UI code: the file browser lazily walks `app.workspace_root` with `path.iterdir()` (`barn/haybale-studio/haybale_studio/editors/file_browser.py:100-101`, `:208-241`); the `.haywire` extension is known only to a context-menu panel (`barn/haybale-haystack/haybale_haystack/panels/file_browser/menu/file.py:32`). An MCP tool must glob the workspace itself; nothing to wrap.
2. **No node-scaffolding API.** `haywire init` creates a library with an *empty* `nodes/` folder (`init.py:508-522`); no template/generator function for a node file exists. An MCP "create node" tool would have to author the file content itself (canon + `math_op.py` as reference) — the good news is hot-reload then registers it with zero further calls (§4.2).
3. **No set-property / set-port-value operation on `Editor`, and none of it is undoable.** Editor covers structure only (§3.2). Value/settings changes go through settings-bag descriptor writes (`node/data.py:66-74`, `:121-135`; ADR 0013/0016 single-cell model) or `DataPort.set_value` / widget events — object-traversal APIs, not addressable by `(binding_id, node_id, name)` from a flat call, not in the undo history, and requiring a manual `GraphDataMutated` broadcast afterwards. This is the largest missing primitive for a graph-mutation MCP tool.
4. **No read-only structural query API.** Options are full `BaseGraph.to_dict()` (`base.py:894-919`) or walking `node_wrappers`/`edge_wrappers` in Python. No "connections of node X", no prospective type-compatibility check for an edge before `create_edge` (validation reports problems only after mutation, via `ValidationResult`/node warnings). For pure reads, parsing the `.haywire` JSON file directly is equivalent and process-independent.
5. **Cross-session signal emission is the caller's responsibility for core mutations.** `HaystackState` mutators broadcast `GraphDataMutated` themselves (§2.1), but direct `Editor` calls do not — the UI wrapper publishes after undo/redo (`graph_editor.py:302-310`). Likewise `LibraryManager` install/uninstall does not emit `LibraryCatalogChanged` (§1.4). An MCP server mutating via these APIs MUST broadcast the right signal via `SessionManager.broadcast(...)` (`session_manager.py:99`) or an `AppState._signal_emit` (`state/base.py:79-91`), or open browser UIs silently go stale.
6. **No headless / out-of-process entry point.** Every major surface is an `AppState` (`HaystackState`, `GraphAppState`, `LibraryManagerState`, `MarketplaceState`) instantiated by the DI library-state container inside the running app, with `on_enable` assuming workspace root, settings registry, and (for graphs) the importable NiceGUI loop (`haystack_state.py:189-204`). There is no RPC/IPC surface. Practical consequence: Farmhand tools either run **in-process** (grab states from the DI context; respect loop affinity per-operation flags above) or reimplement pure-file paths (`.haywire` JSON, haystack TOML, marketplace TOML — all documented formats above) for out-of-process read-only work. Anything execution- or hot-reload-related is in-process only.
7. **Loop-affinity hazards for in-process tools.** `force_validation()` from a non-loop thread runs UI subscribers + broadcasts on that thread — exactly the ADR 0002 hazard (`docs/adr/0002-validation-scheduler-injection.md`); `SignalBus`/session work is documented main-thread-only (ADR 0002 quoting the bus contract). In-process MCP mutations against live graphs should be marshalled onto the NiceGUI loop (e.g. the LoopScheduler pattern, `loop_scheduler.py:48`) rather than called from a server thread.
8. **`MarketplaceState.refresh()` is blocking sync network** (`marketplace_state.py:132-144`, urllib in `refresh.py:200-313`) — an MCP wrapper must offload to a thread to avoid stalling the loop; today's UI callers just eat the stall.
9. **No "peek haystack" API.** `persistence.load_haystack` *opens* all graphs and autostarts `execute = true` entries as a side effect (`persistence.py:147-206`). Inspecting a haystack's contents without loading means parsing the TOML directly (trivial, but unwrapped).
10. **No graph-file management API.** `remove_entry` never deletes `.haywire` files (`haystack_state.py:338-356`) and no graph-file delete API exists; the only on-disk rename path is `rename_graph` (`haystack_state.py:312`) — file management is otherwise the generic file browser's UI actions (`barn/haybale-studio/haybale_studio/editors/file_browser_menu/actions.py`, surface UNVERIFIED in detail).
11. **Subscription management is half-wrapped.** Core helpers exist and are pure file ops — `add_market_subscription_to_global(global_path, url)` / `add_stall_subscription_to_global(global_path, url)` (`packages/haywire-core/src/haywire/core/marketstall/helpers.py:24`, `:34`), block/ignore record helpers (`helpers.py:142`, `:168`), `resolve_and_subscribe(...)` (`packages/haywire-core/src/haywire/core/marketstall/subscribe.py:92`) — but the decision flows around them (first-install safety modal, conflict prompts) are UI-embedded in haybale-marketplace editors. MCP tools can wrap the helpers directly; parity with UI safety semantics (blocked lists) must be reimplemented deliberately.
12. **Component docs querying is convention, not API.** Reading a library's README/OVERVIEW/QUICKREF means `Path(identity.folder_path) / <name>.md` (§1.3); per-component "docs" are only the class docstring + `NodeInfo` identity fields. Fine to wrap, but there is no structured metadata endpoint to lean on.

