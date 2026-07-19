# Process & transport model

Type: grilling
Status: resolved
Blocked by: 01, 02
Resolved: 2026-07-19

## Question

Where does the MCP server (**Farmhand**, per ticket 01's vocabulary decision) live and how do clients reach it?

Constraint from ticket 01: whether Farmhand ships as its own `haybale-farmhand` package (like the `haybale-marketplace` carve-out) or as a first-degree citizen of haywire (core/studio) is decided **here**, by the architectural complexity each option implies — the user is fine with either. This ticket therefore also owns the former fog entry "core vs studio placement". Note ticket 01 also fixed a framework-owned baseline of tools that must exist with zero contributing libraries — the placement answer must say where that baseline lives.

Options to stress-test with the user (informed by the SDK research in ticket 02):

- **In-process**: mounted on the studio's existing FastAPI/ASGI app (NiceGUI `app`, port 8082 or a dedicated port) over Streamable HTTP. Direct access to DI, registries, and `LibraryStateContainer`; MCP mutations ride the existing `GraphDataMutated` broadcasts so open browser sessions update live. MCP is only available while the studio runs.
- **Sidecar process**: separate MCP process talking to the studio over a new internal API. Cleaner lifecycle, but invents a second API surface and loses free state sharing.
- **Hybrid/headless**: an MCP host in haywire-core usable without the studio UI (the `HostStore.in_memory()` comment in app.py hints the engine already anticipates headless hosts).

Also settle: lifecycle (start with studio? toggleable via settings?), port/endpoint conventions, and whether the answer changes the core-vs-studio placement question in the map's fog. This is an architecture decision touching DI wiring — run with `/design` and confirm, never assume (CLAUDE.md rule).

Ticket 02's research (see its Answer + [assets/mcp-sdk-research.md](../assets/mcp-sdk-research.md)) materially frames this: it recommends in-process Streamable HTTP on official `mcp` v1.x with the parent-lifespan mount, notes stdio is structurally impossible for an embedded server, and flags a breaking MCP spec revision landing 2026-07-28 (build on v1.x now, re-evaluate fall 2026). Stress-test the decision against that recommendation rather than starting from a blank slate.

## Answer

Grilled 2026-07-19 via /design (code read first, assumptions confirmed) + /inquisition; all six forks user-confirmed:

1. **In-process.** Farmhand mounts on the studio's existing FastAPI app (the pattern `register_code_intelligence_endpoints()` already establishes at `app.py:48-49`). Tools resolve `HaystackState`/`LibraryManager`/etc. from the ambient DI context exactly like `AppState.on_enable` hooks do; Farmhand emits the cross-session signals core mutators leave to callers (inventory gap 5); loop-sensitive operations marshal onto the NiceGUI loop (inventory gap 7). No sidecar (would require inventing the RPC surface inventory gap 6 says doesn't exist); no file-format read fallback in v1 (single code path; offline reads are a clean v2 door since the file formats are documented).
2. **Packaging: host in haywire-studio, contribution seam in haywire-core.** Studio owns the transport mount, parent-lifespan wiring, live-session registry, `list_changed` notification plumbing, the framework-baseline tools, and the `mcp` dependency. Core owns only the SDK-free contribution mechanism libraries import (exact shape = ticket 05). The optional `haybale-farmhand` packaging is **ruled out** by the complexity criterion from ticket 01: the transport's run-once lifespan can't follow library disable, runtime install couldn't mount it, and baseline tools must exist on a bare studio. Farmhand is a first-degree citizen of haywire.
3. **Lifecycle: FrameworkSettings flag, enabled by default, read once at startup.** Workspace/global tiers apply (a workspace can opt out). Changing it takes effect on restart — no runtime transport start/stop (run-once constraint).
4. **Endpoint: studio's own port, mounted at `/mcp`.** SDK internal path set to `/` with the full prefix in the mount (avoids the documented 307-redirect trap). No SSE endpoint (deprecated in spec and Claude Code). Client one-liner: `claude mcp add --transport http farmhand http://127.0.0.1:8082/mcp`. Studio port hardcoding (`app.py:240`) is a separate, out-of-effort concern Farmhand simply inherits.
5. **Stack: official `mcp` SDK v1.x**, pinned `mcp>=1.28,<2` in haywire-studio; protocol 2025-11-25; low-level `NotificationOptions(tools_changed=True, prompts_changed=True, resources_changed=True)` so `listChanged` is advertised correctly rather than relying on unverified client leniency; re-evaluate SDK v2 + the 2026-07-28 spec revision ~fall 2026 (spec carries this as a version-strategy note).

Map updates: testing-strategy fog graduated into new ticket 10 (blocked by 05); glossary Farmhand entry updated with the settled packaging.
