---
name: studio-authentication
description: One watertight no-access/access boundary at a pure-ASGI gate, with view/edit/admin tiers inside it that guard against ignorance rather than malice — because an edit principal can author a Python node
status: accepted
level: architectural
---

# Studio authentication

The studio has no notion of who is using it. `expose_to_network` and the peer
allowlist (ADR 0026) decide *from where* the studio can be reached; nothing
decides *who* is reaching it. This adds that, off by default.

## The boundary, and the thing that is not a boundary

**There is exactly one watertight line: `no-access` vs `access`.** Everything
behind it — `view`, `edit`, `admin` — is a guard against ignorance, not
against malice.

This is not modesty about the implementation; it follows from what the product
is. A graph executes arbitrary Python in-process. A principal who can add a
node can therefore read `~/.haywire/auth.json`, rewrite the hashes, reach into
`SessionContext`, or do anything else the studio process can do. So `edit` is
already `admin` at the machine level, and any design that spent effort
enforcing `edit < admin` as a containment boundary would be spending it on a
wall with no building attached.

What the tiers *do* buy is real and worth building: a `view` principal cannot
mutate anything, because every mutating path is server-side and every
affordance that reaches one is hidden. During a live show, that is the property
that matters — the wrong click cannot happen because the control is not there.

The corollary is that the front door carries all the weight, and it has to have
no side entrances.

## One gate, two credentials

`AuthGateMiddleware` is a **pure-ASGI callable** on the root app, installed in
`HaywireApp.run()` beside `_install_ip_allowlist`. It admits a request carrying
either a valid signed cookie (browser) or a valid bearer token (agent), and
rejects everything else on both `http` and `websocket` scopes.

Pure-ASGI for the reason ADR 0026 gives at length: `BaseHTTPMiddleware` never
sees `scope["type"] == "websocket"`, and NiceGUI's entire UI runs over
Socket.IO at `/_nicegui_ws/`. A gate built on it would guard the login page and
let the whole application through underneath.

**Accepting both credentials at one gate, rather than exempting `/mcp`**, is
what keeps the line single. `/mcp` is mounted inside the same ASGI app
(`FarmhandHost.mount()` → `nicegui_app.mount("/mcp", …)`), so a root-level
wrapper covers it whether or not that is intended. Exempting it would make the
boundary's correctness depend on `FarmhandSettings.require_auth` staying
`True` — a settings flag as a security control. Under the combined gate, that
flag becomes an optimization: `BearerTokenMiddleware` stays mounted beneath as
defence in depth, and neither guard's failure is fatal alone.

The token the gate matches is the **roster's**, not the workspace
`farmhand_token` file. Those are two credentials with two lifetimes, and only
one of them carries a tier. With authentication off, `ensure_token()` and
`<workspace>/.haywire/farmhand_token` behave exactly as before, so existing
agent configurations are untouched. With it on, the roster is authoritative —
and `haywire auth enable` offers to import an existing workspace token as an
agent principal, so a working Farmhand setup survives the flip instead of going
dark at the moment authentication is switched on.

## The unauthenticated surface is two routes, and neither is NiceGUI

`GET /login` and `POST /login` are **plain FastAPI routes returning
self-contained HTML** — no `ui.page`, no `hui`, no theme tokens, no external
assets.

This looks like a gratuitous deviation from the rest of the studio's UI, and it
is load-bearing. A NiceGUI login page runs its submit handler *server-side over
the websocket*, so unauthenticated clients would need `/_nicegui_ws/` open in
order to log in — the exact transport carrying the entire application. The
exemption would swallow the gate. Because the login page is plain HTTP, the
unauthenticated surface is exactly those two routes; `/_nicegui_ws/`, every
`/_nicegui/<version>/*` asset route, and `/api/code-intel/*` all stay behind
the gate.

The login page is therefore the one place in the codebase that hardcodes colour
values instead of using `--hw-*` tokens, because none of that machinery exists
before the socket connects.

## The cookie carries identity; it never carries authority

The signed cookie holds a principal name, an issued-at, and an expiry. It does
**not** hold a tier. The tier — and the principal's continued existence — is
read from the roster at the moment it is used, through an mtime-cached read.

This is what makes "remove a principal" an actual revocation rather than a
request. Had the cookie carried the tier, a removed principal would keep full
access until expiry and a demoted admin would stay admin until re-login: the
roster UI would have a Remove button that does not remove, which is worse than
having none, because it reads as a control.

Because a WebSocket is **one ASGI scope**, the gate runs once per connection at
the handshake, not per frame. That makes the check free, and it means an open
socket is never re-examined. Revocation therefore reaches live sessions by
push: removing a principal walks `SessionManager.active_sessions`, matches on
`ctx.principal`, and evicts those clients. Demotion needs no push at all —
`ctx.can_edit()` reads live authority, so the next action already sees it, and
the surfaces stop rendering on the next redraw. There is no polling, no timer,
and nothing wrapping `receive`.

