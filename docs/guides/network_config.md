---
status: draft
doc_template: guide
scope: Configuring how the studio is reachable — bind address, IP allowlist, reverse proxies, and what each surface exposes
see-also:
  - ../adr/0026-studio-network-exposure.md
  - ../reference/glossary.md
---

# Network configuration

Whoever can reach the studio can execute arbitrary Python through the graph
editor. This guide covers the settings that control *where it can be reached
from* — bind address, an IP allowlist, and what to do if you want to reach the
studio from another machine. For the full design rationale, see
[ADR-0026](../adr/0026-studio-network-exposure.md).

It does not cover *who* may connect. Authenticating principals is a separate,
independent layer designed in
[ADR-0027](../adr/0027-studio-authentication.md); neither layer substitutes for
the other, and nothing on this page performs any authentication. Sandboxing the
graph editor is out of scope for both — a principal who can edit a graph holds
the authority of the studio process, by design.

## 1. Default: local only

Out of the box, `uv run haywire` binds to `127.0.0.1` only. Nothing off-box
can reach the studio, the code-intelligence endpoints, or the Farmhand MCP
server, regardless of what else is configured — the OS refuses the
connection before any application-level check runs.

**This changed.** Earlier versions of the studio called `ui.run()` with no
`host` argument, which made NiceGUI bind `0.0.0.0` — reachable from the LAN
with no guard at all. If you relied on that for LAN access (a Farmhand agent
on another machine, a colleague's laptop), you now need to opt in explicitly:
set `expose_to_network` to `True` and, in almost every case, populate
`allowed_remote_ranges` too (see [§2](#2-the-five-settings)). Nothing is
migrated automatically — the new default is loopback-only for everyone.

## 2. The five settings

All five live in `NetworkSettings`
(`packages/haywire-studio/src/haywire_studio/network/settings.py`). Every one
of them is read once at process startup — **changing any of these requires
restarting the studio**; there is no live-reload path.

| Setting | Category | Default | What it does |
| --- | --- | --- | --- |
| `port` | `network` | `8124` | The port the studio's web server (and the Farmhand `/mcp` mount it carries) listens on. |
| `expose_to_network` | `network` | `False` | Binds to `0.0.0.0` instead of `127.0.0.1` when `True`, so other machines on the network can reach the studio. This is the master switch — off, everything below is moot. |
| `allowed_remote_ranges` | `network` | `""` (empty) | Comma-separated CIDR ranges allowed to reach the studio once `expose_to_network` is on (e.g. `192.168.1.0/24, 10.0.0.0/8`). Only takes effect when `expose_to_network` is `True`; loopback is always allowed regardless. |
| `public_hostname` | `advanced` | `""` (empty) | The hostname (optionally `host:port`) the studio is reachable at from outside — e.g. behind a reverse proxy. Feeds the MCP `allowed_hosts`/`allowed_origins` lists (see [§5](#5-running-on-a-server)). |
| `trusted_proxies` | `advanced` | `""` (empty) | Comma-separated CIDR ranges of reverse proxies whose `X-Forwarded-For` header is trusted for resolving the real client IP. |

A sixth setting, `restrict_to_loopback`, is easy to expect in this table and
isn't here — it lives on `FarmhandSettings`
(`packages/haywire-studio/src/haywire_studio/farmhand/settings.py`), category
`farmhand`, not on `NetworkSettings`. It only governs the `/mcp` mount, not
the studio as a whole, so it's covered in [§4](#4-what-you-are-exposing)
where its actual guarantee (and its limit) matters.

## 3. CIDR syntax

`allowed_remote_ranges` and `trusted_proxies` both take a comma-separated
list of CIDR ranges, validated with Python's `ipaddress.ip_network(entry,
strict=False)`. A few worked examples:

| Entry | Meaning |
| --- | --- |
| `192.168.1.42/32` | A single host — `/32` matches exactly one address. |
| `192.168.1.0/24` | A subnet — the whole `192.168.1.x` range. |
| `10.21.36.0/21` | A subnet — the whole `10.21.36.x` - '10.21.43.x range. |
| `10.0.0.0/8` | The entire RFC-1918 `10.x.x.x` block. |

Multiple entries are comma-separated in one field:

```text
192.168.1.0/24, 10.0.0.0/8
```

**Loopback is implicit.** `127.0.0.1`/`::1` are allowed unconditionally by
`IPAllowlistMiddleware`, before any list membership check runs. You never
need to list loopback yourself, and — importantly — there is no way to
*exclude* it either: an empty `allowed_remote_ranges` doesn't mean "deny
all," it means "no further restriction beyond loopback." This is deliberate:
`ui.run(show=True)` opens a local browser against the studio it just started,
and a filter that could reject that connection would lock the operator out of
the only UI that could fix the misconfigured setting.

An invalid entry in either field refuses to start the studio — you'll get a
clear error naming the offending setting rather than a silently-unprotected
process or a failure buried until the first request.

## 4. What you are exposing

This is the honest inventory. Turning on `expose_to_network` (and widening
`allowed_remote_ranges` beyond your own machine) puts the following in front
of anyone in the allowed range:

- **The studio UI itself.** Full graph editing is **arbitrary code
  execution** — a graph runs Python in-process. Anyone who can reach the UI
  is a full operator. There is no authentication in front of it and no
  sandbox around what a graph can do.
- **`/api/code-intel/complete`, `/info`, `/hover`.** Unauthenticated by
  design (they back inline editor autocomplete). `_confined_path()`
  (`code_intelligence.py`) restricts the `path` argument to the current
  workspace root plus everything on `sys.path` — a caller cannot walk the
  filesystem to arbitrary locations. Within those roots, though, the
  endpoints will happily disclose names, signatures, and docstrings via
  jedi's static analysis. This is not new capability beyond what a graph node
  could already obtain by importing the same modules, but it's reachable
  without going through the graph editor at all.
- **`/mcp` (the Farmhand MCP server).** Token-guarded by default
  (`FarmhandSettings.require_auth = True`): every request needs an
  `Authorization: Bearer <token>` header, and this is the check that
  actually carries the enforcement weight — possession of the token is what
  stops an attacker. `restrict_to_loopback` (also on, by default) adds a
  *second*, different check: it rejects `/mcp` requests whose `Host`/`Origin`
  header isn't `127.0.0.1`/`localhost`, which defeats DNS-rebinding attacks
  (a malicious page in your own browser resolving an attacker domain to
  `127.0.0.1` and talking to the local MCP server as if same-origin). **It
  does not stop a forged `Host` header** — `curl -H 'Host:
  127.0.0.1:8124' http://<lan-ip>:8124/mcp` sails straight through, because
  the check has no way to know the `Host` value doesn't match how the
  request actually arrived. Don't rely on `restrict_to_loopback` as a
  network-location control; rely on the bearer token for that, and on
  `allowed_remote_ranges` for peer-level filtering.

## 5. Running on a server

If you want to reach the studio from somewhere other than the machine it runs
on, three approaches work with today's trust model — all three keep the
studio itself talking loopback-only or allowlisted-only, rather than trusting
the open network directly.

### VPN / Tailscale (recommended)

Put the studio's host on a VPN or a Tailscale/WireGuard-style mesh network,
and leave `expose_to_network` off (or set `allowed_remote_ranges` to just the
VPN's own subnet). Every peer on the VPN is implicitly trusted at the network
layer, which matches the studio's own trust model — anyone who can reach it
is a full operator either way. No studio-side auth to configure beyond what's
already on by default.

### Reverse proxy with auth in front

Put nginx (or similar) in front of the studio, terminate TLS and
authentication there, and forward to the studio's loopback port. Two settings
matter for this shape:

- **`trusted_proxies`** — set to the proxy's own peer IP (or CIDR range) so
  `IPAllowlistMiddleware` will honor `X-Forwarded-For` from it when deciding
  the real client IP. Leaving it empty while `expose_to_network` is on means
  every request appears to originate from the proxy itself — the studio logs
  a startup warning in that case.
- **`public_hostname`** — set to the hostname the proxy fronts, e.g.
  `haywire.example.com` or `haywire.example.com:443`. When
  `restrict_to_loopback` is on (the default), `FarmhandHost.mount()`
  (`farmhand/host.py`) adds this hostname to the MCP `allowed_hosts` and
  `allowed_origins` lists so the DNS-rebinding check doesn't reject
  legitimate proxied traffic. Concretely, it adds both the bare hostname and
  a `:port`-qualified form (skipping the port-qualified duplicate if you
  already included a port) to `allowed_hosts`, and both `http://` and
  `https://` origin forms to `allowed_origins` — the studio can't know which
  scheme the proxy terminates as, so it allows both. Leave `public_hostname`
  empty and this list stays loopback-only, exactly as before.

The usual failure mode proxying this app specifically is the WebSocket
upgrade: the studio's entire live UI runs over Socket.IO after the initial
page load, so a proxy config that only forwards plain HTTP will load the page
and then go dead on every interaction. Make sure `Upgrade`/`Connection`
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
loopback port on the remote machine. Works today with the default settings —
`expose_to_network` can stay off, since the tunnel presents as loopback
traffic on the remote end. No studio-side configuration at all.

## 6. Machine-wide defaults: the global settings tier

The settings in [§2](#2-the-five-settings) are editable in the studio UI, but
on a head server that is often the wrong place for them. `public_hostname`
and `trusted_proxies` describe *the deployment* — the reverse proxy in front
of this machine — not the preferences of whoever happens to be drawing
graphs. They belong with the person who wrote the nginx config, and they
should apply to every project opened on the box rather than being re-entered
per workspace.

That is what the **global tier** is for.

### Which file

Haywire has two unrelated stores under `~/.haywire/`, and it is easy to reach
for the wrong one:

| File | Holds | Read by |
| --- | --- | --- |
| `~/.haywire/settings.json` | **Setting values** — everything in `NetworkSettings`, `FarmhandSettings`, etc. | The settings registry |
| `~/.haywire/config.toml` | Studio bootstrap config: `[haywire] version`, `[ui] theme`, self-hosted marketplace hosts | `haywire_studio.config` |

Network settings go in **`settings.json`**. Nothing in the settings system
reads `config.toml`, so a `public_hostname` written there is silently ignored
— no error, no warning, and the studio starts with the default empty value.

### The three tiers

Values resolve highest-priority-set-wins across three tiers
(`SettingsRegistry`,
`packages/haywire-core/src/haywire/core/settings/registry.py`):

```text
local (per-node, in graph JSON)  >  workspace  >  global  >  default
```

| Tier | File | Written by |
| --- | --- | --- |
| `workspace` | `<project>/.haywire/settings.json` | The UI, on save |
| `global` | `~/.haywire/settings.json` | **You, by hand** — the app never writes it |

The global tier is the machine-wide default layer. The app loads it at
startup and never overwrites it, so a hand-edited value survives every UI
save. The file does not exist on a fresh install; create it yourself.

**A workspace value still wins over your global one.** If someone opens a
project whose `.haywire/settings.json` already carries a `network` entry —
including one the UI wrote by saving the panel with default values — that
project's value shadows the global default. If a global setting appears not
to take effect, check the workspace file first.

### Setting `public_hostname` and `trusted_proxies`

Create `~/.haywire/settings.json` with the `network` namespace. Each setting
is an object with a `value` key, nested under its namespace:

```json
{
  "network": {
    "public_hostname": {
      "value": "haywire.example.com"
    },
    "trusted_proxies": {
      "value": "172.16.0.0/12"
    }
  }
}
```

A fuller head-server example, pinning the whole network posture for the
machine — bound to all interfaces, reachable only from the office subnet and
the proxy, behind TLS on port 443:

```json
{
  "network": {
    "expose_to_network": {
      "value": true
    },
    "allowed_remote_ranges": {
      "value": "192.168.10.0/24, 172.16.0.0/12"
    },
    "public_hostname": {
      "value": "haywire.example.com:443"
    },
    "trusted_proxies": {
      "value": "172.16.0.0/12"
    }
  }
}
```

Notes on the format:

- The namespace is `network` because `NetworkSettings` declares
  `namespace="network"`. Other schemas use their own (`farmhand`, `editor`,
  `debug`, …) and can live in the same file as sibling keys.
- Booleans are JSON booleans (`true`), not the strings `"True"`/`"true"`.
- CIDR lists are a **single comma-separated string**, not a JSON array —
  `"192.168.1.0/24, 10.0.0.0/8"`. See [§3](#3-cidr-syntax) for the syntax.
- A bare value (`"public_hostname": "haywire.example.com"`) is also accepted,
  but prefer the explicit `{"value": …}` form — it is what the UI writes and
  what the rest of the file will look like.

### Applying and verifying

These are startup-only reads ([§2](#2-the-five-settings)), so **restart the
studio** after editing. Two things worth knowing about failure modes:

- **Invalid CIDR refuses to start.** A malformed entry in
  `trusted_proxies` or `allowed_remote_ranges` exits with a clear error
  naming the setting, rather than starting unprotected.
- **Invalid JSON is quieter.** A syntax error doesn't stop startup: the store
  logs `Failed to parse settings file` at ERROR level, the whole tier is
  skipped, and every setting in it falls back to its default. It is easy to
  miss in the startup noise, so if your values seem ignored, validate the
  file first — e.g. `python -m json.tool ~/.haywire/settings.json`.

To confirm the values took effect, start the studio with `expose_to_network`
on and check the startup log: an empty `trusted_proxies` logs the warning
described in [§5](#reverse-proxy-with-auth-in-front), and its absence means
your proxy CIDR was read. The Network settings panel also reflects the
resolved value, whichever tier it came from.

## 7. Multi-user: not supported

The studio is one process, one filesystem, with no sandbox between whoever
reaches it and the host machine it runs on. There is no per-user identity,
no isolation between concurrent operators, and no notion of "read-only"
access — everyone who gets past the bind address, allowlist, and (for
`/mcp`) the bearer token is the same single operator the studio was designed
for. None of the settings in this guide add authentication or authorization
for the graph editor itself; they only narrow *who can reach the process*,
never *what a reachable caller can do* once in. See
[ADR-0026](../adr/0026-studio-network-exposure.md#consequences) for the full
framing.
