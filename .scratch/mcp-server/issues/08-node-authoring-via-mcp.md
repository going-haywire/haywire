# Node authoring via MCP (new nodes in the local library)

Type: grilling
Status: resolved
Blocked by: 01, 03
Resolved: 2026-07-19

## Question

How should an MCP client create *new node classes* in the project-local haybale library for use in graphs — the most powerful and riskiest capability in the brief?

Ticket 01 confirmed it: in scope for v1, risk handled by guardrails here and in ticket 06. To settle:

- **Generation shape**: template-based scaffolding (constrained: ports/params declared, body filled in) vs free-form Python file writes into `barn/<local-lib>/nodes/`; what the node-authoring canon (`docs/components/`) prescribes. Note ticket 07: the canons ship in the wheel as version-matched resources — the authoring loop starts with the agent reading `farmhand://docs/canon/nodes`.
- **Validation loop**: how the MCP client learns whether the new node imported/registered cleanly — surfacing file-watcher hot-reload results (registry add events, import errors) back through MCP instead of a silent write.
- **Placement**: which library receives the node (the project's local barn library? user-chosen?), and what happens when no local library exists yet (scaffold one? require `haywire init` first?).
- **Safety interplay**: how this capability sits inside ticket 06's confirmation/auth tiers.
- Whether editing *existing* nodes is included or explicitly out of scope for v1.

## Answer

Grilled 2026-07-19; all forks user-confirmed. Two user constraints reshaped the mid-grilling design: (1) the MCP client cannot be assumed to have filesystem access to the haywire workspace — authoring must be self-contained through Farmhand; (2) authoring covers ALL component kinds, not just nodes. Grounding: the studio already has an in-app component-source Edit flow (`component_source_editor`, `is_project_library` in the marketplace Edit dialog) — agent authoring mirrors an existing human capability.

1. **Ownership: `studio` baseline** (not graph-editor as the brief worded it — same registry-level reasoning that moved the component catalog in ticket 07; the brief predated the baseline concept).
2. **Shape: three kind-generic tools, no client file access assumed.**
   - `studio_scaffold_component(library, kind, name, …)` — canon-conformant skeleton per kind (templates derived from the same canons shipped as `farmhand://docs/canon/{kind}`), returns file path + expected registry key.
   - `studio_read_component_source(registry_key)` — line-numbered source of any installed component (reference reading).
   - `studio_write_component_source(registry_key | path, source)` — full-source write, **restricted to project-local (barn) libraries** via the `is_project_library` boundary; site-packages libraries read-only; heaviest destructive annotation, client-gated. Hot-reload registers the result (watchdog → debounce → import → `CLASS_ADDED`), no further calls.
   Rejected: scaffold-only + client file tools (breaks the no-file-access constraint); nodes-only write (arbitrary asymmetry); constrained no-code DSL (can't express real workers).
3. **Verification: `studio_verify_component(registry_key, timeout)`, ledger-backed, staged.** For nodes it goes past registration: trial-instantiate a `NodeWrapper` in a scratch context and run the existing `on_testrun()` hook — wrapper/instantiation-stage errors (the richest diagnostics) surface at authoring time, not when a user drags the node into a graph. Returns registered → instantiable → test-passed with relevant ledger entries at the failing stage.
   **Mandates the spec's THIRD core work item: the global error ledger** — a bounded in-memory collection where every `HaywireException` registers at `.log()` time with a monotonic sequence number; registry-scan import errors get wrapped into `HaywireException` so parse-, instantiation-, and runtime-stage failures share one ledger (the user's independently-planned design; Farmhand is its first consumer).
   Plus baseline tool `studio_get_errors(since_seq?, library?, registry_key?)` — "what broke since my last action"; tool results carry the current cursor.
4. **Placement: explicit `library` param.** Default = the single project-local library; zero → error pointing at `haywire init` (human, studio-stopped); several → error listing candidates. No `studio_create_library` in v1 (project-level surgery with an existing human path).
5. **Editing existing components: in v1.** Same write/verify loop for any project-local component; live graphs pick up hot-reload's existing class-swap semantics (stated in the tool description); git history is the source-level undo.

**Surface delta vs ticket 07**: `studio` baseline grows 4 → 9 (`scaffold_component`, `read_component_source`, `write_component_source`, `verify_component`, `get_errors`); **v1 total: 34 tools**.

Map updates: glossary gains the Error ledger term; spec-assembly ticket now waits only on the prototype and testing strategy.