The only uncovered case is hand-editing the roster on a running studio, which
resolves when that client reconnects. That is an admin editing a file by hand
instead of using the UI that exists, and it was not worth a per-frame hook on
the canvas hot path to catch.

## Layering: vocabulary in core, mechanism in studio, UI in a library

- **`haywire.core.access`** — the `AccessTier` enum, `SessionContext.principal`,
  and `can_view()` / `can_edit()` / `can_admin()` / `can_access(tier)`. No
  files, no crypto, no ASGI. Core must own the vocabulary because
  `@panel(access=…)` and `@editor(access=…)` are core decorators; a studio-owned
  enum would make core import studio.
- **`haywire_studio.auth`** — roster I/O, scrypt, cookie signing, the gate, the
  login routes, the `haywire user` / `haywire auth` CLI.
- **`haybale-studio`** — the `RosterEditor` and the account menu.

**The gate is app-owned and never library-owned.** Libraries are disableable,
hot-reloadable, and installable from a marketplace; a library that owned the
gate could be disabled to open the door.

Core resolves to `admin` for everybody when auth is disabled, so existing
loopback installs are unchanged.

## `access=` lives on three identities, not on `BaseIdentity`

`PanelIdentity`, `EditorIdentity` and `FarmhandIdentity` carry `access`. Nodes,
skins, widgets, themes and adapters do not, and this is deliberate rather than
an omission to be tidied up later.

A component identity governs whether the component appears in an authoring
surface. For a panel, editor or Farmhand tool, that *is* the capability — hide
the identity and the capability is gone. For a node it is not: the identity
governs the Add Nodes menu, while the node instances already sitting in a
`.graph` file execute regardless of who is watching. `@node(access=admin)`
would look like a restriction and restrict nothing.

Enforcement sits at the seams every consumer already funnels through:

| Surface | Seam |
| --- | --- |
| Panels (properties, context menus, selection toolbar) | `visible_panels()` filters; `render_panel()` refuses |
| Editors | `Slot._accessible_bindings()` plus an admission check in `add_binding()` / `populate_from_snapshot()` |
| Farmhand tools | `list_tools` filters; `call_tool` re-checks |

The slot needs both admission and render checks because they close different
doors: a render-only filter leaves the binding in `_bindings`, where
`to_snapshot()` would persist it into the principal's `workspace_state.json`
and `reveal()` could still activate it via `find_binding()`.

A denied surface **vanishes** — it is never rendered disabled. A greyed-out
control is still something to click and wonder about during the one moment
nobody can debug it. The StatusBar carries a passive identity label so the
absence is explained once, globally, instead of per control.

## Users and agents are both principals

The roster does not distinguish "people" from "machines" at the model level.
A **User Principal** authenticates with a password and receives a cookie; an
**Agent Principal** authenticates with a bearer token and may be scoped to one
workspace. Both carry one `AccessTier`. One roster answers "who can reach this
studio" completely.

Tiers are enforced *more* strongly on the agent side, which is initially
counter-intuitive. An agent's surface is an **enumerated API**: a `view` agent
never receives the write tools from `list_tools`, so it is not being asked to
restrain itself — the surface is absent, and `call_tool` re-checks for a client
holding a cached list. There is no equivalent for a browser principal, whose
`edit` tier includes a Python node. So for agents, `view` is a genuine
containment boundary; for browsers it is a boundary against mutation but not
against the machine.

A tool's tier is declared, not derived from `ToolAnnotations.read_only_hint`.
Those are orthogonal axes: `read_only_hint` describes *behaviour* and is
addressed to the client for confirmation prompts, while `access` is *policy*
set by the operator. Deriving one from the other would mean an author tuning a
UX hint silently changed who can see the tool.

Agent tokens are stored in plaintext while passwords are hashed. The asymmetry
is deliberate: passwords are hashed because humans reuse them, so a leaked
roster must not compromise unrelated services. A 256-bit token exists nowhere
but this studio, so hashing it would protect nothing beyond a machine that is
already lost — while costing the ability to re-copy the connection command.

## The roster is one document, and enabling it requires proving you can get in

`~/.haywire/auth.json` (`0600`) holds the enabled flag, every principal, and
the auth tunables. Not a settings bag, and not split across files.

**One document, so "auth is enabled" and "an admin exists" cannot disagree.**
Split across two files they are independently editable, so `enabled: true` with
an empty roster is a reachable state that every guard against it is a check
someone must remember to write and keep working. As fields of one document
validated on one write path, the state does not exist.

Not a settings bag because the UI writes the **workspace tier**
(`<workspace>/.haywire/settings.json`), a per-project file that travels with
the project into git and onto other machines. Session lifetime is
machine-and-operator policy, not project data. The global tier avoids that but
is hand-edit-only, so an `AuthSettings` bag would render fields in the settings
UI that silently do nothing when edited.

