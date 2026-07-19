# Session, concurrency & safety model

Type: grilling
Status: resolved
Blocked by: 04
Resolved: 2026-07-19

## Question

Under whose identity and with what guardrails do MCP calls act on shared studio state?

- **Session identity**: browser clients each get a haywire session via `SessionManager`; shared state (`HaystackState`, `LibraryRegistry`) is process-global. Does an MCP client get its own session, act session-less against shared state, or bind to an existing browser session?
- **Concurrency**: MCP mutations racing live browser edits on the same graph — serialization point (NiceGUI main loop? `Editor` transactions?), and undo/redo ownership for MCP-driven edits (do they enter the same undo stack the user sees?).
- **Thread/loop affinity**: which operations must run on the NiceGUI main loop (ADR 0002 validation scheduling; `LoopScheduler`), and how the MCP transport marshals onto it.
- **Safety posture**: the tool surface includes installing packages (`LibraryManager.install` runs `uv pip install`) and potentially writing node code — near-arbitrary code execution. Localhost-only binding? Token auth? Per-tool confirmation tier (destructive vs read-only annotations)? Informed by the auth findings of ticket 02 and the client expectations settled in ticket 01.

## Answer

Grilled 2026-07-19 (session/undo machinery read first: `HistoryManager` is per-graph on the server-side `Editor` — the undo stack is *already* shared across browser sessions; `SessionManager` sessions are UI containers, and `broadcast()` needs no sender session). All forks user-confirmed:

1. **Session identity: none.** MCP clients get no haywire session. Farmhand tools act directly on shared state and broadcast via `SessionManager.broadcast()` — the same session-less pattern `HaystackState` mutators use. Rejected: synthetic agent sessions (dead UI weight), binding to a browser session (contradicts the decided lifecycle). Attribution, if ever wanted, is tool-call metadata, not sessions.
2. **Undo: one shared timeline.** Agent structural edits enter the graph's existing shared `HistoryManager` via `Editor`; `FarmhandContext` fences each mutating tool call (`add_fence()` around it) so one tool call = one undo gesture. Humans can undo agent actions from the UI; agent-facing undo/redo tools (if ticket 07 adds them) drive the same stack. Rejected: separate agent stack (two histories over one graph can't both be truthful), bypassing history (removes the human safety net).
3. **Concurrency: loop-serialization, no locks, no client cap.** Mutation slices run on the single NiceGUI asyncio loop (interleaving only at `await` boundaries — the same consistency browser sessions get among themselves); long work goes through `FarmhandContext.offload()`. Multiple MCP clients are simply multiple callers under the same rules — **this resolves the map's multi-agent-concurrency fog**. If contention pathologies emerge, a lock can be added behind `FarmhandContext` without touching any tool.
4. **Auth: three cheap layers.** Bind 127.0.0.1; configure `TransportSecuritySettings` explicitly (allowed hosts/origins — SDK's DNS-rebinding protection is off when unset, per ticket 02); require a static bearer token, auto-generated per workspace on first Farmhand start, stored gitignored under the workspace `.haywire/` (spec must state the gitignore), 401 on mismatch, delete-file-to-rotate. Studio settings UI surfaces a ready `claude mcp add --transport http farmhand http://127.0.0.1:8082/mcp --header "Authorization: Bearer …"` line. Rejected: no-token loopback ("any local process" is too broad for install+code-write powers), OAuth 2.1 (disproportionate, per research).
5. **Destructive-op consent is client-side.** Every `FarmhandTool` declares the MCP spec's tool annotations (`readOnlyHint`, `destructiveHint`, …) in its metadata; the human gate is the MCP client's permission flow (Claude Code per-tool allowlisting). No server-side confirmation queue (double-asking trains click-through), no "safe mode" toggle (would re-litigate ticket 01's full-power-with-guardrails decision). Blunt instruments: the FrameworkSettings off-switch and the token. Informational valves (e.g. a dry-run tool wrapping `LibraryManager.dry_run` before install) belong to ticket 07's surface.

Map updates: multi-agent-concurrency fog cleared (decided here); ticket 07 noted to assign annotations per tool.
