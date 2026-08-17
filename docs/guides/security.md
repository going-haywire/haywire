---
status: draft
doc_template: guide
scope: The studio's whole defence picture — network location, authentication, TLS, and the Farmhand MCP mount — as one security document and one set of CLI commands
see-also:
  - ../adr/0028-security-document.md
  - ../adr/0026-studio-network-exposure.md
  - ../adr/0027-studio-authentication.md
  - ../reference/glossary.md
---

# Security

Whoever can reach the studio can execute arbitrary Python through the graph
editor. This guide covers everything that decides *who that is* and *what
they can prove before they get in*: where the studio can be reached from, who
may connect once it's reachable, whether the wire between them is encrypted,
and what the Farmhand MCP mount adds on top. For the design rationale behind
the shape of these controls, see [ADR-0028](../adr/0028-security-document.md);
for the network-layer mechanics specifically, see
[ADR-0026](../adr/0026-studio-network-exposure.md); for the authentication
gate, see [ADR-0027](../adr/0027-studio-authentication.md).

Sandboxing the graph editor is out of scope for all of it — a principal who
can edit a graph holds the authority of the studio process, by design. See
[§11](#11-no-sandbox-no-multi-tenancy).

## 1. Default: local only

Out of the box, `uv run haywire` binds to `127.0.0.1` only. Nothing off-box
can reach the studio, the code-intelligence endpoints, or the Farmhand MCP
server, regardless of what else is configured — the OS refuses the
connection before any application-level check runs.

**This changed, twice.** Earlier versions of the studio called `ui.run()`
with no `host` argument, which made NiceGUI bind `0.0.0.0` — reachable from
the LAN with no guard at all. A later version introduced `expose_to_network`
as a settings-panel checkbox. Neither shape survives. Every control that
decides who can reach this studio now lives in one file,
`~/.haywire/security.json`, changed only from the command line, with the
studio stopped. Nothing is migrated automatically from either earlier shape
— the default is loopback-only, authentication off, for every fresh
installation, exactly as it always has been. If you relied on network
access, TLS, or authentication under an older version, you need to
reconfigure it with the commands in this guide.

## 2. The four axes

Everything in this guide is one of four independent axes, each read once at
process startup — **changing any of them requires restarting the studio**;
there is no live-reload path for any of them.

| Axis | Question it answers | Command | Covered in |
| --- | --- | --- | --- |
| Network location | Which machines can open a connection at all? | `haywire network` | [§4](#4-opening-the-studio-up), [§5](#5-cidr-syntax), [§7](#7-running-on-a-server) |
| Authentication | Who, once connected, is let in? | `haywire auth`, `haywire user` | [§9](#9-managing-principals) |
| TLS | Is the traffic between them encrypted? | `haywire ssl` | [§8](#8-serving-https) |
| Farmhand | Is the MCP tool endpoint served, and to whom? | `haywire farmhand` | [§6](#6-the-mcp-endpoint) |

All four are fields of one document, `~/.haywire/security.json`
([§10](#10-the-security-document)), and none of them is a checkbox in a
settings panel. That is not an accident of implementation — a checkbox
cannot express "you may only turn this on if the other three axes are
already in a safe state," and three of these four axes have exactly that
kind of precondition. `haywire security status` reads all four together and
reports the combinations a single-axis view cannot see — see
[ADR-0028](../adr/0028-security-document.md) for why the axes were split out
of the settings system that used to hold them.

## 3. What you are exposing

This is the honest inventory. Turning on network exposure (and widening the
allowlist beyond your own machine) puts the following in front of anyone in
the allowed range:

- **The studio UI itself.** Full graph editing is **arbitrary code
  execution** — a graph runs Python in-process. Anyone who can reach the UI
  and authenticate as an `edit` or `admin` principal is a full operator.
  There is no sandbox around what a graph can do.
- **`/api/code-intel/complete`, `/info`, `/hover`.** Unauthenticated by
  design (they back inline editor autocomplete). `_confined_path()`
  (`code_intelligence.py`) restricts the `path` argument to the current
  workspace root plus everything on `sys.path` — a caller cannot walk the
  filesystem to arbitrary locations. Within those roots, though, the
  endpoints will happily disclose names, signatures, and docstrings via
  jedi's static analysis. This is not new capability beyond what a graph node
  could already obtain by importing the same modules, but it's reachable
  without going through the graph editor at all.
- **`/mcp` (the Farmhand MCP server).** Behind the same authentication gate
  as everything else once the studio is exposed — see
  [§6](#6-the-mcp-endpoint) for what guards it and why a second, MCP-specific
  credential is no longer part of the picture.

## 4. Opening the studio up

`haywire network expose` is a verb, not a switch, because safe exposure is
three coordinated preconditions and a checkbox cannot enforce any of them:

```sh
# with the studio stopped
uv run haywire auth enable          # need at least one admin first
uv run haywire ssl setup            # need TLS configured
uv run haywire network expose --ranges 192.168.1.0/24
```

Each of the three refusals below names the command that clears it, and
`expose` checks all three every time it runs — there is no way to end up
with a network binding wider than loopback while any one of them is false:

- **"the studio cannot be exposed with authentication off"** — run
  `haywire auth enable` first. Anyone who could reach an unauthenticated,
  exposed studio would be a full operator with no login required; see
  [§9](#9-managing-principals).
- **"the studio cannot be exposed without TLS"** — run `haywire ssl setup`
  first. Passwords and session cookies would otherwise cross the network in
  cleartext the moment authentication has anything to protect; see
  [§8](#8-serving-https).
- **"the studio cannot be exposed with an empty allowlist"** — pass
  `--ranges` naming at least one CIDR block. An exposed studio with no
  allowed ranges rejects every remote peer, which is real but not what
  "expose" plausibly means to type; see [§5](#5-cidr-syntax).

`haywire network seal` reverses the bind — the studio answers on loopback
again — and **keeps the allowlist you configured**. Sealing is the usual
temporary case (a laptop leaving the venue, a demo that just ended); keeping
the ranges means opening back up later is `haywire network expose --ranges
<same subnet>` again, not re-deriving the CIDR block from memory.

```sh
uv run haywire network status       # where the studio can currently be reached from
uv run haywire security status      # the full four-axis picture
```

## 5. CIDR syntax

The `--ranges` and `--trusted-proxies` arguments both take CIDR ranges,
validated with Python's `ipaddress.ip_network(entry, strict=False)`. A few
worked examples:

| Entry | Meaning |
| --- | --- |
| `192.168.1.42/32` | A single host — `/32` matches exactly one address. |
| `192.168.1.0/24` | A subnet — the whole `192.168.1.x` range. |
| `10.21.36.0/21` | A subnet — the whole `10.21.36.x` - `10.21.43.x` range. |
| `10.0.0.0/8` | The entire RFC-1918 `10.x.x.x` block. |

Multiple entries are comma-separated in one argument:

```sh
uv run haywire network expose --ranges "192.168.1.0/24, 10.0.0.0/8"
```

**Loopback is implicit.** `127.0.0.1`/`::1` are allowed unconditionally by
`IPAllowlistMiddleware`, before any list membership check runs. You never
need to list loopback yourself, and — importantly — there is no way to
*exclude* it either.

Be careful reading the empty case the other way round, though: an
unreachable-by-others allowlist does **not** mean "allow everyone."
Membership is `any(ip in network for network in allowed_ranges)`, which over
an empty list is always `False` — this is exactly why `--ranges` is a
required argument to `expose` rather than an optional one, so the confusing
empty-list state is never reachable through the CLI at all. An invalid entry
refuses the write, with a clear error naming the offending value, rather
than a silently-unprotected process or a failure buried until the first
request.

## 6. The MCP endpoint

`haywire farmhand` configures the Farmhand MCP mount at `/mcp`:

```sh
uv run haywire farmhand enable          # serve /mcp
uv run haywire farmhand disable         # stop serving it
uv run haywire farmhand local-only      # reject requests whose Host isn't loopback (default)
uv run haywire farmhand allow-remote    # accept requests from any Host
uv run haywire farmhand status
```

`/mcp` is mounted inside the same ASGI app as the rest of the studio, so it
sits behind the same authentication gate as everything else: a bearer token
is required whenever authentication is on, and the studio cannot be exposed
with authentication off ([§4](#4-opening-the-studio-up)). There is no
separate MCP credential and no workspace token file any more — an agent
connects with a roster token, minted by `haywire user add <name> --agent
--tier edit`, the same roster that authenticates a browser session.

### `restrict_to_loopback`

This is the setting most likely to matter to you without your knowing it
exists, so it gets called out explicitly rather than left to a settings
table.

**What DNS rebinding is.** A page open in your browser — any page, not one
you'd suspect — can be scripted to resolve an attacker-controlled domain
name to `127.0.0.1` *after* it has already loaded, then issue requests to
that domain from JavaScript. Your browser sees a same-origin request to
`127.0.0.1` and attaches cookies and local trust to it exactly as it would
for any other request to localhost. If a local MCP server happens to be
listening on that port, the malicious page can talk to it as if it were an
invited client.

**Why a header check defeats it.** `restrict_to_loopback` configures the MCP
SDK's `TransportSecuritySettings` to reject any `/mcp` request whose `Host`
or `Origin` header is not loopback. A browser sets that header honestly on
requests it issues itself — it is the one signal in this whole system a
browser cannot be talked into lying about — so a rebinding attempt shows up
with a `Host` value the browser wrote truthfully, and it's rejected.

**Why it does not stop `curl`.** The header is client-supplied, full stop.
`curl -H 'Host: 127.0.0.1:8124' http://<lan-ip>:8124/mcp` sails straight
through the check, because nothing about the header contradicts itself —
the check has no way to know the `Host` value doesn't match how the request
actually arrived. `restrict_to_loopback` is not a network-location control
and was never meant to be one; the peer-address allowlist
([§5](#5-cidr-syntax)) and the authentication gate are what actually decide
who can reach `/mcp` at all. This setting closes exactly one specific
attack — a browser talked into betraying itself — and nothing wider.

**When you would legitimately turn it off.** An MCP client running on
another machine — a colleague's laptop, a CI runner, an agent host that
isn't this box — needs the studio to accept a `Host` header that genuinely
isn't loopback, because from that client's point of view the studio's
address isn't `127.0.0.1`. That is exactly what `haywire farmhand
allow-remote` is for.

**Why doing so requires authentication.** With the header check off, the one
thing standing between an arbitrary web page and this studio's MCP tools —
including a tool that can add and execute a Python node — is whatever
guards `/mcp` otherwise. Without authentication, that is nothing.
`set_farmhand_loopback` therefore refuses to turn the check off while
`auth.enabled` is `false`: run `haywire auth enable` first. This is a
constraint on the *transition*, not on the resulting state — a document
that already has both off is not treated as corrupt on load, since that
combination can be reached by disabling authentication afterward, and
refusing to boot over it would be a lockout. `haywire security status`
reports it if it happens.

## 7. Running on a server

If you want to reach the studio from somewhere other than the machine it
runs on, three approaches work with today's trust model — all three keep
the studio itself talking loopback-only or allowlisted-only, rather than
trusting the open network directly.

### VPN / Tailscale (recommended)

Put the studio's host on a VPN or a Tailscale/WireGuard-style mesh network,
and leave network exposure off (or scope `--ranges` to just the VPN's own
subnet). Every peer on the VPN is implicitly trusted at the network layer,
which matches the studio's own trust model — anyone who can reach it is a
full operator either way, once authenticated. No studio-side change beyond
what's already required to expose at all.

### Reverse proxy with auth in front

Put nginx (or similar) in front of the studio, terminate TLS and
authentication there, and forward to the studio's loopback port. Two
arguments to `haywire network expose` matter for this shape:

- **`--trusted-proxies`** — set to the proxy's own peer IP (or CIDR range)
  so `IPAllowlistMiddleware` will honor `X-Forwarded-For` from it when
  deciding the real client IP. Leaving it unset while exposed means every
  request appears to originate from the proxy itself — `haywire security
  status` flags this as a NOTE.
- **`--hostname`** — set to the hostname the proxy fronts, e.g.
  `haywire.example.com` or `haywire.example.com:443`. When
  `restrict_to_loopback` is on (the default), `FarmhandHost.mount()`
  (`farmhand/host.py`) adds this hostname to the MCP `allowed_hosts` and
  `allowed_origins` lists so the DNS-rebinding check doesn't reject
  legitimate proxied traffic. Concretely, it adds both the bare hostname and
  a `:port`-qualified form (skipping the port-qualified duplicate if you
  already included a port) to `allowed_hosts`, and both `http://` and
  `https://` origin forms to `allowed_origins` — the studio can't know which
  scheme the proxy terminates as, so it allows both. Leave `--hostname`
  unset and this list stays loopback-only, exactly as before.

The usual failure mode proxying this app specifically is the WebSocket
upgrade: the studio's entire live UI runs over Socket.IO after the initial
page load, so a proxy config that only forwards plain HTTP will load the
page and then go dead on every interaction. Make sure `Upgrade`/`Connection`
headers are forwarded:

```nginx
location / {
    proxy_pass http://127.0.0.1:8124;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

See [ADR-0026](../adr/0026-studio-network-exposure.md#pure-asgi-over-basehttpmiddleware-the-socketio-hole)
for why this matters at the ASGI layer, not just for nginx configuration.

### `ssh -L` (zero config)

`ssh -L 8124:localhost:8124 user@host` tunnels a local port to the studio's
loopback port on the remote machine. Works today with the default settings
— network exposure can stay off, since the tunnel presents as loopback
traffic on the remote end. No studio-side configuration at all.

## 8. Serving HTTPS

Without TLS the studio serves plain HTTP. On a loopback-only studio that is
fine — the traffic never leaves the machine, and this is reported as the
correct configuration it is, not as a warning. Once the studio is exposed,
`haywire network expose` already refuses to run without TLS configured
first, so this section covers how to configure it.

Two things follow once traffic does cross the network unencrypted (which
`expose` no longer permits, but is worth understanding as the reason the
precondition exists):

- The session cookie that *is* a principal's identity travels in cleartext
  on every request, as do passwords at login and agent bearer tokens.
  Anyone who can observe one request can replay it.
- **Browser features that require a secure context are unavailable.**
  `http://192.168.…` is not a
  [secure context](https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts)
  (`http://localhost` is, which is why this never reproduces on the machine
  you develop on), and there is no override.

    In practice this costs Haywire nothing today. `navigator.clipboard` is
    restricted this way, but the copy helper falls back to
    `document.execCommand`, so copy buttons still work. Camera and
    microphone are not affected at all — Haywire captures video server-side
    in Python (`cv2.VideoCapture`, `depthai`), so no browser permission is
    involved. The rule only starts to bite if a library reaches for
    `navigator.mediaDevices`, geolocation, notifications or a service worker
    from the front end.

### One command

```sh
uv run haywire ssl setup
```

This generates a self-signed certificate, stores it in `~/.haywire/certs/`
(key `0600`, certificate `0644`), and writes the certificate and key paths
into `~/.haywire/security.json`. Restart the studio and it serves HTTPS.

The certificate covers `localhost`, `127.0.0.1`, `::1`, every non-link-local
address the machine currently has, the machine's hostname, its `<host>.local`
mDNS name, and the hostname you passed to `haywire network expose
--hostname`, if any. Add more with `--also`, repeatable:

```sh
uv run haywire ssl setup --also studio.example.com --also 10.21.136.88
```

### What the browser does

A self-signed certificate produces a full-page warning on first visit —
`NET::ERR_CERT_AUTHORITY_INVALID` in Chrome, `SEC_ERROR_UNKNOWN_ISSUER` in
Firefox, "This Connection Is Not Private" in Safari. This is **not** about
weak encryption. The connection is fully encrypted either way; the browser
is telling you it cannot verify *who* is on the other end, because the only
thing vouching for the certificate is the certificate itself.

You can click through ("Advanced" → proceed), and the origin then counts as
a secure context. But the exception is per-browser and per-device, and
non-browser clients (an MCP agent, `curl`, `httpx`) reject the certificate
outright with no interstitial to click.

To remove the warning entirely, make the machine trust the certificate:

```sh
uv run haywire ssl trust
```

That prints the platform command — `security add-trusted-cert` on macOS,
`update-ca-certificates` on Linux, `Import-Certificate` on Windows. Haywire
prints it rather than running it: it needs `sudo` and it modifies a system
trust store, which is not something a subcommand should do unannounced. Run
it once per machine that connects.

### Checking what you have

```sh
uv run haywire ssl status
```

Reports whether TLS is configured, which names the certificate covers, when
it expires, and — importantly — whether the address you are currently
reachable at is one of them. It always exits `0`; it reports rather than
judges, and "loopback only, no TLS" is reported as the correct configuration
it is.

It also catches the three states that make the studio refuse to start: a
missing certificate file, only one of the pair configured, and a key that
does not match its certificate.

### Moving between networks

A certificate is valid only for the names baked into it when it was signed.
A laptop that moves between a home LAN and a university network gets a
different IP in each, so a certificate listing only the home address will
be rejected at the other one.

Two things handle this. First, the `<host>.local` mDNS name is covered by
default and follows the machine, so `https://your-machine.local:8124` often
keeps working with no change at all — `ssl status` tells you when that
applies. Second, when you do need the new address in the certificate:

```sh
uv run haywire ssl update --refresh
```

`update` re-signs **reusing the existing private key** and preserves names
you added by hand, so it amends the certificate rather than starting over.
Use `--add` / `--remove` to change the list explicitly. Loopback names
cannot be removed.

Because trust stores pin the certificate rather than the key, anyone who
ran `ssl trust` must run it again after an update. The command says so.

### When a real certificate is the better answer

`haywire ssl setup` is deliberately limited to self-signed certificates,
which suit a LAN. If the studio is reachable from the public internet under
a real domain name, terminate TLS at a reverse proxy with a CA-issued
certificate instead (see [§7](#7-running-on-a-server)) and leave the
certificate/key paths unset — a proxy-terminated setup has no browser
warning and needs no per-machine trust step.

## 9. Managing principals

Authentication is a separate, independent layer from network location — off
by default. With it off, anyone who can reach the studio is a full
operator, and `haywire network expose` will not let you turn on network
exposure until it's on.

### Enabling it

Authentication needs at least one admin principal before it can be turned
on — the roster is empty otherwise and nobody could sign back in.

```sh
# with the studio stopped
uv run haywire user add alice --tier admin
uv run haywire auth enable
```

`auth enable` prompts for an admin username and password and verifies them
before writing the flag — a proof of recoverability, not a barrier against
an attacker (anyone who can run the command can also edit the JSON by
hand). It makes the realistic failure unreachable: turning on authentication
with a roster whose passwords nobody remembers, on a machine whose UI is
now the only way to fix it.

### Managing principals

```sh
uv run haywire user add <name> --tier {view,edit,admin}              # a password-holding user
uv run haywire user add <name> --agent --tier {view,edit,admin}      # a token-holding agent
uv run haywire user add <name> --agent --tier edit --workspace <path> # scoped to one project
uv run haywire user list
uv run haywire user tier <name> {view,edit,admin}
uv run haywire user passwd <name>
uv run haywire user remove <name>
uv run haywire auth status
uv run haywire auth disable
```

Once signed in, an admin can do all of this from the studio itself — the
account menu behind the `account_circle` icon at the bottom of the action
bar opens a roster editor with the same add/remove/re-tier/re-key
operations, plus live effect: a re-tiered or removed principal's open
session is evicted immediately, no re-login needed to see it take hold. The
account menu also shows who else is currently connected (both browser
sessions and MCP agents, the latter by last-seen time rather than a
possibly-stale online/offline flag).

Every mutation — CLI or UI — goes through the same document, so the two
surfaces can never disagree about who's allowed in.

An agent principal's token is the credential an MCP client presents; connect
with `claude mcp add --transport http farmhand http://127.0.0.1:8124/mcp
--header "Authorization: Bearer <token>"`, or with no header at all when
authentication is off.

## 10. The security document

Everything in this guide is one axis of `~/.haywire/security.json`: mode
`0600`, three blocks (`auth`, `network`, `farmhand`), one file. It is
**machine-global**, never per-project, and it must never be committed to a
repository — nothing under `~/.haywire/` belongs in a project's version
control, and this file specifically holds password hashes, agent tokens,
and this machine's exposure decisions.

You do not normally edit it by hand — every CLI command in this guide reads
and writes it for you, validating as it goes so an invalid combination
(exposed with authentication off, TLS half-configured, an unparseable CIDR
entry) is refused before it's written. If you do edit it by hand anyway, or
it's touched by a bad merge or a partial write, the studio does not refuse
to start over it. At boot, the document is **sanitized**: any violation is
repaired in the safe direction (exposure off, TLS off, authentication off),
the reasons are logged at `CRITICAL`, and the same list is available on
demand:

```sh
uv run haywire security status
```

This is the one command that reads all four axes together and reports the
combinations a single-axis view can't — authentication on with TLS off, for
instance, which turns "enabling auth" into "putting a password on a wire
that reads in cleartext," a finding that `auth status` and `ssl status`
alone cannot each independently produce.

## 11. No sandbox, no multi-tenancy

The studio is one process, one filesystem, with no sandbox between whoever
reaches it and the host machine it runs on. Authentication adds *who* a
connection is — separate view/edit/admin principals with their own
identity — but not *isolation*: there is no "read-only copy of the studio"
and no per-graph, per-node or per-file permission. Every principal who can
reach the studio sees the same live graphs, the same running execution and
the same haystack; a `view` principal simply cannot mutate them. None of the
settings in this guide add a sandbox around the graph editor — a principal
who can edit a graph holds the authority of the studio process, by design.
See [ADR-0026](../adr/0026-studio-network-exposure.md#consequences) and
[ADR-0027's non-goals](../adr/0027-studio-authentication.md#explicit-non-goals)
for the full framing.
