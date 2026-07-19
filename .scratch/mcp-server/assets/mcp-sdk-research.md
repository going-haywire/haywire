# MCP Python Server Ecosystem — Research for Farmhand

**Researched:** 2026-07-18. All versions and dates below were checked against primary sources on this date unless noted otherwise. Every claim carries an inline citation to the doc page, repo file (pinned to a tag), or spec section that owns it. Items that could not be verified from a primary source are marked **UNVERIFIED**.

---

## TL;DR

- **Official SDK:** `mcp` **1.28.1** (released 2026-06-26, Python ≥3.10, MIT). **v1.x is the only stable line.** A **v2 pre-release line** (`2.0.0aN`/`2.0.0bN`) exists on `main`; the README says outright "Do not use v2 in production" and instructs dependents to pin `mcp>=1.27,<2`. Stable v2 targets **2026-07-27**, alongside the next spec revision. ([PyPI](https://pypi.org/pypi/mcp/json), [README](https://github.com/modelcontextprotocol/python-sdk/blob/main/README.md))
- **FastMCP:** now **3.4.4** (2026-07-09), moved from `jlowin/fastmcp` to **`PrefectHQ/fastmcp`** at 3.0 (stable 2026-02-18). FastMCP 3 still runs on the official `mcp` package underneath (`mcp>=1.24,<2.0` via `fastmcp-slim` extras). FastMCP 2.x's last release was 2.14.7 (2026-04-13); no formal 2.x maintenance policy is published (**UNVERIFIED**). ([PyPI fastmcp](https://pypi.org/pypi/fastmcp/json), [PyPI fastmcp-slim](https://pypi.org/pypi/fastmcp-slim/json), [v3.0.0 release](https://github.com/PrefectHQ/fastmcp/releases/tag/v3.0.0))
- **Spec:** current protocol revision is **2025-11-25**. A **major, breaking revision "2026-07-28"** (stateless core, initialize handshake removed, `Mcp-Session-Id` removed, extensions framework) ships **ten days from now**; its RC locked 2026-05-21. Old HTTP+SSE transport is deprecated; stdio + Streamable HTTP are the two standard transports. ([Versioning](https://modelcontextprotocol.io/specification/versioning), [2026-07-28 RC](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/), [Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports))
- **Clients:** Claude Code natively supports **HTTP (streamable-http)**, stdio, WebSocket, and (deprecated) SSE; it explicitly supports **`list_changed` notifications for tools/prompts/resources**, resources via `@` mentions, and prompts as slash commands. Claude Desktop reaches **remote** MCP via cloud-hosted connectors (cannot reach `localhost`) and **local** servers only via stdio (`claude_desktop_config.json` / `.mcpb` extensions) — so `mcp-remote` (v0.1.38, alive) is still the bridge for Desktop → local HTTP. ([Claude Code MCP docs](https://code.claude.com/docs/en/mcp), [Custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp), [Local servers quickstart](https://modelcontextprotocol.io/docs/develop/connect-local-servers))
- **Dynamic tools:** official SDK v1 `FastMCP` has `add_tool()`/`remove_tool()` but **does not send `notifications/tools/list_changed` automatically and advertises `listChanged: false`** (open issue [#710](https://github.com/modelcontextprotocol/python-sdk/issues/710)); you must call `session.send_tool_list_changed()` per live session yourself. FastMCP 3 sends the notification **automatically**, but per its docs only "within an active MCP request context" — a hot-reload event outside a request still needs manual handling.
- **Auth:** spec authorization is **OPTIONAL**; full OAuth 2.1 machinery applies to HTTP servers that opt in. For a loopback single-user server, the spec's hard requirements are transport-security ones: **MUST validate `Origin`**, **SHOULD bind 127.0.0.1**, SHOULD authenticate. A static bearer token via Claude Code's `--header` is the pragmatic middle ground. ([Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization), [Transports §Security](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports))
- **Pin for a project starting now:** `mcp>=1.28,<2` (the SDK README itself tells you to add the `<2` bound), or `fastmcp>=3.4,<4` if choosing FastMCP. Protocol on the wire: negotiate 2025-11-25; plan a revisit ~Q4 2026 once SDK v2 + the 2026-07-28 spec settle in clients.

---

## 1. Official `mcp` Python SDK vs FastMCP

### Official SDK (`mcp`, modelcontextprotocol/python-sdk)

- **Latest stable: 1.28.1**, uploaded 2026-06-26. Requires **Python ≥3.10**. MIT license. Recent cadence: 1.27.0 (2026-04-02), 1.27.1 (2026-05-08), 1.27.2 (2026-05-29), 1.28.0 (2026-06-16). Checked 2026-07-18. ([PyPI JSON](https://pypi.org/pypi/mcp/json))
- **v1 docs** live at <https://py.sdk.modelcontextprotocol.io/> (sections: Building Servers, Writing Clients, Protocol Features, Low-Level Server, Authorization, Testing). v1 source lives on the [`v1.x` branch](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x); `main` is v2.
- **v2 status** (quoting [README on `main`](https://github.com/modelcontextprotocol/python-sdk/blob/main/README.md), checked 2026-07-18):
  > "This README documents v2 of the MCP Python SDK — a pre-release (alpha/beta) line under active development. **Do not use v2 in production.** Pre-releases are published to PyPI as `2.0.0aN` / `2.0.0bN`, and each pre-release may contain breaking changes from the previous one."
  >
  > "**v1.x is the only stable release line and remains recommended for production.** It … continues to receive critical bug fixes and security patches … **If your package depends on `mcp`, add a `<2` upper bound to your version constraint (for example `mcp>=1.27,<2`) before the stable release lands.**"
  >
  > "v2 is a major rework of the SDK, both to support the [2026-07-28 MCP specification release] and to fix long-standing architectural issues. … Stable v2 is targeted for 2026-07-27, alongside the spec release."
  Tags `v2.0.0a1`…`v2.0.0b2` exist on the repo (verified via `gh api repos/modelcontextprotocol/python-sdk/tags`, 2026-07-18).

### FastMCP (PrefectHQ/fastmcp, gofastmcp.com)

- **Latest: 3.4.4**, released 2026-07-09. Requires **Python ≥3.10**. Apache-2.0. First stable 3.0 on **2026-02-18**. Checked 2026-07-18. ([PyPI history](https://pypi.org/project/fastmcp/#history), [PyPI JSON](https://pypi.org/pypi/fastmcp/json))
- **Packaging changed in 3.x:** the `fastmcp` PyPI package is now a thin meta-package depending on `fastmcp-slim[client,server]==<same version>`; the `client`, `server`, and `mcp` extras of `fastmcp-slim` all carry the constraint **`mcp>=1.24,<2.0`** — i.e. **FastMCP 3 still builds on the official SDK v1 line** for the protocol/transport layer. ([fastmcp-slim PyPI JSON](https://pypi.org/pypi/fastmcp-slim/json))
- **Governance:** at 3.0 "FastMCP moves from jlowin/fastmcp to PrefectHQ/fastmcp. GitHub forwards all links, PyPI is the same, imports are the same." ([v3.0.0 release notes](https://github.com/PrefectHQ/fastmcp/releases/tag/v3.0.0))
- **Relationship history:** "FastMCP 1.0 proved the concept so well that Anthropic made it the foundation of the official MCP SDK" — the `FastMCP` class inside the official SDK (`mcp.server.fastmcp`) is that donated 1.0 lineage; FastMCP 2.x continued independently and 3.0 is its successor with a provider/transform architecture, hot reload in dev, OpenAPI/FastAPI generation, proxying, and a large auth-provider suite. Surface API "largely unchanged — `@mcp.tool()` still works exactly as before." ([Introducing FastMCP 3.0](https://jlowin.dev/blog/fastmcp-3), [What's new](https://jlowin.dev/blog/fastmcp-3-whats-new), [upgrade guide](https://gofastmcp.com/development/upgrade-guide))
- **FastMCP 2.x maintenance:** last 2.x release was **2.14.7 on 2026-04-13** (PyPI JSON, checked 2026-07-18). Neither the 3.0 release notes nor the upgrade guide state a formal 2.x support window — **UNVERIFIED** (no primary-source policy found). Treat 2.x as effectively frozen.

### Which to build on for an embedded server

Both support mounting into an existing ASGI app (see §2). Differences that matter for Farmhand are in §4 (dynamic tools) and the dependency-weight/stability trade-off summarized in the Recommendations section.

---

## 2. Mounting Streamable HTTP into an existing FastAPI/Starlette app

### Official SDK v1 — supported pattern

The SDK docs ("Building Servers" → mounting) give exactly this shape ([py.sdk server docs](https://py.sdk.modelcontextprotocol.io/server/), checked 2026-07-18):

```python
import contextlib
from starlette.applications import Starlette
from starlette.routing import Mount

mcp = FastMCP("My App")          # mcp.server.fastmcp.FastMCP

@contextlib.asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield

app = Starlette(
    routes=[Mount("/", app=mcp.streamable_http_app())],
    lifespan=lifespan,
)
```

For FastAPI, identical: `FastAPI(lifespan=lifespan)` + `app.mount("/mcp", mcp.streamable_http_app())`. Multiple servers: set each `sub.settings.streamable_http_path = "/"`, mount each under its own prefix, and enter every `session_manager.run()` in one lifespan via `contextlib.AsyncExitStack` ([py.sdk server docs](https://py.sdk.modelcontextprotocol.io/server/); same pattern confirmed by maintainers in [python-sdk#713](https://github.com/modelcontextprotocol/python-sdk/issues/713)).

**Why the lifespan wiring is mandatory (source-level):**

- `streamable_http_app()` builds a `Starlette` app whose own lifespan is `lambda app: self.session_manager.run()` ([fastmcp/server.py L1041-L1046 @ v1.28.1](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/fastmcp/server.py#L1041-L1046)). **Starlette does not run a mounted sub-app's lifespan**, so when you `Mount(...)` it inside another app, nothing starts the session manager unless the *parent* lifespan does.
- `StreamableHTTPSessionManager.run()` creates the task group all sessions run in; `handle_request()` raises `RuntimeError("Task group is not initialized. Make sure to use run().")` if it never ran ([streamable_http_manager.py L102, L159-L160 @ v1.28.1](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/streamable_http_manager.py#L102)).
- `run()` may be called **only once per instance** — a second call raises (`_has_started` guard, [L121-L126](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/streamable_http_manager.py#L121-L126)). Relevant to Haywire hot-reload: don't tear down/re-enter the manager; keep one manager for the process lifetime and change the *tool set*, not the transport.
- The `session_manager` property exists precisely "to enable advanced use cases like mounting multiple FastMCP servers in a single FastAPI application" and raises if accessed before `streamable_http_app()` has been called ([fastmcp/server.py L261 @ v1.28.1](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/fastmcp/server.py#L261)).

**Known pitfalls (primary-source issue tracker):**

- "Mounting a Streamable HTTP MCP endpoint on existing FastAPI app does not work" — the canonical symptom of missing lifespan wiring / "Task group is not initialized": [python-sdk#1367](https://github.com/modelcontextprotocol/python-sdk/issues/1367).
- Multiple mounted servers, only the one whose `session_manager.run()` was wired works: [python-sdk#713](https://github.com/modelcontextprotocol/python-sdk/issues/713) (fix: `AsyncExitStack` lifespan, above).
- Redirect (307) behavior for the mounted path (trailing-slash mismatch between mount path and `streamable_http_path`): [python-sdk#951](https://github.com/modelcontextprotocol/python-sdk/issues/951). Mitigation: set `settings.streamable_http_path = "/"` on the sub-app and put the whole path in the `Mount` prefix.
- `stateless_http=True` and `json_response=True` settings exist for stateless / plain-JSON deployments ([py.sdk server docs](https://py.sdk.modelcontextprotocol.io/server/)); statefulness is the default.

### FastMCP 3 — supported pattern

Same shape, different method name: `mcp.http_app(path="/mcp")` returns a Starlette app; default endpoint `/mcp/`. The docs are explicit ([deployment/http](https://gofastmcp.com/deployment/http), checked 2026-07-18):

> "you **must** pass the lifespan context from the FastMCP app to the resulting Starlette app, as nested lifespans are not recognized. Otherwise, the FastMCP server's session manager will not be properly initialized."

```python
mcp_app = mcp.http_app(path="/")
api = FastAPI(lifespan=mcp_app.lifespan)
api.mount("/mcp", mcp_app)
```

FastMCP 3 exposes `stateless_http=True` (also via `FASTMCP_STATELESS_HTTP=true`) for multi-worker/load-balanced deployments, warns that MCP clients don't honor sticky-session cookies ("Most MCP clients—including Cursor and Claude Code—use `fetch()` internally and don't properly forward `Set-Cookie` headers"), and notes nginx needs `proxy_buffering off` for the SSE response streams ([deployment/http](https://gofastmcp.com/deployment/http), [integrations/fastapi](https://gofastmcp.com/integrations/fastapi)). Composing an externally supplied lifespan with FastMCP's own was a tracked pain point: [fastmcp#1026](https://github.com/PrefectHQ/fastmcp/issues/1026).

### Co-hosting with NiceGUI / socket.io / uvicorn

- **No documented conflict found** between an MCP Streamable HTTP mount and python-socketio/engineio sharing the same FastAPI app under uvicorn — searches of the python-sdk and fastmcp issue trackers surfaced only the generic lifespan issues above (checked 2026-07-18). Absence of reports is not proof of absence; treat as low-risk but prototype it.
- NiceGUI's own docs confirm the app runs on Uvicorn ("you can directly provide your certificates to Uvicorn, which NiceGUI is based on") and that NiceGUI supports running inside "a custom FastAPI app … very flexible deployments as described in the FastAPI documentation" ([NiceGUI configuration & deployment](https://nicegui.io/documentation/section_configuration_deployment)).
- Engineering note (not from a primary source — verify in a prototype): NiceGUI constructs its FastAPI `app` at import time, so you can't pass `lifespan=` at construction. The equivalent wiring is an `AsyncExitStack` entered from a startup hook and closed on shutdown (`await stack.enter_async_context(mcp.session_manager.run())`), or wrapping `app.router.lifespan_context`. The session-manager-run-once constraint (above) means this must happen exactly once per process.
- The MCP mount lives on its own path (e.g. `/mcp`); NiceGUI's socket.io traffic uses its own path (`/_nicegui_ws/` by default) — path-level separation is the whole integration story at the HTTP layer.

---

## 3. stdio vs Streamable HTTP — client conventions in 2026

### Spec position

- The 2025-11-25 spec defines exactly two standard transports: **stdio** and **Streamable HTTP**. "Clients **SHOULD** support stdio whenever possible." ([Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports))
- Streamable HTTP "replaces the HTTP+SSE transport from protocol version 2024-11-05"; the old transport is explicitly labeled **deprecated**, with a backwards-compatibility recipe for clients/servers that must still interop ([Transports §Backwards Compatibility](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)). Note SSE-the-encoding still exists *inside* Streamable HTTP (server may answer a POST with an SSE stream); it's the standalone HTTP+SSE transport that is deprecated.
- The upcoming 2026-07-28 revision reworks Streamable HTTP further: protocol-level sessions and the `Mcp-Session-Id` header are **removed** (SEP-2567), the `initialize` handshake is **removed** (SEP-2575), and persistent server→client SSE push is being replaced by multi-round-trip requests (SEP-2322) ([2026-07-28 RC post](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)).

### Claude Code (checked 2026-07-18, [code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp))

- **HTTP is the recommended transport for remote servers**: `claude mcp add --transport http <name> <url>`; in JSON config `"type": "http"` with `streamable-http` accepted as an alias. Static headers via `--header "Authorization: Bearer …"`.
- **SSE transport carries an explicit deprecation warning**: "The SSE (Server-Sent Events) transport is deprecated. Use HTTP servers instead, where available."
- **stdio** (`claude mcp add … -- <command>`) and **WebSocket** (`"type": "ws"`, config-only) are also supported.
- HTTP/SSE servers get automatic reconnection with exponential backoff; stdio servers are not auto-reconnected.
- Claude Code answers `roots/list` and sends `notifications/roots/list_changed` (v2.1.203+).

### Claude Desktop

- **Remote servers** = "custom connectors": "Claude connects to your remote MCP server **from Anthropic's cloud infrastructure**, rather than from your local device, across every Claude client including claude.ai, Claude Desktop, Cowork, and the mobile apps. Your MCP server must be reachable over the public internet." → **a `localhost` HTTP server is not reachable via connectors** ([support article 11175166](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)).
- **Local servers** on Desktop are launched as subprocesses via `claude_desktop_config.json` (`"command"`/`"args"` — stdio) ([MCP quickstart: Connect to local MCP servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers)), or via one-click **desktop extensions (`.mcpb` packages)**, positioned as the modern local mechanism ([support article 10949351](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)). I found no primary-source evidence that Desktop's local config accepts an HTTP `url` entry — **UNVERIFIED either way**; assume stdio-only for local.
- Consequence: **the stdio→HTTP bridge pattern is still needed for Claude Desktop → local HTTP servers.** `mcp-remote` is alive (v0.1.38, "Remote proxy for Model Context Protocol, allowing local-only clients to connect to remote servers using oAuth", no deprecation notice; [npm registry](https://registry.npmjs.org/mcp-remote/latest), checked 2026-07-18). For Claude Code the bridge is unnecessary — native HTTP is first-class.

---

## 4. Dynamic tool registration/removal at runtime (load-bearing)

### What the spec requires

A server that changes its tool list should declare the `tools.listChanged: true` capability and send `notifications/tools/list_changed` when the set changes; same pattern for resources and prompts ([spec: Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools), same in 2025-11-25).

### Official SDK v1.28.1 — APIs exist, notifications are manual, capability flag is wrong by default

- **APIs:** `FastMCP.add_tool(fn, name=…, …)` ([fastmcp/server.py L397](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/fastmcp/server.py#L397)) and `FastMCP.remove_tool(name)` (raises `ToolError` if absent; [L435](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/fastmcp/server.py#L435), backed by `ToolManager.add_tool`/`remove_tool` [tools/tool_manager.py L45, L75](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/fastmcp/tools/tool_manager.py#L45)). Both are plain dict mutations — callable at any time, from any task.
- **No automatic notification:** neither method touches any session. The notification primitive is per-session: `ServerSession.send_tool_list_changed()` / `send_resource_list_changed()` / `send_prompt_list_changed()` ([server/session.py L485-L493](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/session.py#L485-L493)). The v1 server docs show the sanctioned usage *inside a request*: `await ctx.session.send_tool_list_changed()` ([py.sdk server docs](https://py.sdk.modelcontextprotocol.io/server/)).
- **Capability advertisement bug/quirk:** the low-level server derives `tools: {listChanged}` from `NotificationOptions`, which defaults to `False` for tools/resources/prompts ([lowlevel/server.py L112-L121 and get_capabilities L193-L217](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/lowlevel/server.py#L112)). The `FastMCP` wrapper and the Streamable HTTP session manager both call `create_initialization_options()` **without** notification options ([streamable_http_manager.py L197-L200, L299-L302](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/streamable_http_manager.py#L197-L200); `run_stdio_async` likewise, [fastmcp/server.py](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/fastmcp/server.py)), so an official-SDK FastMCP server **advertises `listChanged: false`** even though you can and may send the notifications. Only low-level-server users can pass `NotificationOptions(tools_changed=True)`.
- **Open issue:** "how to trigger a resources_changed or listChanged" — [python-sdk#710](https://github.com/modelcontextprotocol/python-sdk/issues/710), still **open** (P2, enhancement, FastMCP-v2 milestone) as of 2026-07-18. This is the canonical tracking issue for automatic list-changed emission in the official SDK.
- **Broadcasting outside a request:** there is no public "all active sessions" registry on `StreamableHTTPSessionManager` (sessions live in a private dict). To notify on a hot-reload event you must track live `ServerSession` objects yourself (e.g., capture `ctx.session` per request, or maintain a registry keyed by session id) and call `send_tool_list_changed()` on each. Notifications reach HTTP clients over the standalone GET/SSE stream of the Streamable HTTP transport ([Transports §Listening for Messages](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)).

### FastMCP 3.4.x — automatic, but scoped to active request contexts

- **APIs:** `mcp.add_tool(tool)`, `mcp.local_provider.remove_tool("name")`, plus visibility control `mcp.enable(keys={"tool:…"}) / mcp.disable(tags={…})` and per-session `ctx.enable_components()/ctx.disable_components()` ([servers/tools](https://gofastmcp.com/servers/tools), [servers/visibility](https://gofastmcp.com/servers/visibility), checked 2026-07-18). Tool **transformations** (rename/reshape/curate without touching originals) are a separate first-class feature ([transforms](https://gofastmcp.com/servers/transforms/tool-transformation)).
- **Notifications:** "FastMCP automatically sends `notifications/tools/list_changed` notifications to connected clients when tools are added, removed, enabled, or disabled" and "This happens automatically. You don't need to trigger notifications manually" ([servers/tools](https://gofastmcp.com/servers/tools), [servers/visibility](https://gofastmcp.com/servers/visibility)).
- **The caveat that matters for Farmhand:** "Notifications are only sent when these operations occur **within an active MCP request context** (e.g., when called from within a tool or other MCP operation)" ([servers/tools](https://gofastmcp.com/servers/tools)); session-scoped visibility changes "go only to the affected session" ([servers/visibility](https://gofastmcp.com/servers/visibility)). A haybale-library hot-reload fires from Haywire's own event loop, *not* from inside an MCP request — in that path FastMCP's automatic mechanism does not fire, and you're back to needing a session-tracking/notification strategy of your own (or nudging clients only on their next request).
- Client-side, FastMCP documents `list_changed` handling in its client library ([clients/notifications](https://gofastmcp.com/clients/notifications)) — useful for integration tests of Farmhand's notification behavior.

### Client support for `list_changed`

Claude Code: "Claude Code supports MCP `list_changed` notifications, allowing MCP servers to dynamically update their available tools, prompts, and resources without requiring you to disconnect and reconnect. When an MCP server sends a `list_changed` notification, Claude Code automatically refreshes the available capabilities from that server." ([Claude Code MCP docs §Dynamic tool updates](https://code.claude.com/docs/en/mcp)). Whether Claude Code honors the notification from a server that advertised `listChanged: false` is not documented — **UNVERIFIED** (given the official SDK's default above, empirically many servers advertise `false` and clients appear lenient, but do not rely on this: prefer a stack that advertises the capability correctly, i.e. low-level `NotificationOptions(tools_changed=True)` or FastMCP 3).

---

## 5. Auth for local HTTP MCP servers

### What the spec says (2025-11-25, checked 2026-07-18)

- "**Authorization is OPTIONAL for MCP implementations.** When supported: implementations using an HTTP-based transport **SHOULD** conform to this specification. Implementations using an STDIO transport **SHOULD NOT** follow this specification, and instead retrieve credentials from the environment." ([Authorization §Protocol Requirements](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization))
- When implemented, the stack is OAuth 2.1 (draft-ietf-oauth-v2-1-13) + RFC 9728 Protected Resource Metadata (MUST, for discovery) + RFC 8414/OIDC discovery (MUST provide one) + Client ID Metadata Documents (SHOULD) + RFC 7591 dynamic client registration (MAY, "included for backwards compatibility") + RFC 8707 resource indicators (client MUST send) + PKCE (client MUST). Bearer tokens go in the `Authorization` header on **every** request, never in query strings. ([Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization))
- The 2026-07-28 revision adds "authorization hardening" on top of this model but does not replace it ([RC post](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)).

### Transport-security requirements that apply to Farmhand regardless of auth

From the Streamable HTTP security warning ([Transports §Security Warning](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)):

1. "Servers **MUST** validate the `Origin` header on all incoming connections to prevent DNS rebinding attacks" (respond 403 to invalid Origins);
2. "When running locally, servers **SHOULD** bind only to localhost (127.0.0.1) rather than all network interfaces (0.0.0.0)";
3. "Servers **SHOULD** implement proper authentication for all connections."

The official SDK ships this as `TransportSecuritySettings` (`allowed_hosts`, `allowed_origins`) enforced by `TransportSecurityMiddleware` — **but when no settings are passed, DNS-rebinding protection is disabled by default** "for backwards compatibility" ([transport_security.py @ v1.28.1](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/transport_security.py)); `streamable_http_app()` forwards `settings.transport_security` into the transport ([fastmcp/server.py L956-L962](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/fastmcp/server.py#L950)). **Farmhand must set this explicitly.**

### What clients actually do for localhost servers

- Claude Code supports full OAuth 2.0 for remote HTTP servers (`/mcp` login flow, `claude mcp login`, RFC 9728/8414 discovery, CIMD, pre-registered credentials, pinned scopes) **and** plain static headers: `claude mcp add --transport http … --header "Authorization: Bearer <token>"`, plus `headersHelper` for dynamically generated headers ([Claude Code MCP docs §Authenticate](https://code.claude.com/docs/en/mcp)). Nothing in the docs requires auth for a localhost URL — an unauthenticated `http://127.0.0.1:…/mcp` server is accepted.
- Lighter options, in increasing order of effort: **no auth on loopback** (spec-permissible: auth is OPTIONAL; Origin validation + 127.0.0.1 binding still required/strongly recommended) → **static bearer token** checked by middleware, delivered via `--header` (Claude Code) or `Authorization` config — for Farmhand this is the sweet spot: a per-install random token printed/managed by the studio → **full OAuth 2.1** (overkill for a single trusted local user; FastMCP 3 ships providers if ever needed, [servers/auth](https://gofastmcp.com/servers/auth/authentication)).

---

## 6. Resources and prompts

### Server-side support

- **Official SDK v1:** first-class — `@mcp.resource()` (incl. URI templates for resource templates), `@mcp.prompt()`, documented under "Building Servers"; low-level server exposes the corresponding request handlers; per-session `send_resource_list_changed()` / `send_prompt_list_changed()` exist ([py.sdk docs](https://py.sdk.modelcontextprotocol.io/server/), [session.py L485/L493](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/session.py#L485)). Capability advertisement has the same `listChanged: false` default quirk as tools (§4).
- **FastMCP 3:** first-class — resources, resource templates, prompts, with the same automatic `ResourceListChangedNotification`/`PromptListChangedNotification` behavior (and the same request-context caveat) ([servers/resources](https://gofastmcp.com/servers/resources), [servers/prompts](https://gofastmcp.com/servers/prompts), [servers/visibility](https://gofastmcp.com/servers/visibility)).

### Client-side surfacing (checked 2026-07-18)

- **Claude Code — yes, both.** Resources: "MCP servers can expose resources that you can reference using @ mentions … Type `@` in your prompt to see available resources from all connected MCP servers"; format `@server:protocol://resource/path`; "Resources are automatically fetched and included as attachments"; Claude also gets list/read tools for resources. Prompts: "MCP servers can expose prompts that become available as commands … `/mcp__servername__promptname`", with space-separated arguments. `list_changed` refresh applies to tools, prompts, *and* resources. ([Claude Code MCP docs §Use MCP resources / §Use MCP prompts as commands / §Dynamic tool updates](https://code.claude.com/docs/en/mcp))
- **Claude Desktop:** the current support articles describe connectors/extensions in terms of *tools* (with approval flows); I found no current primary documentation of resource-browsing or prompt-slash-command UX in Desktop — **UNVERIFIED**; do not design Farmhand features that depend on Desktop surfacing resources/prompts.
- Note for roadmap awareness: the 2026-07-28 spec deprecates **Roots, Sampling, and Logging** (SEP-2577) — *not* resources or prompts ([RC post](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)).

---

## 7. Version pinning guidance

### Protocol revisions

- Current: **2025-11-25** ("The current protocol version is 2025-11-25", [Versioning](https://modelcontextprotocol.io/specification/versioning), checked 2026-07-18). Prior finals: 2024-11-05, 2025-03-26, 2025-06-18.
- Next: **2026-07-28**, final publication 2026-07-28 (RC locked 2026-05-21); the largest revision since launch, with breaking changes (stateless core; `initialize` handshake removed SEP-2575; `Mcp-Session-Id` removed SEP-2567; extensions SEP-2133; new deprecation policy SEP-2596 with ≥12-month windows). "Tier 1 SDKs are expected to ship support within this window." ([RC post](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/))

### How the Python SDK negotiates versions

- v1.28.1 constants: `LATEST_PROTOCOL_VERSION = "2025-11-25"`; `SUPPORTED_PROTOCOL_VERSIONS = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"]`; HTTP requests without an `MCP-Protocol-Version` header are assumed to be `DEFAULT_NEGOTIATED_VERSION = "2025-03-26"` per spec. ([types.py L27/L35](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/types.py#L27), [shared/version.py](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/shared/version.py), spec [Transports §Protocol Version Header](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports))
- Negotiation happens during `initialize`; client and server "MUST agree on a single version to use for the session" ([Versioning §Negotiation](https://modelcontextprotocol.io/specification/versioning)). The server picks the best mutually supported revision, so a v1.x server keeps working with clients speaking any of the four supported revisions.

### Stability statements & concrete pins

- The SDK's own guidance: **`mcp>=1.27,<2`** — "If your package depends on `mcp`, add a `<2` upper bound … before the stable release lands"; v1.x "continues to receive critical bug fixes and security patches" ([README](https://github.com/modelcontextprotocol/python-sdk/blob/main/README.md)). v2 pre-releases explicitly break between pre-releases.
- **Recommendation for a project starting now (2026-07):**
  - Official SDK: `mcp>=1.28,<2` (1.28.1 current).
  - FastMCP (if chosen): `fastmcp>=3.4,<4` (3.4.4 current; 3.0 release notes: "a major version is a major version").
  - Do **not** build on `mcp` 2.0.0aN/bN now; re-evaluate ~1–2 months after v2 stable (target 2026-07-27) once the 2026-07-28 spec, SDK v2, FastMCP (which currently pins `mcp<2.0`), and the Claude clients have all converged. The 12-month deprecation policy (SEP-2596) means v1/2025-11-25 servers won't be stranded overnight.

---

## Recommendations for Farmhand

1. **Transport: Streamable HTTP, mounted at `/mcp` inside the studio's existing FastAPI/NiceGUI app; loopback-only.** stdio is structurally impossible for an *embedded* server (the client must spawn the server as its subprocess — [Transports §stdio](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) — but Farmhand lives inside the running studio). Claude Code connects natively: `claude mcp add --transport http farmhand http://127.0.0.1:<port>/mcp` ([Claude Code MCP docs](https://code.claude.com/docs/en/mcp)). Don't build an SSE-transport endpoint (deprecated in spec and Claude Code).

2. **SDK: official `mcp` v1.x (`mcp>=1.28,<2`) as the base; treat FastMCP 3 as the alternative if you want its extras.** Rationale: (a) Farmhand's load-bearing requirement — notifying clients after a *hot-reload event outside any MCP request* — is not solved out-of-the-box by either stack (§4), so FastMCP's headline advantage (automatic list_changed) doesn't actually cover the main trigger; (b) the official SDK is the smaller, canonical dependency with a clear v1→v2 story, while FastMCP 3 is a fast-moving major (3.0 → 3.4.4 in five months) that adds a provider/transform architecture Farmhand doesn't need; (c) both mount into ASGI the same way. Choose FastMCP 3 instead if you want its auth providers, proxying, or per-session visibility filtering (`ctx.disable_components`) as product features.

3. **Dynamic tools: own the notification path explicitly.**
   - Advertise the capability correctly: with the official SDK, drop to the low-level entry point for initialization options (`NotificationOptions(tools_changed=True, prompts_changed=True, resources_changed=True)` — [lowlevel/server.py](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/lowlevel/server.py#L112)); don't rely on clients tolerating `listChanged: false` (**unverified** leniency, §4).
   - Maintain a Farmhand-owned registry of live `ServerSession`s (populate on first request per session / prune on disconnect), and on haybale enable/disable/install/uninstall/hot-reload: mutate the tool set via `add_tool`/`remove_tool`, then `await session.send_tool_list_changed()` for each live session ([session.py L489](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/session.py#L489)). Notifications ride the standalone GET/SSE stream, which Claude Code holds open and reacts to ([§Dynamic tool updates](https://code.claude.com/docs/en/mcp)).
   - Keep **one** `FastMCP`/session-manager instance for the process lifetime (run-once constraint, §2); hot-reload changes the tool registry, never the transport.

4. **Lifespan wiring in NiceGUI:** enter `mcp.session_manager.run()` exactly once via an `AsyncExitStack` from the app's startup hook and close it on shutdown (§2). This is the single most common mounting failure mode ([#1367](https://github.com/modelcontextprotocol/python-sdk/issues/1367), [#713](https://github.com/modelcontextprotocol/python-sdk/issues/713)). Set `settings.streamable_http_path = "/"` and put the full prefix in the mount to avoid the 307-redirect trap ([#951](https://github.com/modelcontextprotocol/python-sdk/issues/951)). Prototype the socket.io co-existence early; no conflicts are documented, but none of this is covered by tests anywhere upstream.

5. **Security posture for a single trusted local user:** bind 127.0.0.1; **explicitly configure** `TransportSecuritySettings(allowed_hosts=["127.0.0.1:<port>", "localhost:<port>"], allowed_origins=[...])` since the SDK disables DNS-rebinding protection when unset (§5); add a lightweight static bearer-token check (random per-install token, surfaced in the studio UI, consumed via Claude Code's `--header`). Skip OAuth 2.1 — spec-optional and disproportionate here (§5).

6. **Claude Desktop path (if needed):** don't target it directly in v1 of Farmhand. Custom connectors can't reach localhost (cloud-side egress, §3); the supported bridge is a stdio entry (`claude_desktop_config.json` or a `.mcpb` extension) running `mcp-remote http://127.0.0.1:<port>/mcp` (alive at 0.1.38, §3) — a cheap follow-up once the HTTP server exists.

7. **Resources & prompts:** worth exposing for Claude Code (graph inspection docs as resources → `@farmhand:…` mentions; canned workflows as prompts → `/mcp__farmhand__…` commands), using the same session-registry notification path for their `list_changed` events. Don't gate any Desktop functionality on them (§6).

8. **Version strategy:** pin `mcp>=1.28,<2` now; negotiate protocol 2025-11-25. Put a calendar marker ~Sept/Oct 2026 to re-evaluate SDK v2 (stable target 2026-07-27) and the 2026-07-28 spec once Claude Code/Desktop advertise support — the removal of `Mcp-Session-Id` and the initialize handshake (§3, §7) will eventually change the session-registry design in (3), and the SDK v2 migration guide ([py.sdk v2 migration](https://py.sdk.modelcontextprotocol.io/v2/migration/)) is the doc to read then.

---

## UNVERIFIED / open items (flagged, not guessed)

- **FastMCP 2.x maintenance policy** — no primary-source statement; last 2.x release 2.14.7 (2026-04-13).
- **Client behavior when `listChanged: false` is advertised but notifications are sent anyway** — not documented for Claude Code or Desktop.
- **Claude Desktop local config accepting HTTP `url` entries** — no primary source shows it; quickstart shows stdio `command`/`args` only.
- **Claude Desktop surfacing of MCP resources/prompts** — not documented in current support articles.
- **socket.io / MCP-mount co-hosting conflicts** — no reports found in either issue tracker; needs a prototype, not more reading.
- **Exact FastMCP 3 internal mechanism for list_changed emission** — behavior cited from official docs ([servers/tools](https://gofastmcp.com/servers/tools), [servers/visibility](https://gofastmcp.com/servers/visibility)); the emission code path in `fastmcp-slim` was not traced line-by-line.
