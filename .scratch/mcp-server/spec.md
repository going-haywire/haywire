---
title: "Farmhand — the Haywire MCP server"
status: settled
created: 2026-07-19
effort: .scratch/mcp-server/ (wayfinder map + 11 tickets; each section cites its deciding ticket)
handoff: /writing-plans
---

# Farmhand — the Haywire MCP server (v1 spec)

Farmhand lets AI-agent clients operate a running Haywire studio through the Model
Context Protocol: query and install libraries, manage and execute graphs, edit graph
structure, and author new components — with every capability contributed **per haybale
library** through the registry system. Vocabulary is canonical in
[`docs/reference/glossary.md`](../../docs/reference/glossary.md) (sections *Farmhand — MCP
server*: Farmhand, MCP tool, Error ledger).

Decision detail lives in the wayfinder tickets under [`issues/`](issues/); research facts
with primary-source citations live in [`assets/mcp-sdk-research.md`](assets/mcp-sdk-research.md)
and [`assets/wrappable-operations-inventory.md`](assets/wrappable-operations-inventory.md).
This spec is the assembled, binding summary.

## 1. Scope (ticket 01)

- **Copilot-first**: v1 targets an agent (Claude Code-style, trusted local user)
  connected to the user's *live* studio; changes appear in open browser sessions.
  Headless hosts are a kept-open door, **not designed** here.
- **Contributors**: haybale-marketplace, haybale-haystack, haybale-graph-editor, plus a
  **framework-owned baseline** (`studio` namespace) that exists on a bare studio and is
  the contribution API's reference implementation.
- **Full mutation surface** in v1, including component authoring and execution control.
  Risk is carried by guardrails (§5, §7), not scope cuts.
- **Deliverable**: this spec; implementation is a separate effort via `/writing-plans`.

## 2. Architecture (tickets 04, 09)

- **In-process.** Farmhand mounts on the studio's existing FastAPI app (precedent:
  `register_code_intelligence_endpoints()`, `app.py:48-49`). Tools resolve services from
  the ambient DI context; no sidecar, no second read path.
- **Packaging**: host in **haywire-studio** (transport mount, lifespan wiring, live-session
  registry, `list_changed` plumbing, baseline tools, the `mcp` dependency); SDK-free
  contribution seam in **haywire-core**. `haybale-farmhand` as an optional package is
  **ruled out** (transport lifespan can't follow library enable/disable; baseline must
  exist on a bare studio).
- **Lifecycle**: a `FrameworkSettings` flag, **enabled by default**, read once at startup;
  changes take effect on restart.
- **Endpoint**: `/mcp` on the studio's port. SDK internal path `/`, full prefix in the
  mount (307-trap avoidance). No SSE endpoint. Client setup:
  `claude mcp add --transport http farmhand http://127.0.0.1:8124/mcp --header "Authorization: Bearer <token>"`.
- **Stack**: official `mcp` SDK v1.x, pinned **`mcp>=1.28,<2`** in haywire-studio;
  protocol 2025-11-25; low-level `NotificationOptions(tools_changed=True,
  prompts_changed=True, resources_changed=True)` so `listChanged` is advertised
  correctly (the FastMCP wrapper default advertises `false` — confirmed empirically).
- **Lifespan (prototype-proven, supersedes the research recipe)**: the session manager
  runs in a **single long-lived runner task** that itself enters
  `session_manager.run()`, signals started, and waits for a stop event; `on_startup`
  spawns it, `on_shutdown` signals and awaits it. The AsyncExitStack-across-handlers
  shape **crashes NiceGUI shutdown** (anyio cancel-scope/task mismatch) — see
  [`.insights/feedback_nicegui_lifespan_task_scope.md`](../../.insights/feedback_nicegui_lifespan_task_scope.md).
- **Version strategy**: a breaking MCP spec revision lands 2026-07-28 and SDK v2 goes
  stable ~2026-07-27. Build on v1.x/2025-11-25 now; re-evaluate ~Sept/Oct 2026 once
  Claude clients advertise support (the stateless core will eventually simplify the
  session registry).

## 3. Contribution mechanism (ticket 05)

- **A tenth typed registry** in haywire-core: `FarmhandToolRegistry` (kind constant
  `mcp`), DI singleton, linked via `add_class_registry` like its siblings. Libraries
  contribute with `self.add_folder_to_registry(str(base_path / "mcp"),
  registry_cls=FarmhandToolRegistry)`. Tools are a new **Component** kind, keyed
  `{lib_id}:mcp:{name}`, inheriting folder-scan, hot-reload, eviction, and lifecycle
  events. `mcp/` scans after `state/` in the canonical order.
- **One class per tool**: a `FarmhandTool` subclass — declarative metadata (label,
  description, MCP annotations) + one **async** `run(ctx, ...)` handler. (Async is
  load-bearing: the SDK thread-offloads sync functions, breaking loop affinity.)
- **Input schema**: derived from the `run()` signature (type hints + defaults → JSON
  Schema, the node-`worker()` idiom), optional class-attribute override.
