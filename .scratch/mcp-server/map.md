# Map: Haywire MCP server

Labels: wayfinder:map
Status: complete
Created: 2026-07-18
Completed: 2026-07-19 — destination reached: [spec.md](spec.md); handoff to /writing-plans

## Destination

A settled, implementation-ready spec at `.scratch/mcp-server/spec.md` for **Farmhand** — the Haywire MCP server whose capabilities are contributed **per haybale library** — covering the process/transport model, the library contribution mechanism (how a library adds MCP tools when enabled and removes them when disabled), the session/concurrency/safety model, and the v1 tool surface (framework baseline + haybale-marketplace, haybale-haystack, haybale-graph-editor). Done when nothing is left to decide before `/writing-plans` can take over.

## Notes

- Domain: Haywire visual-programming studio (Python + NiceGUI/FastAPI, `injector` DI, reactive props, haybale plugin libraries). Vocabulary: `docs/reference/glossary.md` — "library" has five meanings there; be precise.
- Hard project rule (CLAUDE.md): do NOT assume registration paths, ownership models, or singletons — every contribution-mechanism decision goes through the user. That is what the grilling tickets are for.
- Skills to consult per ticket: `/inquisition` + `/domain-modeling` for grilling tickets, `/design` for anything touching class hierarchies or DI wiring, `/research` for AFK research tickets, `/prototype` for the prototype ticket, `haywire-libs` to load library-system docs.
- Grounding facts already established while charting (verify, don't re-derive):
  - Studio entry: `HaywireApp` in `packages/haywire-studio/src/haywire_studio/app.py`, runs `ui.run(port=8124)` on NiceGUI/FastAPI; shared services + `LibraryRegistry` are process-global, sessions are per browser client via `SessionManager`.
  - Library extension pattern: `@library` decorator + `BaseLibrary.register_components()` adding folders to typed registries (`NodeRegistry`, `SettingsRegistry`, `PanelRegistry`, `EditorTypeRegistry`, `LibraryStateRegistry`, …) in `packages/haywire-core/src/haywire/core/library/base.py`.
  - Marketplace: `LibraryManager` (`barn/haybale-marketplace/haybale_marketplace/library_manager.py`) already implements list/install/uninstall/dry-run/versions/dependency queries over `core/marketstall`.
  - Haystack: `HaystackState` (`barn/haybale-haystack/haybale_haystack/state/haystack_state.py`) implements create_new/open_graph/save_graph/load_haystack; `GraphEntry` adds compile/start/stop execution. Mutations broadcast `GraphDataMutated` cross-session, so in-process MCP mutations would light up open browser UIs for free.
  - Graph editor: `GraphAppState` registry + `Editor` (undo/redo mutation wrapper) are the programmatic mutation surface.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- [Destination & v1 scope](issues/01-destination-and-v1-scope.md) — copilot-first (headless deferred); three briefed libraries + framework baseline tools; full mutation surface incl. node authoring; execution control in; spec+prototype deliverable; subsystem named **Farmhand** (packaging decided later by complexity).
- [MCP Python SDK capabilities research](issues/02-mcp-sdk-research.md) — build on official `mcp` v1.x (`>=1.28,<2`), Streamable HTTP mounted via parent-lifespan trick; no stack auto-notifies `tools/list_changed` on the hot-reload path, so Farmhand must own a live-session registry; Claude Desktop can't reach localhost (Claude Code is the native client); breaking spec revision 2026-07-28 → re-evaluate pin in fall 2026. Full report: [assets/mcp-sdk-research.md](assets/mcp-sdk-research.md).
- [Inventory of wrappable operations per library](issues/03-wrappable-operations-inventory.md) — marketplace most wrap-ready (async streaming install); haystack complete & self-signaling; core `Editor` = full undoable structural API but broadcasts nothing and has no set-property primitive (largest gap); no node-scaffolding API but hot-reload registers brand-new files unaided; no headless entry point → in-process or file-format reads; 12 gaps catalogued. Full inventory: [assets/wrappable-operations-inventory.md](assets/wrappable-operations-inventory.md).
- [Process & transport model](issues/04-process-and-transport-model.md) — in-process, mounted at `/mcp` on the studio's own port; host lives in haywire-studio (with the `mcp>=1.28,<2` dep), SDK-free contribution seam in haywire-core; optional `haybale-farmhand` packaging ruled out; FrameworkSettings flag, on by default, applied at startup; official SDK v1.x with low-level `NotificationOptions`.
- [Library contribution mechanism](issues/05-library-contribution-mechanism.md) — new typed registry in core (`FarmhandToolRegistry`), `mcp/` folder convention, tools = new Component kind keyed `{lib_id}:mcp:{name}`; one `FarmhandTool` class per tool with signature-derived schema; MCP names `{lib_id}_{name}` (`studio` reserved for baseline); handlers get a `FarmhandContext` (broadcast/offload/progress); host drives SDK add/remove + `list_changed` off registry lifecycle events — one pipeline, baseline included.
- [Session, concurrency & safety model](issues/06-session-concurrency-safety.md) — agents get no haywire session (session-less shared-state access + broadcasts); agent edits enter the shared per-graph undo stack, fenced per tool call; loop-serialization with no locks and no client cap (multi-agent fog resolved); auth = loopback + explicit `TransportSecuritySettings` + per-workspace gitignored bearer token with copy-paste setup line; consent is client-side via MCP tool annotations — no server confirmation gates.
- [v1 tool surface](issues/07-v1-tool-surface.md) — 29 tools: `studio` baseline ×4 (incl. component catalog), `marketplace` ×6 (full lifecycle incl. uninstall + dry-run), `haystack` ×9 (graph lifecycle + compile/start/stop; haystack files deferred), `graph_editor` ×10 (incl. mandated new undoable `set_property` core primitive; promotion wrapped as-is). Resources: installed-library docs + component canons packaged into the wheel (`farmhand://docs/canon/…`); no prompts v1. Spec-wide conventions: structured JSON, `limit`/`offset`/`total`, structured errors, four-sentence schema-evolution rule.
- [Node authoring via MCP](issues/08-node-authoring-via-mcp.md) — generalized to ALL component kinds, self-contained through Farmhand (no client filesystem access assumed): `studio` scaffold/read/write component-source tools (writes bounded to project-local libraries via `is_project_library`), staged `studio_verify_component` (for nodes: registration → trial instantiation → `on_testrun`), and `studio_get_errors` — mandating the global `HaywireException` **error ledger** as the spec's third core work item. Baseline grows to 9 tools; v1 total 34.
- [Prototype: minimal MCP endpoint inside the running studio](issues/09-mount-prototype.md) — mount PROVEN against the real studio: MCP session + tool calls work, socket.io unaffected, async tools on the main loop, mutation broadcast clean, `listChanged:false` quirk confirmed. Discovery: the AsyncExitStack lifespan recipe crashes NiceGUI shutdown (cancel-scope/task mismatch) — spec mandates the single-runner-task pattern instead. Assets: [prototype/](prototype/).
- [Testing strategy for Farmhand](issues/10-testing-strategy.md) — two tiers on existing markers (no browser tests v1); session-scoped `farmhand_server` fixture (library_system idiom, runner-task mount, ephemeral-port uvicorn) + per-test SDK clients + bare-studio variant; test MCP components in haybale-testing's `mcp/`; nine-row coverage table incl. the `listChanged:true` regression, affinity/offload, undo-fence, and auth-rejection contracts; prototype stays throwaway, patterns lifted.
- [Final spec assembly](issues/11-final-spec-assembly.md) — **destination reached**: [spec.md](spec.md) assembled from all ten resolutions, contradiction-free (one explicit supersession: research lifespan recipe → prototype runner-task pattern). Handoff: `/writing-plans`.

## Not yet specified

(empty — the way is fully charted; the remaining open tickets are the route)

## Out of scope

<!-- gist + why + link to the closed ticket, when something gets ruled out -->

(nothing ruled out yet)
