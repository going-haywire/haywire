---
name: studio-network-exposure
description: The studio defaults to loopback-only; opening it to the network layers a bind-address switch, a pure-ASGI peer-IP allowlist, and jedi path confinement — each closing a distinct hole the others don't
status: accepted
level: architectural
---

# Studio network exposure

`ui.run()` in `HaywireApp.run()` used to pass no `host`, so NiceGUI bound
`0.0.0.0` — the studio was reachable from the LAN with no socket-level guard
at all. Reachable on that port: the full graph editor (arbitrary Python
execution, by design), `/mcp` (guarded by `require_auth` and
`restrict_to_loopback`), and three unauthenticated jedi endpoints
(`/api/code-intel/{complete,info,hover}`) that accepted a caller-controlled
filesystem path. `farmhand/auth.py` already documented Farmhand as "Layered
with 127.0.0.1 binding" — a layer that had never existed. This change
supplies it.

**Framing, stated plainly:** Haywire is a single-operator workbench. Everyone
who reaches it is a full operator; a graph executes arbitrary Python
in-process. These controls govern *who gets in*, never *what they may do*.

## The layered model

Two independent controls, both in `NetworkSettings`
(`packages/haywire-studio/src/haywire_studio/network/settings.py`):

1. **Bind address** (`expose_to_network`, default `False`) — `HaywireApp.run()`
   picks `host = "0.0.0.0" if settings.expose_to_network else "127.0.0.1"`.
   The OS refuses off-box connections unless this is explicitly flipped.
2. **Peer allowlist** (`allowed_remote_ranges`, default `""`) — a CIDR filter
   on the real TCP peer, enforced by `IPAllowlistMiddleware`, installed only
   when `expose_to_network` is on.

The bind address alone is not enough because it is binary: once flipped, the
studio is reachable from *any* address on *any* attached network, with no way
to scope it to "just my other machine" or "just the office subnet." A
Farmhand agent, a colleague's laptop, and an unrelated device on the same
Wi-Fi are equally reachable. The allowlist is the only knob that discriminates
between them once the socket is open — bind address decides *whether* the
studio is reachable beyond loopback at all, the allowlist decides *from
where*.

## Pure-ASGI over `BaseHTTPMiddleware` — the Socket.IO hole

This is the headline, and the reason a future "simplify this" pass could
silently reopen the gap.

NiceGUI runs its entire UI over Socket.IO, mounted at `/_nicegui_ws/` with
`cors_allowed_origins='*'`. Socket.IO negotiates its handshake over HTTP
polling, then upgrades to a WebSocket. Every button click, graph edit, and
node execution in the studio travels over that WebSocket after the initial
page load — the page load itself is a small fraction of the traffic.

Starlette's `BaseHTTPMiddleware` only sees ASGI scopes where
`scope["type"] == "http"`. It has no hook for `scope["type"] ==
"websocket"` at all. A filter built on `BaseHTTPMiddleware` would correctly
block (or allow) the *initial page load*, then let every subsequent
WebSocket frame — i.e. the entire live application — through completely
unfiltered, for any peer that happened to load the page once (or opened the
socket directly, skipping the page load entirely).

`IPAllowlistMiddleware`
(`packages/haywire-studio/src/haywire_studio/network/ip_filter.py`) is
instead a **pure-ASGI callable**: a plain class with `__call__(self, scope,
receive, send)`, handling `http`, `websocket`, and `lifespan` scopes itself,
with no Starlette middleware base class in the hierarchy. `lifespan` passes
through untouched; `http` and `websocket` both run the same peer check before
either reaches the wrapped app. This mirrors the existing
`BearerTokenMiddleware` in `farmhand/auth.py`, which is itself pure-ASGI for
the same reason (though it wraps only the `/mcp` sub-app, not the whole
process — see below).

**If you are reading this because you're about to rewrite
`IPAllowlistMiddleware` as a `BaseHTTPMiddleware` subclass to "simplify" it:
don't.** The `http`-only code path would keep working in manual testing
(the page still loads) while every WebSocket frame — the actual UI — sails
through unfiltered. The bug is invisible in a browser and invisible in a
casual `curl` check against `/`; it only shows up as "the allowlist doesn't
actually block anyone."

## Three guards, three threat models

Three distinct checks exist across this feature and Farmhand, and none is
redundant because each answers a question the others cannot:

| Guard | Enforces on | Signal | Forgeable? |
| ----- | ----------- | ------ | ---------- |
| `IPAllowlistMiddleware` (peer IP) | every HTTP/WS request when `expose_to_network` is on | TCP peer address (`scope["client"]`) | No — the kernel supplies it |
| `restrict_to_loopback` (Host/Origin) | `/mcp` only, via `TransportSecuritySettings` | `Host`/`Origin` **headers** | Yes — client-supplied |
| `require_auth` (bearer token) | `/mcp` only, via `BearerTokenMiddleware` | `Authorization: Bearer <token>` | Only by possessing the token |