`haywire auth enable` prompts for an admin username and password and verifies
them before writing the flag. Anyone who can run that command can also edit the
JSON, so this is not a barrier against an attacker — it is a **proof of
recoverability**. It makes the realistic failure unreachable: turning on
authentication with a roster whose passwords nobody remembers, on a machine
whose UI is now the only way to fix it.

Auth is read once at startup; enabling or disabling requires a restart.

## Consequences

- **Off by default, and orthogonal to `expose_to_network`.** Existing loopback
  installs are unchanged; existing LAN deployments relying on the peer
  allowlist keep working. Startup logs a WARNING when the studio is exposed
  with auth off. Coupling the two — or refusing to start — would break a
  configuration ADR 0026 endorses, and would turn an upgrade into a lockout
  whose fix requires the UI it just took away.
- **Credentials are sniffable over plain HTTP.** A replayed cookie is a valid
  cookie and the gate cannot tell. `NetworkSettings.ssl_certfile` /
  `ssl_keyfile` pass through `ui.run(**kwargs)` to uvicorn (NiceGUI recognises
  both explicitly and builds the `https://` auto-open URL), so TLS is a
  configuration choice rather than an unavailable one. Setting exactly one of
  the pair refuses to start. The `Secure` cookie flag follows actual TLS
  presence, never unconditional, or the cookie breaks on loopback.
  `FarmhandHost.mount()` must build its `allowed_origins` with the matching
  scheme, or `/mcp` rejects its own origin under TLS.
- **Zero new dependencies.** `hashlib.scrypt` (≈36 ms) for passwords, `hmac` +
  `secrets.compare_digest` for the cookie. The signer must sign the entire
  payload including the expiry and validate it from the signed payload — never
  from the cookie's client-controlled `Max-Age` — and encode unambiguously
  (base64url JSON, not delimiter-joined fields). Rotating the secret is the
  "log everyone out" lever.
- **No account lockout.** A fixed 1 s delay on failure, and always hashing even
  for unknown usernames so timing does not enumerate the roster. Lockout is a
  self-denial-of-service vector: anyone who can reach `/login` could lock out
  the admin trying to fix a show.
- **Presence is displayed, never managed.** TopBar chips per connected
  principal, driven by a `PresenceChanged` cross-session signal. Agents show
  *last seen*, stamped in the gate on every `/mcp` request — MCP's `ping` is an
  optional protocol message, so a binary indicator could be wrong while a
  relative timestamp cannot. There is no kill-session UI.

## Explicit non-goals

No password reset, email verification, or self-service recovery — the CLI is
the recovery path. No per-graph, per-node or per-file permissions. No audit
log. No SSO/OAuth/LDAP. No sandboxing. No protection of files on disk. No
account lockout. No tier enforcement inside node code: a graph runs at its own
authority, not the viewer's.

**And no multi-tenancy.** A `view` principal does not get a filtered copy of
the studio — they see the same live graphs, the same running execution and the
same haystack as everyone else, and simply cannot mutate them. "These users see
only these graphs" is a different and far larger feature, and nothing here is a
step toward it.

## Alternatives considered

**`app.storage.user` plus the documented NiceGUI auth pattern.** Rejected: it
is `BaseHTTPMiddleware`-based, so it gates the page load and not the socket.
The gate also verifies its own cookie rather than reading `app.storage.user`,
which is served by Starlette's `SessionMiddleware` *inside* the NiceGUI app —
a root-level wrapper runs outside it and would re-implement the unsealing
anyway, while acquiring an ordering dependency on NiceGUI internals.

**Snapshotting the tier onto the session at login.** Rejected — it puts
authority where it can go stale, and makes demotion a disruptive eviction
rather than a quiet change of what renders.

**Periodic re-validation** (a `receive` wrapper, or a per-session timer).
Rejected: the only case it uniquely catches is a hand-edited roster on a
running studio, and the gate-level form is a Python call per websocket frame on
the canvas hot path.

**`bcrypt` / `argon2-cffi`.** Rejected: a compiled dependency on every install
of a wheel distributed through the marketplace, for a hash that is not holding
the boundary.

**A separate `haybale-auth` library for the roster UI.** Rejected: an editor
with a user list does not earn a package in the lockstep release, a pyproject,
entry points and generated docs. `access=admin` already hides it.

**Merging the agent token into the global roster unscoped.** Rejected: the
Farmhand token is workspace-scoped today, and folding it in unscoped would
silently promote one project's agent credential into a machine-wide key.

## References

- ADR 0026 — studio network exposure (bind address, peer allowlist, jedi confinement)
- `docs/reference/glossary.md` — Access & Authentication vocabulary
- `packages/haywire-studio/src/haywire_studio/network/ip_filter.py` — the pure-ASGI precedent
- `packages/haywire-studio/src/haywire_studio/farmhand/auth.py` — `BearerTokenMiddleware`
- `packages/haywire-core/src/haywire/ui/panel/host_rendering.py` — `visible_panels()`, the single panel gate
