# v1 tool surface per library

Type: grilling
Status: resolved
Blocked by: 01, 03
Resolved: 2026-07-19

## Question

Which concrete MCP tools (names, inputs, outputs, destructive-or-not) does each v1 library contribute, and which doc/graph content is exposed as tools vs MCP resources?

Per ticket 06: every tool's table row must carry its MCP annotations (`readOnlyHint`/`destructiveHint`/…) — that is the consent surface clients present — and informational safety valves (e.g. a dry-run tool wrapping `LibraryManager.dry_run` ahead of install) are decided here.

Working from the operations inventory (ticket 03) and the scope line (ticket 01), settle per contributor:

- **Framework baseline** (per ticket 01: owned by the Farmhand host itself, present on a bare studio): list enabled/installed libraries, studio status/version — what else belongs in the orientation floor without preempting library surfaces?
- **haybale-marketplace**: list available libraries, query library docs, query individual components (nodes/types/widgets of a library), install a required library, versions/dependency checks — which of these, with what granularity?
- **haybale-haystack**: create new graph, list existing graphs, load/open graph, save graph, rename/remove — plus compile/start/stop execution (ticket 01 admitted execution control fully into v1).
- **haybale-graph-editor**: query a specific graph (nodes/edges/ports as structured data), add node, connect edge, set node properties — how much of the `Editor` API is exposed, and in what units (single ops vs batched transactions)? Ticket 03's inventory flags that **no set-property/port-value primitive exists on `Editor`** (settings-bag writes are non-undoable, non-addressable, and don't broadcast) — this grilling must decide whether the spec mandates a new core primitive or the tool wraps the raw paths; also decide docs exposure knowing docs are plain files under `identity.folder_path` (convention, not API — inventory §1.3, gap 12).
- Cross-cutting: docs as MCP **resources** vs query tools, and whether Farmhand ships MCP **prompts** (canned workflows). Ticket 02 settled the facts: both fully supported server-side; Claude Code surfaces resources as `@` mentions and prompts as `/mcp__…` commands; Claude Desktop surfacing is undocumented, so gate nothing on it. What remains here is the *choice* of what to expose. Also: result formats (structured JSON vs prose); pagination for big graphs/marketplaces; error contracts.

