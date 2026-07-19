# Inventory of wrappable operations per library

Type: research
Status: resolved
Blocked by: —
Resolved: 2026-07-19
Asset: [assets/wrappable-operations-inventory.md](../assets/wrappable-operations-inventory.md)

## Question

For each candidate contributing library, what operations does the codebase *already* expose that MCP tools could wrap, and where are the gaps against the brief? Produce a markdown inventory (linked asset in this directory) covering:

- **haybale-marketplace**: `LibraryManager` (list_installed, install/dry_run/uninstall, fetch_versions, dependency queries), `MarketplaceState`/marketstall parsing for *available* (not-installed) libraries, and what "query for the docs / individual components" could read (README/OVERVIEW/QUICKREF from `haybale-gen-docs`, `NodeRegistry` metadata, `LibraryIdentity` fields).
- **haybale-haystack**: `HaystackState` (create_new, open_graph, save_graph/_save_entry, rename, remove, load_haystack, list entries), `GraphEntry` (compile/start/stop, run_settings), haystack TOML persistence.
- **haybale-graph-editor**: `GraphAppState`, the `GraphContainer` protocol, and — critically — the `Editor` mutation API surface (`packages/haywire-core/src/haywire/core/graph/editor.py`): add/remove node, connect/disconnect edge, set props, undo/redo transactions. This is the least-mapped area; enumerate its public methods and their preconditions.
- **Local node authoring**: what exists today for creating a node class file in a project-local barn library (templates? `haywire init` scaffolding?) and how the file-watcher hot-reload picks it up.
- For every operation: sync/async, thread-affinity constraints (NiceGUI main-loop, ADR 0002 validation scheduling), and whether it broadcasts cross-session signals.

Gaps found here feed the tool-surface grilling; do not design tools in this ticket.

## Answer

Full inventory with per-operation tables (sync/async, loop-affinity, cross-session-signal flags, file:line citations): [assets/wrappable-operations-inventory.md](../assets/wrappable-operations-inventory.md). Headlines:

- **Marketplace is the most wrap-ready area.** `LibraryManager`'s install/uninstall/dry-run are async with streaming `on_output` callbacks (maps cleanly to MCP progress); list/query methods are sync and loop-free. The AVAILABLE catalog is plain TOML on disk; per-library component listing is registry-key prefix scanning (`{lib_id}:{type}:{name}`) — the same pattern the Library Overview editor uses. Library docs are plain files under `lib.identity.folder_path` (convention, not API). Caveat: `MarketplaceState.refresh()` is synchronous blocking network.
- **Haystack is a complete, self-signaling surface.** Every `HaystackState` mutator broadcasts `GraphDataMutated` itself; `persistence.py` is pure I/O over `<workspace>/haystacks/*.toml`; `GraphEntry` gives per-graph compile/start/stop.
- **Graph mutation: core `Editor` is the full undoable *structural* API** (create/paste/move/remove nodes, create/split/dissolve edges, undo/redo, `add_fence` as the only transaction primitive), all sync, string-id addressed — but it **broadcasts nothing** (signal emission is the caller's job) and has **no set-property/port-value operation** (the largest missing primitive; settings-bag writes are object-traversal, non-undoable). Reads = `BaseGraph.to_dict()` or parsing `.haywire` JSON directly. Validation affinity: live graphs schedule via `LoopScheduler` on the NiceGUI loop; calling `force_validation()` from a foreign thread reintroduces the ADR 0002 hazard.
- **Node authoring: no scaffolding API exists** (`haywire init` creates empty component folders; CLI is init/share/rename only) — but hot-reload fully supports brand-new files: watchdog `on_created` → debounce → import → `CLASS_ADDED`, no further calls needed. A new library *folder* additionally needs `scan_for_libraries()`.
- **12 gaps catalogued**, the structural ones being: no list-`.haywire`-files API; no node scaffold; no undoable set-property primitive; no read-only structural query short of full serialization; caller-owned signal broadcasting for core mutations; **no headless/out-of-process entry point** (every surface is a DI-container `AppState` inside the running app → Farmhand is in-process, or file-format-based for pure reads); blocking `refresh()`; no side-effect-free "peek haystack" (load autostarts execution).
- One doc/code divergence found, already self-flagged in the node canon (old `self.inlet()`/`set_outlet()` accessors vs. actual `value()`/`out()`).

Feeds: ticket 04 (in-process consequence), ticket 05 (signal-broadcast responsibility), ticket 06 (loop-affinity hazards), tickets 07/08 (surface + gaps).
