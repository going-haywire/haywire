---
name: haywire-live-studio
description: >
  Use when you need to drive a RUNNING Haywire studio — start/stop it, then
  inspect or mutate live graphs, call Farmhand MCP tools, check the error
  ledger, scaffold or hot-reload components, or verify a change in the real
  app rather than in tests. Trigger on: "start the studio and use farmhand",
  "call a studio/MCP tool", "access the running studio", "list open graphs",
  "add a node via MCP", "check the error ledger", "the farmhand MCP server",
  or any task that needs the live studio instead of the test suite.
---

# haywire-live-studio

## Overview

The studio serves both the NiceGUI app and the **Farmhand MCP server** on
`http://127.0.0.1:<port>/mcp/` (port defaults to 8124, `NetworkSettings.port`).
This repo's [.mcp.json](../../../.mcp.json) registers the **farmhand4claude
proxy** as an MCP server for Claude Code — it bridges stdio to that HTTP
endpoint, so studio tools (`studio_*`, `haystack_*`, `graph_editor_*`,
`marketplace_*`, `testing_*`) appear directly in this session once the studio
is up, with no reconnect needed.

The proxy bridges to a studio, it doesn't launch one — bring the studio itself
up/down with `scripts/studioctl`.

## When to use

- You need to see or change a **live** graph (open graphs, nodes, edges, run state).
- You want to call any Farmhand tool and read the result.
- You're verifying a component change end-to-end: scaffold → write → hot-reload →
  `studio_verify_component` → `studio_get_errors`.

Do **not** use for offline work the test suite covers — prefer `pytest` when you
don't need a live app.

## Quick reference

```sh
S=.claude/skills/haywire-live-studio/scripts

$S/studioctl start          # boot studio if down (idempotent), wait for its port
$S/studioctl status         # up? tracked pid? who owns the port?
$S/studioctl stop           # clean shutdown (SIGINT) of a studio studioctl started
$S/studioctl restart
```

Once the studio is up, call its tools directly by name in this session —
`studio_status`, `haystack_list_graphs`, `studio_get_errors`, etc.

## Typical workflow

1. `studioctl start` — if it prints "already up … (your own instance)", a studio
   you launched is running; `stop` will refuse to kill it (see below).
2. Call tools directly (e.g. `haystack_list_graphs`, `graph_editor_add_node`).
3. Read `studio_get_errors` after any mutation/hot-reload to catch failures the
   result didn't surface.
4. `studioctl stop` when done (only if studioctl started it).

## Lifecycle discipline (won't stomp your GUI studio)

`studioctl` tracks only the studio **it** started, via `.haywire/studioctl.pid`.

- `start` is idempotent — reuses a studio already on the resolved port, never
  spawns a second.
- `stop` kills only the tracked pid. A studio you started yourself (terminal
  `uv run haywire`, or the desktop app) has no pid file here, so `stop` refuses
  and tells you to pass `--force` (which kills whatever holds the port).
- `stop` escalates SIGINT → SIGTERM → SIGKILL. SIGINT is the studio's designed
  shutdown (`run()` catches `KeyboardInterrupt`), so it's clean and fast (~0.5s).

## Two always-available proxy tools

These are answered by the proxy itself (not forwarded), so they work even
before the studio is up:

- `farmhand_studio_status` — is the studio reachable? Reports which
  URL/token it resolved and where from (env override, sidecar file, or
  default guess), and distinguishes "nothing there" from "found it, but the
  token is wrong" (401).
- `farmhand_studio_connect` — point the proxy at a studio in a *different*
  workspace/project that automatic discovery can't find (pass `port`, and
  `token` if required). Takes effect immediately, session-only, not persisted.

## Troubleshooting

If `farmhand_studio_status` reports the studio unreachable or unauthorized,
these are the same facts a manual `farmhand_studio_connect` call needs:

- **Port**: `.haywire/studio.json` in the project root — a JSON sidecar the
  studio writes on startup (`pid`, `port`, `url`, …). Written only when
  `farmhand.enabled`.
- **Token**: `.haywire/farmhand_token` in the project root — a plain-text
  bearer token, stable across restarts (delete the file to rotate it). If
  the project was scaffolded into a *subdirectory* of the open workspace,
  check there too — the proxy checks one level down automatically, but a
  manual read doesn't.
- **Trailing slash is mandatory** if you ever hand-roll a request outside the
  proxy: the endpoint is `/mcp/`. A bare `POST /mcp` 307-redirects, and most
  POST clients drop the body on redirect.
- **`<token>` placeholder bug**: if a token was ever pasted into a header
  literally as `<token>` instead of substituted, you'll see 401
  "not authenticated" — re-read the actual file contents, don't reuse a
  half-remembered value.

If `farmhand_studio_status` isn't available at all, the MCP server itself
didn't start — check `.mcp.json` is present at the repo root and that `npx`
can reach the npm registry (the proxy is fetched as
`@going-haywire/farmhand4claude@latest` on every session start).

## Files

- `scripts/studioctl` — run with `--help` for flags (`start --timeout`, `stop --force`).