- **Naming**: MCP-visible name `{lib_id}_{name}`; `studio` is a reserved prefix no
  library id may claim (enforced at registration).
- **`FarmhandContext`** passed to every handler: typed DI accessors, `broadcast(signal)`
  (cross-session signal emission is caller-owned for core mutations — inventory gap 5),
  `offload(fn)` (blocking work off the shared NiceGUI loop), MCP progress bridging
  (streams `on_output` callbacks), cancellation. Future enforcement point for guardrails.
- **One change pipeline**: the studio host subscribes to the registry's
  `CLASS_ADDED`/`CLASS_REMOVED` events; on add → wrap as SDK tool, `add_tool`,
  `send_tool_list_changed()` to every live session (Farmhand owns a live-session
  registry — no stack auto-notifies on the hot-reload path); on remove → inverse.
  Enable/disable/hot-reload/install/uninstall all flow through registry events.
  **Baseline tools register through the same registry** at startup.

## 4. Session, concurrency & safety model (ticket 06)

- **No sessions for agents**: tools act on shared state and broadcast session-lessly
  (the `HaystackState` pattern). Attribution, if ever needed, is tool-call metadata.
- **One undo timeline**: structural edits go through `Editor` into the shared per-graph
  `HistoryManager`; `FarmhandContext` fences each mutating tool call (one call = one
  undo gesture). Humans can undo agent actions from the UI.
- **Concurrency**: loop-serialization only (mutation slices on the single NiceGUI loop);
  no locks, no client cap — multiple agents are multiple callers. A lock can be added
  behind `FarmhandContext` later without touching tools.
- **Auth**: bind 127.0.0.1; **explicitly configure** `TransportSecuritySettings`
  (allowed hosts/origins — SDK DNS-rebinding protection is off when unset); static
  bearer token auto-generated per workspace on first start, stored **gitignored** under
  `<workspace>/.haywire/`, 401 on mismatch, delete-file-to-rotate. Studio settings UI
  shows the ready-made `claude mcp add … --header` line. No OAuth.
- **Consent is client-side**: every tool declares MCP annotations
  (`readOnlyHint`/`destructiveHint`/…); the human gate is the client's per-tool
  permission flow. No server-side confirmation queue, no safe-mode toggle.

## 5. v1 surface — 34 tools, 2 resource families, 0 prompts (tickets 07, 08)

Conventions (all tools): structured-JSON result + one-line summary; list tools take
`limit`/`offset` and return `total`; failures are MCP tool errors with stable code +
actionable message + offending ids, never stack traces (`HaywireException` maps
directly); schema evolution = schemas change only with library code, clients learn via
re-fetch + `list_changed`, a rename is removal+addition, `CompatibilityWarning` is not
involved.

### `studio` baseline (9)

| Tool | Purpose | Annotations |
|---|---|---|
| `studio_status` | versions, workspace root, enabled-library/open-graph counts, docs-site URL | read-only |
| `studio_list_libraries` | installed libraries (id, label, version, tags, enabled) | read-only |
| `studio_list_components` | component catalog by `library`/`kind` (registry prefix-scan) | read-only |
| `studio_describe_component` | one component's identity + docstring | read-only |
| `studio_scaffold_component` | canon-conformant skeleton (any kind) into a project-local library; returns path + expected registry key | mutating |
| `studio_read_component_source` | line-numbered source of any installed component | read-only |
| `studio_write_component_source` | full-source write, **project-local libraries only** (`is_project_library`) | **destructive** |
| `studio_verify_component` | staged verification: registered → (nodes) trial `NodeWrapper` instantiation → `on_testrun()`; ledger entries attached at the failing stage | read-only |
| `studio_get_errors` | error-ledger query (`since_seq`, `library`, `registry_key`); results carry the current cursor | read-only |

Authoring is **self-contained through Farmhand** (no client filesystem access assumed)
and kind-generic. Target library: explicit param, defaulting to the single project-local
library; zero → error pointing at `haywire init`; several → error listing candidates.
Editing existing project-local components uses the same write/verify loop; git is the
source-level undo.

### `marketplace` (6)

| Tool | Wraps | Annotations |
|---|---|---|
| `marketplace_list_available` | merged AVAILABLE catalog | read-only |
| `marketplace_refresh` | `MarketplaceState.refresh()` via `offload()` | network, rewrites caches |
| `marketplace_get_library_docs` | installed: docs from `identity.folder_path`; available: `docs_url` fetch | read-only, network |
| `marketplace_dry_run_install` | `LibraryManager.dry_run` | read-only, network |
| `marketplace_install_library` | `LibraryManager.install` (progress-streamed; `PostInstallHints` + dep-gating in result) | **destructive** |
| `marketplace_uninstall_library` | `LibraryManager.uninstall_streaming` | **destructive** |

### `haystack` (9)