Peer IP is the strongest signal available at the ASGI layer: it comes from
the OS socket, not from anything the client sends, so it cannot be spoofed
by a browser or a `curl` invocation. Its weakness is granularity — it says
*where the request came from*, nothing about *who* or *whether they should
be trusted*, and it says nothing at all when `expose_to_network` is off,
because the middleware isn't installed.

`Host`/`Origin` headers are the opposite: trivially forgeable by any HTTP
client, but they are exactly what a **browser** sets honestly during a
same-origin request, which is the one thing DNS-rebinding attacks exploit.
`restrict_to_loopback` is not a network-location check and does not claim to
be — it defeats the specific attack where a malicious page in the victim's
own browser resolves an attacker DNS name to `127.0.0.1` after the fact and
tries to talk to the local MCP server as if it were same-origin. **It does
not stop `curl`:** `curl -H 'Host: 127.0.0.1:8124' http://<lan-ip>:8124/mcp`
passes the check trivially, because the header check has no way to know the
`Host` value it received doesn't match how the request actually arrived.

The bearer token is the only one of the three that is an actual
authentication check — possession of a secret, not a claim about the
request's shape. It is the guard that actually carries the enforcement
weight on `/mcp`. `restrict_to_loopback` and `require_auth` are read a few
lines apart in `FarmhandHost.mount()`
(`packages/haywire-studio/src/haywire_studio/farmhand/host.py`) precisely
because they close different vectors: the token stops an attacker who can
reach `/mcp` at all; `restrict_to_loopback` stops a browser-based rebinding
attack that never needs a token because it rides the victim's own trusted
session.

None of the three is redundant: turn off the allowlist (leave
`expose_to_network` off) and the other two are moot because nothing off-box
can connect. Turn on network exposure without an allowlist entry and the
peer check still blocks everyone not listed. Reach `/mcp` specifically and
the token is still required regardless of what the peer IP or headers say.

## No `X-Forwarded-For` without `trusted_proxies`

`IPAllowlistMiddleware` never trusts `X-Forwarded-For` unconditionally.
`_resolve_client()` only consults it when the *direct TCP peer* is itself
inside `trusted_proxies`; if `trusted_proxies` is empty, XFF is never read
and the raw peer IP is used. An unconditionally honoured XFF would make the
allowlist decorative: any client can set that header to any value, so if it
were trusted by default, a rejected peer could simply claim to be
`127.0.0.1` or any allowed address and walk straight through.

When a proxy *is* trusted, the resolution is rightmost-untrusted: XFF
entries are appended left-to-right as a request hops through proxies (the
leftmost entry is the first hop's claim about itself, which is
attacker-controlled — anyone can set that header before it ever reaches the
first real proxy). Scanning from the right and skipping entries that are
themselves listed in `trusted_proxies` finds the first hop the deployment
didn't put there itself — the most trustworthy signal available in a chain
that a client partially controls.

`HaywireApp._install_ip_allowlist` logs a one-line WARNING at startup when
`expose_to_network` is on and `trusted_proxies` is empty: behind a reverse
proxy in that configuration, every real client arrives from the proxy's own
peer address, so `allowed_remote_ranges` degenerates to "allow the proxy or
allow nothing."

## Loopback is outside the allowlist's jurisdiction

`allowed_remote_ranges` names *remote* machines. In `IPAllowlistMiddleware`,
a peer whose address `is_loopback` is allowed immediately, before any list
membership check runs, and this is not configurable — there is no way to
list `127.0.0.1`/`::1` in `allowed_remote_ranges` to have it mean anything
different, and no way to exclude loopback either. This makes self-lockout
structurally unreachable: `ui.run(show=True)` opens a local browser against
the studio the operator just started, and a filter that could reject that
connection would lock the operator out of the only UI that could fix the
misconfigured setting. An empty `allowed_remote_ranges` list means "no
further restriction beyond loopback," not "deny all" — with
`expose_to_network` on and no ranges configured, the practical effect is
loopback-only despite the wider bind, which is a safe default direction for
an unconfigured allowlist.

## jedi path confinement

