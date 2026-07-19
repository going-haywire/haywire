# Prototype: minimal MCP endpoint inside the running studio

Type: prototype
Status: resolved
Blocked by: 04
Resolved: 2026-07-19
Asset: [prototype/farmhand_mount_prototype.py](../prototype/farmhand_mount_prototype.py) + [prototype/client_check.py](../prototype/client_check.py)

## Question

Does the chosen process/transport model (ticket 04) actually work against the real studio — before the spec commits to it?

Build a throwaway prototype (via `/prototype`): the smallest possible MCP server mounted per ticket 04's decision (e.g. Streamable HTTP on the NiceGUI/FastAPI app), exposing one hardcoded read tool (say, list open haystack entries via `HaystackState`) and, if cheap, one mutating tool (create_new graph) to observe the cross-session `GraphDataMutated` broadcast lighting up a live browser session.

Success criteria to react to with the user:

- A real MCP client (Claude Code / MCP inspector) connects and calls the tool while the studio serves a browser session.
- No interference with NiceGUI's socket.io/uvicorn lifecycle (startup, shutdown, hot-reload of libraries).
- Thread/loop-affinity of state reads and mutations observed and noted — feeds ticket 06 if it runs after, or validates it if already settled.

Link the prototype branch/directory as the asset; the reaction, not the code, is the resolution.

## Answer

Built and run 2026-07-19 against the REAL studio (workspace = the monorepo, user's actual haystack rehydrated); user reviewed the findings and confirmed resolution. Prototype: `prototype/farmhand_mount_prototype.py` (launcher: official `mcp` 1.28.1, FastMCP with `streamable_http_path="/"`, mounted at `/mcp` on port 8099, two async tools reading/mutating `HaystackState` via ambient DI) + `prototype/client_check.py` (SDK's own streamable-HTTP client + httpx probes). One command each.

**Confirmed (success criteria all met):**

1. **MCP session over the mount works**: initialize (protocol 2025-11-25), `tools/list`, both tool calls, against the running studio.
2. **socket.io coexistence** — the one unverifiable-by-reading item from ticket 02: Engine.IO handshake on NiceGUI's real path (`/_nicegui_ws/socket.io/`) returns 200 before and after MCP traffic; `GET /` healthy throughout. No interference observed in either direction.
3. **Loop affinity as designed**: async tools execute on `MainThread` with the running event loop — the tickets-05/06 model holds. Corollary for the spec: the SDK thread-offloads *sync* tool functions, so `FarmhandTool.run` must be async (ticket 05 already mandates this; now empirically load-bearing).
4. **Mutation end-to-end**: `haystack_create_graph` → `create_new()` → visible in next read; `GraphDataMutated` broadcast ran without error.
5. **Capability quirk confirmed empirically**: server advertised `tools.listChanged: false` (FastMCP wrapper default) — validating ticket 04's low-level `NotificationOptions` mandate.

**Discovery (the prototype's payoff — the research recipe was wrong for NiceGUI):** the documented AsyncExitStack lifespan shape (enter `session_manager.run()` in `app.on_startup`, `aclose()` in `app.on_shutdown`) **crashes shutdown** with `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in` — NiceGUI runs each handler in its own task, and the session manager's anyio task group must be entered and exited in the SAME task. **Mandated spec pattern: a single long-lived runner task** that itself enters `session_manager.run()`, sets a started-event, waits on a stop-event, and exits the context in place; `on_startup` spawns it and awaits started; `on_shutdown` sets stop and awaits the task. Proven: clean "Application shutdown complete" on run 2.

Side effects disclosed: workspace `new_counter` advanced by the test creates (in-memory graphs died with the process); `mcp==1.28.1` left installed in the venv (the exact spec pin).