| Tool | Wraps | Annotations |
|---|---|---|
| `haystack_list_graphs` | open entries + on-disk `.haywire` glob | read-only |
| `haystack_create_graph` | `create_new()` | mutating |
| `haystack_open_graph` | `open_graph(path)` | mutating |
| `haystack_save_graph` | `save_graph(entry, save_as?)` | mutating |
| `haystack_rename_graph` | `rename_graph` | mutating |
| `haystack_close_graph` | `remove_entry` (never deletes files) | mutating |
| `haystack_compile_graph` | `GraphEntry.compile` → `CompileResult` | read-only-ish |
| `haystack_start_graph` | `start_execution` | **destructive** (real I/O) |
| `haystack_stop_graph` | `stop_execution` | mutating |

### `graph_editor` (10)

| Tool | Wraps | Annotations |
|---|---|---|
| `graph_editor_query_graph` | structured nodes/edges/ports read, filterable, paginated | read-only |
| `graph_editor_add_node` | `Editor.create_wrapper` | mutating |
| `graph_editor_connect` | `Editor.create_edge` | mutating |
| `graph_editor_remove_elements` | `Editor.remove_elements` (= disconnect) | mutating |
| `graph_editor_move_nodes` | `Editor.move_nodes_to` | mutating |
| `graph_editor_set_property` | **new undoable `Editor` primitive** (core work item 1) | mutating |
| `graph_editor_promote_setting` | `promote_setting(...)`, eligibility errors surfaced | mutating |
| `graph_editor_demote_setting` | `demote_setting(...)` | mutating |
| `graph_editor_undo` / `graph_editor_redo` | shared timeline (stated in description) | mutating, client-gated |

### Resources & prompts

- **Installed-library docs**: `farmhand://library/{lib_id}/overview|quickref` — same
  lifecycle pipeline drives `resources/list_changed`.
- **Component canons**: `farmhand://docs/canon/{area}` — served from canons packaged
  into the haywire-core wheel (core work item 2); version-matched authoring reference.
  Authoring flows start by reading `farmhand://docs/canon/nodes`.
- Graphs are **not** resources (the query tool is the read path). **No prompts in v1**
  (`prompts_changed` plumbing stays wired).

## 6. Mandated core work items

1. **Undoable `set_property` `Editor` primitive** — a `SetPropertyAction` beside the
   nine existing action classes: set a settings-bag field / port default by
   `(node_id, name)`, undo-recorded, broadcast included. Without it the raw path is
   non-undoable and breaks the one-timeline model (inventory gap 3).
2. **Canon packaging** — `docs/components/*-canon.md` ships in the haywire-core
   distribution so Farmhand can serve version-matched authoring resources.
3. **Error ledger** — bounded in-memory collection; every `HaywireException` registers
   at `.log()` time with a monotonic sequence number; registry-scan import errors are
   wrapped in. First consumers: `studio_get_errors`, `studio_verify_component`.

## 7. Testing strategy (ticket 10)

Two tiers on existing markers; **no browser tests in v1** (optional later addition).
`tests/farmhand/conftest.py` provides: session-scoped `farmhand_server` (the
`library_system` idiom — full barn libraries, global-injector set/clear, runner-task
mount, ephemeral-port uvicorn in a background thread), per-test `farmhand_client`
(fresh SDK `ClientSession`, own `asyncio.run`), and a bare-studio variant. Test MCP
components live in **haybale-testing**'s new `mcp/` folder.

Coverage the implementation must land (each row traces to a decided behavior):

| Tier | Contract |
|---|---|
| unit | registry add/evict; schema derivation (types/defaults/override); naming + `studio` reservation; annotations |
| unit | `SetPropertyAction` undo/redo/serialization |
| integration | initialize advertises `listChanged: true` (regression vs SDK default) |
| integration | tool round-trip structured JSON; structured error contract |
| integration | disable/enable haybale-testing → client observes `tools/list_changed` → list shrinks/grows |
| integration | mutating tool on the loop; blocking tool via `offload()` doesn't stall a concurrent request |
| integration | one tool call = one undo fence |
| integration | auth: missing/wrong token → 401; disallowed Origin rejected; token file created gitignored |
| integration | bare-studio fixture serves exactly the baseline tools |

## 8. Later work (recorded, not v1)

Promotion undo-routing (UI + agent alike); haystack-*file* tools (list/load/save —
load autostarts execution, gap 9); offline file-format reads (headless door); MCP
prompts; Claude Desktop bridge (stdio `mcp-remote` — Desktop connectors can't reach
localhost); `studio_create_library`; diff-based component editing; optional Playwright
end-to-end test; SDK v2 / 2026-07-28 spec migration (~fall 2026).

## 9. Non-goals

Headless MCP host design; OAuth; server-side confirmation UI; separate agent undo
stack; per-agent sessions; graphs-as-resources; prompt authoring.

---

*Assembled 2026-07-19 from the wayfinder map [`map.md`](map.md). No contradictions
between resolved tickets were found during assembly; the one supersession (research's
lifespan recipe → prototype's runner-task pattern) is explicit in §2.*