`code_intelligence.py` registers three unauthenticated POST endpoints —
`/api/code-intel/complete`, `/info`, `/hover` — that each construct
`jedi.Script(body.get("code", ""), path=_confined_path(body.get("path")))`.
Before confinement, `path` went straight from the request body into
`jedi.Script`, and jedi resolves imports relative to it — a caller could walk
the filesystem by supplying arbitrary paths and reading back completions,
signatures, and docstrings (including, via the `name.description` fallback
for names jedi can't otherwise describe, literal source text such as a
module-level assignment's value).

`_confined_path()` resolves `Path(raw).resolve()` — collapsing `../`
traversal and symlinks — then accepts it only if it falls under one of the
allowed roots: the current workspace root (read fresh per call via
`get_workspace_root()`, falling back to sys.path-only roots if the workspace
isn't set up yet, e.g. during early import) plus every entry of
`sys.path`, resolved once at module import into `_SYS_PATH_ROOTS` since
`sys.path` doesn't change for the life of the interpreter. A path outside
those roots returns `None` rather than raising — `jedi.Script(code,
path=None)` still works, just without relative-import resolution — and all
three endpoints already wrap their body in `try`/`except Exception` and
return an empty payload on failure, so a rejected path degrades quietly
instead of 500ing. Rejections log at WARNING as the signal that someone is
probing.

**`code` is deliberately left unbounded**, and this is not an oversight.
jedi performs purely *static* analysis on `code` — no execution — and the
allowed roots are exactly what this interpreter could import anyway, so
confinement grants the caller no disclosure beyond importable-module
structure that any node running in the studio could already obtain by
importing the same modules. Restricting `code` itself would not remove a
capability an attacker doesn't already have through the graph editor, which
is unauthenticated-by-design at this trust tier (see Consequences).

## Consequences

- **The default flips to loopback-only.** `expose_to_network` defaults to
  `False`, so `ui.run()` binds `127.0.0.1` unless an operator explicitly
  opts in — a behavior change from the previous unconditional `0.0.0.0`
  bind. Anyone who relied on unauthenticated LAN access must now set
  `expose_to_network` (and almost certainly `allowed_remote_ranges`)
  explicitly.
- **All three settings are read once at startup; changing any of them
  requires a restart.** `NetworkSettings` and `FarmhandSettings` fields all
  carry the house phrase "Read once at startup; restart to apply." in their
  description. `IPAllowlistMiddleware` parses its CIDR lists once in
  `__init__`; there is no runtime-live allowlist.
- **An invalid CIDR entry refuses to start the process, not fail open.**
  `HaywireApp._install_ip_allowlist` constructs a throwaway
  `IPAllowlistMiddleware` purely to run its constructor's CIDR parsing
  eagerly (Starlette's `add_middleware` only records `(cls, args, kwargs)`
  and would otherwise defer the same `ValueError` until the first request,
  or never raise it if the server received none). A parse failure prints a
  clear error naming the offending setting and exits via
  `SystemExit(1)` rather than silently starting unprotected.
- **`NetworkSettings.public_hostname` feeds the MCP `allowed_hosts`/
  `allowed_origins` lists.** `FarmhandHost.mount()` builds
  `TransportSecuritySettings` from the request port plus, when
  `restrict_to_loopback` is on and `public_hostname` is set, the configured
  hostname — in both its bare and `:port`-qualified forms (skipping the
  bare-plus-port duplication if the setting already names a port), and both
  `http://` and `https://` origin forms, since this module cannot know which
  scheme a fronting reverse proxy terminates as. Leaving `public_hostname`
  empty (the default) leaves the loopback-only list exactly as before. This
  is what lets a reverse-proxy deployment with `restrict_to_loopback` still
  on pass the DNS-rebinding `Host`/`Origin` check for the proxy's own
  hostname.
- **The single-operator trust model is unchanged.** None of this is
  authentication, authorization, or per-user isolation for the graph editor
  itself — it remains full arbitrary-code-execution surface for anyone who
  gets past the bind address and allowlist. These controls narrow *who can
  reach the process*; they do not change what a reachable caller can do once
  in, which stays "everything," by design, for this single-operator
  workbench.

## Alternatives considered

**`BaseHTTPMiddleware` subclass for the IP filter.** Rejected outright — see
"Pure-ASGI over `BaseHTTPMiddleware`" above. This is not a style preference;
it is the difference between a filter that works and one that silently
doesn't cover the WebSocket transport carrying the actual application.

**Trusting `X-Forwarded-For` unconditionally.** Rejected: any client can set
that header, so honoring it without a `trusted_proxies` check would let a
rejected peer simply claim an allowed address.

**Making `restrict_to_loopback` a true bind-level check.** Not pursued
because it configures the MCP SDK's `TransportSecuritySettings`, which
validates headers by design — reworking it into a socket-level restriction
would duplicate the bind-address/allowlist layers this ADR already
describes for the rest of the studio, for one mount, using a different
mechanism than the SDK it's layered onto provides.

## References

- Plan: `docs/superpowers/plans/2026-08-14-studio-network-exposure.md`
- `packages/haywire-studio/src/haywire_studio/network/settings.py` — `NetworkSettings`
- `packages/haywire-studio/src/haywire_studio/network/ip_filter.py` — `IPAllowlistMiddleware`
- `packages/haywire-studio/src/haywire_studio/farmhand/settings.py` — `FarmhandSettings`
- `packages/haywire-studio/src/haywire_studio/farmhand/auth.py` — `BearerTokenMiddleware`
- `packages/haywire-studio/src/haywire_studio/farmhand/host.py` — `FarmhandHost.mount()`
- `packages/haywire-studio/src/haywire_studio/app.py` — `HaywireApp.run()`, `_install_ip_allowlist`
- `packages/haywire-studio/src/haywire_studio/code_intelligence.py` — `_confined_path`
