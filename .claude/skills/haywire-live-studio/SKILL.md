---
name: haywire-live-studio
description: >
  Use when you need to drive a RUNNING Haywire studio — start/stop it, then
  inspect or mutate live graphs, call Farmhand MCP tools, check the error
  ledger, scaffold or hot-reload components, or verify a change in the real
  app rather than in tests. Trigger on: "start the studio and use farmhand",
  "call a studio/MCP tool", "access the running studio", "list open graphs",
  "add a node via MCP", "check the error ledger", "the farmhand MCP server",
  "live check", "post a questionnaire", "ask the user to test in the studio",
  or any task that needs the live studio instead of the test suite.
---

# haywire-live-studio

## Overview

The studio serves both the NiceGUI app and the **Farmhand MCP server** on
`http://127.0.0.1:<port>/mcp/` (port defaults to 8124, `NetworkSettings.port`).
The **farmhand proxy** as an MCP server for Claude Code — it bridges stdio to that HTTP endpoint, so studio tools (`haybale-studio_*`, `haybale-haystack_*`, `haybale-graph-editor_*`, `haybale-marketplace_*`, `haybale-testing_*`) appear directly in this session once the studio is up, with no reconnect needed.

The proxy bridges to a studio, it doesn't launch one — bring the studio itself
up/down with `scripts/studioctl`.

## When to use

- You need to see or change a **live** graph (open graphs, nodes, edges, run state).
- You want to call any Farmhand tool and read the result.
- You're verifying a component change end-to-end: scaffold → write → hot-reload →
  `haybale-studio_verify_component` → `haybale-studio_get_errors`.
- A finished change needs the user to confirm it in the studio: a live check, run as a
  Questionnaire (below). When one is due and where its Findings go: the
  `haywire-workflow` skill, *Live check*.

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
`haybale-studio_status`, `haybale-haystack_list_graphs`, `haybale-studio_get_errors`, etc.

## Typical workflow

1. `studioctl start` — if it prints "already up … (your own instance)", a studio
   you launched is running; `stop` will refuse to kill it (see below).
2. Call tools directly (e.g. `haybale-haystack_list_graphs`, `haybale-graph-editor_add_node`).
3. Read `haybale-studio_get_errors` after any mutation/hot-reload to catch failures the
   result didn't surface.
4. `studioctl stop` when done (only if studioctl started it).

## Live check with a Questionnaire

The user confirms; you post the Checks and read the answers. It costs the user's time:
post one only when your own checks (tests, Farmhand tools, an empty error ledger) leave
you confident everything works, and only with Checks that need a person. When one is due:
the `haywire-workflow` skill, *Live check*. Format, every element and the Findings
fields: [docs/reference/questionnaire.md](../../../docs/reference/questionnaire.md).

1. `studioctl start` from inside this worktree, so the user tests this branch's code.
2. `haybale-studio_post_questionnaire` with a title naming the change and one `check`
   per behaviour (`do`, `expect`, `isRequired: true`). A rejected post names the element
   and property to fix.
3. Tell the user it waits in the studio's aside, give the studio's URL
   (`http://127.0.0.1:<port>`, the port `studioctl status` prints), and wait for them
   to say they are done. Nothing tells you earlier.
4. `haybale-studio_get_findings`. `status: "open"` means not submitted yet: say so, or
   read the answers so far if the user asks. `failed_checks` lists the failed and
   blocked ones; their `note` says what the user saw.
5. `haybale-studio_get_errors` with `since_seq` = `ledger_seq.posted`: the errors logged
   while the user was checking.
6. Record the Findings where the workflow says. After a fix, ask the user before posting
   another round.

Traps:

- A post replaces the current Questionnaire and its Findings: record a round before you
  post the next. Earlier ones stay on disk only.
- Reading a submitted Questionnaire takes it out of the studio (`closed: "read"`);
  `closed: "discarded"` means the user threw it away, and its answers are partial.
- Keep a Check to one action and one observable result; a Check that needs a second
  look is two Checks. A `blocked` verdict usually means a Check depends on one that
  failed: say so in its `description`, or hide it with `visibleIf: "{earlier} = 'pass'"`.

## Lifecycle discipline (won't stomp your GUI studio)

`studioctl` tracks only the studio **it** started, via `.haywire/studioctl.pid`.

- The port is resolved in order: `.haywire/studio.json` (written by a studio
  the first time it runs in this folder), then `network.port.value` in
  `.haywire/settings.json` (a worktree's own port, written by
  `scripts/worktree_setup.py`), then 8124 — the main folder's studio.
- `start` is idempotent — reuses a studio already on the resolved port, never
  spawns a second, but only if that studio's process runs in this workspace
  (its `/proc/<pid>/cwd`). A studio of another folder on the port is refused
  with exit 1: `port N is held by the studio of <folder>; this workspace's port
  is N (<source>)`. Run `studioctl` from inside the worktree whose code you
  want to check, never point it at another folder's studio.
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
- **Token**: `/mcp` needs no `Authorization` header when `studio.json` has
  `auth_required: false`. When `true`, use a roster agent token — mint one
  with `haywire user add <name> --agent --tier edit`. If the project was
  scaffolded into a *subdirectory* of the open workspace, check
  `.haywire/studio.json` there too — the proxy checks one level down
  automatically, but a manual read doesn't.
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
`@going-haywire/farmhand@latest` on every session start).

## Files

- `scripts/studioctl` — run with `--help` for flags (`start --timeout`, `stop --force`).
