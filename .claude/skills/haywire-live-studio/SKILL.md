---
name: haywire-live-studio
description: >
  Use when you need to drive a RUNNING Haywire studio from the CLI — inspect or
  mutate live graphs, list/read/call Farmhand MCP tools, check the error ledger,
  scaffold or hot-reload components, or verify a change in the real app rather
  than in tests. Bypasses Claude Code's own MCP client (which only connects at
  session start and is awkward to reconnect mid-session) by talking to the
  studio's /mcp endpoint over HTTP. Trigger on: "start the studio and use
  farmhand", "call a studio/MCP tool", "access the running studio", "list open
  graphs", "add a node via MCP", "check the error ledger", "the farmhand MCP
  server", or any task that needs the live studio instead of the test suite.
---

# haywire-live-studio

## Overview

The studio serves both the NiceGUI app and the **Farmhand MCP server** on
`http://127.0.0.1:8082` (`/mcp`). This skill bundles two dependency-free CLIs so
you (or a future session) can bring that server up/down and drive its tools over
HTTP — without depending on Claude Code's session-startup MCP handshake.

- `scripts/studioctl` — start / stop / status / restart the studio.
- `scripts/farmhand` — MCP client: `tools`, `call`, `resources`, `read`, `raw`.

**Why not the built-in MCP client?** Claude Code connects to configured MCP
servers only at session start. If the studio wasn't up then (or the config had
the wrong token), the tools never load and `/mcp reconnect` is often unavailable
mid-session. These CLIs sidestep that entirely: they read the token from disk
and speak MCP directly.

## When to use

- You need to see or change a **live** graph (open graphs, nodes, edges, run state).
- You want to call any Farmhand tool (`studio_*`, `haystack_*`, `graph_editor_*`,
  `marketplace_*`, `testing_*`) and read the JSON result.
- You're verifying a component change end-to-end: scaffold → write → hot-reload →
  `studio_verify_component` → `studio_get_errors`.
- The built-in `farmhand` MCP tools aren't loaded in this session.

Do **not** use for offline work the test suite covers — prefer `pytest` when you
don't need a live app.

## Quick reference

```sh
S=.claude/skills/haywire-live-studio/scripts

$S/studioctl start          # boot studio if down (idempotent), wait for :8082, print token
$S/studioctl status         # up? tracked pid? who owns the port?
$S/studioctl stop           # clean shutdown (SIGINT) of a studio studioctl started
$S/studioctl restart

$S/farmhand tools           # list 38 tools (name + one-line desc)
$S/farmhand tools --json    # full input schemas
$S/farmhand call studio_status
$S/farmhand call haystack_list_graphs
$S/farmhand call testing_echo '{"text": "hi"}'
echo '{"text":"hi"}' | $S/farmhand call testing_echo -   # args via stdin
$S/farmhand resources                       # list canon + library docs
$S/farmhand read farmhand://docs/canon/nodes
$S/farmhand raw tools/list                  # escape hatch: any MCP method
```

## Typical workflow

1. `studioctl start` — if it prints "already up … (your own instance)", a studio
   you launched is running; the tools work against it, and `stop` will refuse to
   kill it (see below).
2. `farmhand call <tool> '<json-args>'` — drive the studio. `call` **exits 2**
   when the tool returns an error (with `isError`), 0 on success, so you can
   branch on it.
3. Read `studio_get_errors` after any mutation/hot-reload to catch failures the
   result didn't surface.
4. `studioctl stop` when done (only if studioctl started it).

## Lifecycle discipline (won't stomp your GUI studio)

`studioctl` tracks only the studio **it** started, via `.haywire/studioctl.pid`.

- `start` is idempotent — reuses a studio already on `:8082`, never spawns a second.
- `stop` kills only the tracked pid. A studio you started yourself (terminal
  `uv run haywire`, or the desktop app) has no pid file here, so `stop` refuses
  and tells you to pass `--force` (which kills whatever holds `:8082`).
- `stop` escalates SIGINT → SIGTERM → SIGKILL. SIGINT is the studio's designed
  shutdown (`run()` catches `KeyboardInterrupt`), so it's clean and fast (~0.5s).

## Gotchas (learned the hard way)

- **Trailing slash is mandatory.** The endpoint is `/mcp/`. A bare `POST /mcp`
  307-redirects to `/mcp/`, and most POST clients drop the body on redirect. The
  `farmhand` script always uses `/mcp/`; if you ever hand-roll a `curl`, do too.
- **Token lives at `.haywire/farmhand_token`.** It's stable across restarts
  (`ensure_token` reuses the file; delete it to rotate). `farmhand` reads it
  automatically — never paste it into a header by hand.
- **The `<token>` placeholder bug.** `claude mcp add … "Bearer <token>"` stores
  the literal `<token>` if not substituted, causing 401 "not authenticated".
  These CLIs avoid the issue by not using Claude's MCP client at all.
- **Startup logs → `.haywire/studioctl.log`.** If `start` times out, it tails
  this file. Harmless `anyio.EndOfStream` ASGI errors from NiceGUI's own routes
  can appear at startup and are unrelated to Farmhand.
- **Each `farmhand` call is a fresh MCP session** (initialize →
  notifications/initialized → method). Stateless by design; no session to manage.

## Files

- `scripts/studioctl` — run with `--help` for flags (`start --timeout`, `stop --force`).
- `scripts/farmhand` — run with `--help`; subcommands each take `--help` too.
