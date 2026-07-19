# MCP Python SDK capabilities research

Type: research
Status: resolved
Blocked by: —
Resolved: 2026-07-18
Asset: [assets/mcp-sdk-research.md](../assets/mcp-sdk-research.md)

## Question

What does the current MCP Python ecosystem support, concretely, for the shapes Haywire needs? Produce a markdown summary (linked asset in this directory) answering:

- Official `mcp` Python SDK vs FastMCP (v2): current versions, maintenance status, which to build on.
- Mounting a **Streamable HTTP** MCP server into an *existing* FastAPI/ASGI app (NiceGUI's `app` object) — supported patterns, lifespan integration, and any known conflicts with NiceGUI's socket.io/uvicorn setup.
- stdio transport in a long-running server context: is there a sane pattern for a stdio sidecar proxying to a running HTTP studio (e.g. `mcp-remote`), or is HTTP-native the norm for clients like Claude Code / Claude Desktop now?
- **Dynamic tool registration/removal at runtime** — API for adding/removing tools after server start, and support for `notifications/tools/list_changed`. This is load-bearing: Haywire libraries enable/disable/hot-reload at runtime.
- Auth options for local HTTP MCP servers (tokens, localhost-binding conventions, OAuth requirements in the spec vs practice).
- Resources and prompts support (for exposing library docs / graph files as MCP resources).
- Version pinning guidance and protocol-revision compatibility notes.

## Answer

Full report with per-claim citations: [assets/mcp-sdk-research.md](../assets/mcp-sdk-research.md) (all facts verified against primary sources 2026-07-18). Headlines:

- **SDK choice**: build on the official `mcp` SDK v1.x — current 1.28.1, pin `mcp>=1.28,<2`. FastMCP now means PrefectHQ/fastmcp 3.4.4 (a fast-moving major); it remains the documented alternative. SDK v2 is pre-release ("do not use in production"), stable targeted 2026-07-27.
- **Timing caution**: a **breaking MCP spec revision lands 2026-07-28** (stateless core, initialize handshake and `Mcp-Session-Id` removed). Recommendation: build on v1.x + protocol 2025-11-25 now, re-evaluate ~Sept/Oct 2026. Old HTTP+SSE transport is deprecated — don't build an SSE endpoint.
- **Mounting**: both stacks mount Streamable HTTP into an existing FastAPI/Starlette app; the one mandatory trick is running the session manager from the *parent* app's lifespan (mounted sub-app lifespans never run; run-once constraint; canonical failure "Task group is not initialized"). No documented socket.io conflicts — explicitly a prototype question (ticket 09).
- **Dynamic tools (the load-bearing one)**: `add_tool`/`remove_tool` exist and are callable any time, but **no stack auto-notifies on Haywire's hot-reload path**. Official SDK sends nothing automatically and even advertises `listChanged: false` unless you use low-level `NotificationOptions`; FastMCP 3 auto-notifies only from inside an active MCP request context. **Farmhand must own a live-session registry and call `send_tool_list_changed()` per session itself.** Claude Code documents honoring these notifications. Direct constraint on ticket 05's mechanism design.
- **Clients**: Claude Code speaks Streamable HTTP natively (recommended path). Claude Desktop custom connectors run from Anthropic's cloud and **cannot reach localhost** — Desktop support means a stdio `mcp-remote` bridge, recommended as a post-v1 follow-up.
- **Auth for a trusted-local-user server**: spec auth is OPTIONAL; the hard requirements are 127.0.0.1 binding + Origin validation. The SDK's DNS-rebinding protection is **disabled by default when `TransportSecuritySettings` is unset** — must be configured explicitly. Pragmatic layer: static per-install bearer token via Claude Code's `--header`. Skip OAuth 2.1. Feeds ticket 06.
- **Resources & prompts**: fully supported server-side with the same manual list_changed caveat; Claude Code surfaces resources as `@` mentions and prompts as `/mcp__…` commands — worth exposing (feeds ticket 07); Desktop surfacing undocumented — gate nothing on it.

Six UNVERIFIED items are flagged at the end of the report — most notably socket.io co-hosting (no reports either way; ticket 09's job) and client leniency toward `listChanged: false`.