Also settle (graduated from the map's fog once ticket 05 fixed signature-derived schemas): the convention for tool-name/schema evolution across library versions — with schemas derived from handlers and clients re-fetching per session there is no stored contract, so this is likely a one-paragraph spec convention (e.g. renames are removals+additions; `CompatibilityWarning` untouched), but say it explicitly.

Output: a tool table per library, ready to be pasted into the spec. Naming follows ticket 05's rule: MCP-visible `{lib_id}_{name}`, `studio` reserved for baseline.

## Answer

Grilled 2026-07-19; all eight forks user-confirmed. **v1 surface: 29 tools, 2 resource families, 0 prompts.** Names follow ticket 05 (`{lib_id}_{name}`, `studio` reserved); annotations per ticket 06; all mutating graph tools fence per call per ticket 06.

**Catalog ownership**: component-catalog queries are BASELINE (registry truth exists on a bare studio; the brief's marketplace assignment predated the baseline decision). Marketplace keeps distribution only.

### `studio` baseline (all read-only)

| Tool | Returns |
|---|---|
| `studio_status` | versions (haywire/studio/Farmhand/protocol), workspace root, enabled-library count, open-graph count, docs-site URL |
| `studio_list_libraries` | installed libraries from `LibraryRegistry`: id, label, version, description, tags, enabled |
| `studio_list_components` | components by `library` and/or `kind` filters (registry prefix-scan `{lib_id}:{type}:{name}`) |
| `studio_describe_component` | one component's identity + docstring (a node's ports/params — read before `graph_editor_add_node`) |

### `marketplace` (full lifecycle)

| Tool | Wraps | Annotations |
|---|---|---|
| `marketplace_list_available` | merged AVAILABLE catalog (cache TOMLs) | read-only |
| `marketplace_refresh` | `MarketplaceState.refresh()` via `offload()` (blocking network) | network, rewrites caches |
| `marketplace_get_library_docs` | installed: README/OVERVIEW/QUICKREF from `identity.folder_path`; available: fetch `docs_url` (offloaded) | read-only, network |
| `marketplace_dry_run_install` | `LibraryManager.dry_run` (ticket 06's informational valve) | read-only, network |
| `marketplace_install_library` | `LibraryManager.install`; `on_output` → MCP progress; result carries `PostInstallHints` + dep-gating errors | **destructive** |
| `marketplace_uninstall_library` | `LibraryManager.uninstall_streaming` | **destructive** |

### `haystack` (graph lifecycle; haystack-FILE management deferred to v2 — load autostarts execution, gap 9, human act in v1)

| Tool | Wraps | Annotations |
|---|---|---|
| `haystack_list_graphs` | open entries (unsaved/executing status) + on-disk `.haywire` glob (closes gap 1) | read-only |
| `haystack_create_graph` | `create_new()` | mutating |
| `haystack_open_graph` | `open_graph(path)` | mutating |
| `haystack_save_graph` | `save_graph(entry, save_as?)` | mutating |
| `haystack_rename_graph` | `rename_graph` | mutating |
| `haystack_close_graph` | `remove_entry` (never deletes files — stated in description) | mutating |
| `haystack_compile_graph` | `GraphEntry.compile` → `CompileResult` errors | read-only-ish |
| `haystack_start_graph` | `start_execution` | **destructive** (real I/O) |
| `haystack_stop_graph` | `stop_execution` | mutating |

### `graph_editor` (graph by `binding_id`, elements by string ids)

| Tool | Wraps | Annotations |
|---|---|---|
| `graph_editor_query_graph` | structured read (nodes/edges/ports), filterable, paginated | read-only |
| `graph_editor_add_node` | `Editor.create_wrapper(registry_key, position)` → node id | mutating |
| `graph_editor_connect` | `Editor.create_edge(...)` | mutating |
| `graph_editor_remove_elements` | `Editor.remove_elements(nodes, edges)` (= disconnect too) | mutating |
| `graph_editor_move_nodes` | `Editor.move_nodes_to` | mutating |
| `graph_editor_set_property` | **mandated NEW undoable `Editor` primitive** (`SetPropertyAction` beside the nine existing action classes): set settings-bag field / port default by `(node_id, name)`, undo-recorded, broadcast included. The spec's one deliberate new core surface — raw path is non-undoable (gap 3), which would break ticket 06's one-timeline decision | mutating |
| `graph_editor_promote_setting` | `promote_setting(node, accessor, field, direction)` — eligibility errors surfaced | mutating |
| `graph_editor_demote_setting` | `demote_setting(node, port_id)` | mutating |
| `graph_editor_undo` / `graph_editor_redo` | `Editor.undo()/redo()` on the SHARED timeline (stated in description) | mutating, client-gated |

Promotion tools wrap the existing free functions AS-IS (UI parity: today's setting-row-menu path is not undo-routed either). "Undo-routing for promotion (UI + agent alike)" is recorded as a later-work note; `set_property` stays the sole mandated primitive because its raw path is unusable, promotion's is complete.

### Resources & prompts

- **Installed-library docs as resources**: `farmhand://library/{lib_id}/overview|quickref`, `resources/list_changed` via the same lifecycle pipeline. Complements `marketplace_get_library_docs`.
- **Framework component canons as resources**: spec mandates packaging `docs/components/*-canon.md` into the haywire-core wheel; served as `farmhand://docs/canon/{area}` — version-matched authoring reference (node authoring reads `farmhand://docs/canon/nodes` first). Architecture docs stay on the published site (URL via `studio_status`).
- **Graphs are NOT resources** (the addressed, paginated query tool is the read path). **No prompts in v1** (product content without demand evidence; `prompts_changed` plumbing stays wired).

### Conventions (spec-wide)

1. Structured-JSON results + one-line human summary per tool.
2. List tools take `limit`/`offset` (sane defaults) and return `total` — no context blowouts on big graphs/catalogs.
3. Failures = MCP tool errors with stable code + actionable message + offending ids; never stack traces. `HaywireException` structure maps directly.
4. Schema evolution: schemas derive from handlers so they change only with library code; clients learn via per-session re-fetch + `list_changed`; a rename is removal+addition; `CompatibilityWarning` (saved graphs) is not involved.

Map updates: Final-spec-assembly fog graduated into ticket 11 (task, blocked by 08/09/10) — fog now empty; ticket 08 pointed at the canon resource URI.
