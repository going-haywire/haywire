---
name: security-document
description: Every startup-read control that decides who can reach the studio and what they can do once there moves into one 0600 document, ~/.haywire/security.json, because splitting it was the defect
status: accepted
level: architectural
---

# The security document

## The defect

ADR 0027 gave two reasons the authentication roster could not be a settings
bag. The settings UI writes the **workspace tier**
(`<workspace>/.haywire/settings.json`), a per-project file that travels with
the project into git and onto other machines — so a panel that writes a
security decision commits that decision into a project. And the **global
tier** avoids that, but is hand-edit-only, so a settings bag would render
fields in the UI that silently do nothing when a human clicks them.

Both reasons apply verbatim to every network knob, and neither was applied.
`expose_to_network`, `allowed_remote_ranges`, `public_hostname`,
`trusted_proxies`, `ssl_certfile` and `ssl_keyfile` all lived on
`NetworkSettings`, an ordinary `FrameworkSettings` schema rendered by the
Network settings panel. `expose_to_network` was one checkbox in that panel,
and clicking it did exactly what ADR 0027 already warned a settings bag would
do: it wrote `<workspace>/.haywire/settings.json`, committing a machine's
exposure decision into a project file that ships to every collaborator, every
fork, and — if the `.haywire/` directory is not scrupulously gitignored —
every clone. A laptop opened once at a conference with the studio bound wide
leaves that fact sitting in source control, attached to the project rather
than the machine, indistinguishable from any other settings change in the
diff.

The roster got the special-case treatment ADR 0027 built for it. The rest of
the studio's exposure surface did not, because it predates that ADR and
nobody went back to apply the same reasoning to it. This document is that
application, generalized: not "auth is special," but "every control whose
correctness depends on which machine it runs on is special," and that
description covers the whole network surface, not just the roster.

## One document

`~/.haywire/security.json`, mode `0600`, three top-level blocks: `auth` (the
roster — principals, the enabled flag, session lifetime), `network`
(exposure, the peer allowlist, TLS paths, the proxy list), `farmhand`
(whether `/mcp` is mounted, and whether it restricts to loopback). One file,
one owner, one write path.

The invariants live inside `save_document`, not in each caller, and that
placement is the point rather than an implementation detail. "Authentication
is enabled but no admin exists," "TLS is half-configured," "the studio is
exposed with an empty allowlist" — these are not properties of the `auth`
block or the `network` block in isolation; they are properties of the
*document*, checked by reading more than one block at once. A CLI command
that validated only the block it was about to write could produce a document
that is individually plausible in every field and collectively broken —
exposed, authenticated with no admin, TLS half-configured — because nothing
ever looked at the whole thing together. Centralizing validation in
`save_document` means every writer, present or future, gets the same checks
for free and cannot forget to call them; a second validation path is a second
place for the rules to drift out of step with the one the studio actually
boots against.

This is also why the document is one file rather than three. Split across
`auth.json`, `network.json` and `farmhand.json`, "auth is enabled" and "the
studio is exposed" become independently editable facts, and every invariant
that spans them — "exposed implies authenticated," in particular — becomes a
cross-file check that some future write path can simply not perform, because
nothing forces it to open the other two files to validate the one it's
writing. As fields of one document behind one function, the invalid
combination is not a case the code has to catch; it is a state the format
cannot represent.

## Writes refuse, loads fail closed

`save_document` raises `SecurityError` on any invariant violation. There is
no way to write a security document that describes an unreachable studio as
if it were exposed and defended, or an exposed studio as if it required no
login. Every writer — `haywire network expose`, `haywire auth enable`, the
CLI in general — goes through this one function, so a bad state cannot enter
the file through code.

A hand-edited file is a different problem, and `sanitize` is a different
function for it. It runs once, at startup, against whatever
`load_document` returns, and it **never refuses to start**. A violation is
repaired in the safe direction — exposure off, TLS off, authentication off —
and every reason is logged at `CRITICAL`, reportable afterward with
`haywire security status`.

The asymmetry is deliberate, and it is ADR 0027's lockout reasoning applied
again rather than a new argument. That ADR rejected refusing to start on a
roster with authentication enabled and no admin, because a studio that will
not boot has taken away the only UI that could fix the roster that is
blocking it — the failure mode becomes unrecoverable without editing a JSON
file blind, on a machine that may not even be the one the operator is
sitting at. The security document generalizes the same shape to every field
in it: a corrupt or self-contradictory `security.json`, whether from a typo,
a bad merge, or an interrupted write, must degrade toward "nobody but this
machine can reach the studio and there is nothing to configure," never
toward "the studio refuses to exist until someone fixes a file by hand." The
API can refuse — that is what `save_document` is for, and it is the only
path a human interacting through the CLI or the UI ever takes. The boot path
cannot, because refusing there has no operator on the other end who agreed
to be locked out.

## Exposure is a verb

`expose_to_network` used to be a boolean field with a tooltip. Under the
document, there is no boolean to flip — `haywire network expose --ranges
<cidr>` is the only way to turn exposure on, and it is a function
(`haywire_studio.security.operations.expose`) that assembles a candidate
document and hands it to `save_document`, which is where the actual
enforcement lives.

A checkbox cannot express a precondition, and safe exposure has three:
authentication must already be on, TLS must already be configured, and the
allowlist must not be empty. A UI toggle can only be flipped; it cannot
refuse to flip until three other things are true first, short of disabling
itself with a tooltip explaining why — which is exactly the "hidden field
that does nothing" failure mode ADR 0027 already rejected, aimed at a
different control. `expose` is a verb specifically so that it can say no:
call it against a document with authentication off, or TLS unset, or no
`--ranges`, and `validate` rejects the write with a message naming the one
command that clears it. There is no state in which the flag reads `true`
in the file while one of its preconditions is false, because the write that
would have produced that state never completes.

`--ranges` is required, not merely recommended, for the same reason an empty
`allowed_remote_ranges` was already the correct-but-confusing default before
this change: `IPAllowlistMiddleware`'s membership check is `any(ip in
network for network in allowed_ranges)`, which over an empty sequence is
always `False`. Exposing the studio with no ranges configured does not open
it — it binds the socket wide and then rejects every remote peer at the
allowlist, which is real but is not what "expose" plausibly means to
someone typing the command. Requiring at least one range up front turns a
silent no-op into an immediate, explicit choice.

`haywire network seal` reverses the bind — the studio answers on loopback
again — and **keeps the allowlist**. Sealing is the temporary case: a laptop
leaving the venue, a demo that just ended, an operator who wants the studio
quiet for an hour. Discarding the ranges on seal would turn every return
trip into re-typing the same CIDR block, punishing the operator for doing
the safe thing. Exposure is the bit that decides whether the ranges matter
at all; while it is off, the ranges are inert and harmless to keep.

## The MCP rule

`/mcp` is mounted inside the same ASGI app the rest of the studio runs
under, behind `AuthGateMiddleware` (ADR 0027) exactly like every other route.
That gate demands a valid cookie or a valid bearer token whenever
authentication is on, and admits everyone when it is off. Two more facts
close the matrix completely. First, the document's own invariants require
`auth.enabled` before `network.exposed` can be `true` — the same check
described above. Second, the gate covers `/mcp` unconditionally, because it
wraps the whole app rather than exempting any one mount. Put together:
**exposed implies authenticated, and authenticated implies gated** — so
there is no reachable configuration in which `/mcp` is open to another
machine without a roster token.

That closure is what makes `require_auth`, `BearerTokenMiddleware`, and the
workspace `farmhand_token` file deletable rather than merely redundant. They
were a second, independent guard built for a world in which `/mcp` might be
reachable from off-box while the rest of the studio's authentication story
said nothing about it — a world where "is `/mcp` protected" had its own
answer, separate from "is the studio protected." Once exposure structurally
requires authentication, that second answer cannot diverge from the first
one, and a mechanism that exists only to prevent divergence between two
things that cannot diverge is not defence in depth — it is a second copy of
a rule, with its own file, its own credential, and its own chance to go
stale relative to the original. Deleting it removes a place the two stories
could disagree, not a layer of protection.

The `studio.json` sidecar (`write_identity` in
`haywire_studio/farmhand/identity.py`) carries an `auth_required` field,
mirroring `document.auth.enabled` at the moment the studio mounted
Farmhand. This is a **hint**, read by a later process — the farmhand4claude
proxy's startup script — deciding whether to attach an `Authorization`
header before it has made a single request. It is not, and must never
become, a credential: it says whether a token is expected, never what the
token is. A `studio.json` carrying a token would be the workspace-file
problem all over again — machine-and-session secret material committed
alongside project files — and the sidecar is already gitignored specifically
so that even the hint travels no further than this machine.

## `restrict_to_loopback` survives as a CLI-only control

Not everything network-shaped moved for the same reason. `restrict_to_loopback`
stays, on `FarmhandPolicy`, changed only by `haywire farmhand local-only` /
`allow-remote` — no settings panel ever rendered it and none does now.

It survives because it is not a network-location control at all, and
folding it into the exposure story would misdescribe what it does.
`IPAllowlistMiddleware` reads the TCP peer address, supplied by the kernel
and unforgeable by anything the client sends. `restrict_to_loopback`
configures the MCP SDK's `TransportSecuritySettings` to reject a request
whose `Host` or `Origin` **header** is not loopback — a value the client
sets, and can set to anything. `curl -H 'Host: 127.0.0.1:8124'
http://<lan-ip>:8124/mcp` sails straight through it, exactly as it did
before this document existed. What it defeats is narrower and specific: DNS
rebinding, where a malicious page already open in the operator's own
browser resolves an attacker-controlled domain to `127.0.0.1` after the
page loads, and then issues same-origin-looking requests that the browser
will happily attach cookies to. A header check is precisely the tool for
that attack, because a browser's `Host` header is the one signal in this
whole system that a browser sets honestly on its own requests — it is also
precisely the wrong tool for anything a peer-address or a bearer-token
check should be doing instead, which is why it stays scoped to exactly the
threat it answers.

Turning it off — `haywire farmhand allow-remote` — is a legitimate
operation, not a foot-gun disabled by omission: an MCP client running on
another machine needs the studio to accept a `Host` header that isn't
loopback, because from that client's perspective the studio's hostname
genuinely isn't `127.0.0.1`. `set_farmhand_loopback` demands that
authentication already be on before it allows this, and that check lives in
`operations.py` rather than in `validate`, deliberately. It constrains a
**transition** — you may not *turn off* loopback-restriction while
unauthenticated — not a **state**: a document that already has the
restriction off and authentication off is not corrupt, it's simply what
results when authentication is disabled afterward by someone who forgot
this was on, and refusing to *load* that document would be exactly the
lockout `sanitize` exists to avoid. `haywire security status` reports the
combination if it is ever reached by that path, rather than the load path
refusing to boot over it.

## What ADR 0026 keeps

Everything ADR 0026 calls "the layered model" is architecture, and none of
it moved. `IPAllowlistMiddleware` is still a pure-ASGI callable rather than
a `BaseHTTPMiddleware` subclass, for the same reason: NiceGUI's entire live
UI runs over Socket.IO after the initial page load, and a filter that only
sees `scope["type"] == "http"` would guard the login page and wave the
websocket carrying the actual application straight through. The
`X-Forwarded-For` rightmost-untrusted resolution is unchanged — XFF is
still read only when the direct TCP peer is itself a trusted proxy, still
scanned from the right to find the first hop the deployment didn't insert
itself. Loopback's unconditional exemption from the allowlist is unchanged
— `127.0.0.1`/`::1` still bypass the check before any list membership is
consulted, and there is still no way to configure that away, because doing
so would risk locking the operator out of the one UI that could undo the
mistake. jedi path confinement in `code_intelligence.py` is untouched.

What moved is *where the controls live*, not what they do or why. Every
field ADR 0026 described as living on `NetworkSettings` now lives on
`SecurityDocument.network`, read from `~/.haywire/security.json` instead of
`~/.haywire/settings.json`, changed through `haywire network` /
`haywire ssl` instead of a settings panel. The placement changed because
the placement was the defect this document fixes; the mechanism did not
change because nothing about the mechanism was wrong.

## Consequences

**Hard break, no migration.** A workspace's old `<workspace>/.haywire/settings.json`
`network` block, and a global `~/.haywire/settings.json` machine-wide
override, are both simply not read any more — `NetworkSettings` no longer
declares the fields that block would have populated. There is no
code path that copies an old value forward into `security.json`, and there
is deliberately no code path: a value that traveled into a workspace file is
exactly the thing this document exists to stop trusting. An operator who
relied on the old global-tier `public_hostname`/`trusted_proxies` pattern
must re-enter it through `haywire network expose --hostname ... --trusted-proxies ...`.

`NetworkSettings` keeps exactly one field: `port`. A port number is not a
security control — binding `8125` instead of `8124` exposes nothing that
`8124` didn't — so it is genuinely a local, project-agnostic convenience
with none of the reasons the rest of the schema had to leave.

The settings panel that used to render the network schema is now
**read-only and admin-gated** (`SecurityPanel`, `access=AccessTier.ADMIN`).
It shows the four-axis posture — network, auth, TLS, Farmhand — and every
finding `haywire security status` would print, with the fix command for
each one shown as copyable text, because the moment someone is reading this
panel with the studio running is exactly the moment they cannot paste that
fix command into the CLI that would apply it. `NetworkSettings` (just
`port`) is the only editable schema still rendered there.

**The farmhand4claude proxy must change, and this ADR does not change it.**
The proxy is a separate repository. It currently reads
`<ws>/.haywire/farmhand_token` lazily and attaches it as a bearer token; that
file no longer exists after this change. It must instead read
`auth_required` from `<ws>/.haywire/studio.json` and send no `Authorization`
header when that is `false`. Until the proxy ships that change, it will
attach no header at all — correct against an unauthenticated studio,
rejected with a `401` against an authenticated one. That is a coordinated,
cross-repo release, not a silent regression this plan can absorb by itself.

## Alternatives considered

**Hiding the fields instead of deleting them.** Keep `NetworkSettings`
declaring `expose_to_network` and friends, but stop rendering them in the
panel. Rejected: the workspace-tier JSON path stays open regardless of
whether a panel draws a checkbox for it. Anyone who writes
`<workspace>/.haywire/settings.json` by hand, via a script, or via a future
panel that forgets the memo, still commits an exposure decision into the
project. Hiding a field changes what the UI shows; it does not change what
the file format allows.

**A read-only setting kind in the settings system.** Add a schema-level
"admin can view, nobody can write through the UI" flavour, so
`NetworkSettings` could keep declaring these fields and the framework would
enforce their immutability. Rejected: this is a new concept in the settings
framework, built to solve a *placement* problem — these values belong to
the machine, not the project — that the settings system's tier model has no
notion of. Inventing framework machinery to make a wrong home look right is
solving the symptom; the actual fix is moving the data out of a system whose
tiers were never the right shape for machine-scoped, security-sensitive
state.

**`haywire mcp` instead of `haywire farmhand`.** Name the CLI subcommand
after the protocol rather than the component, on the theory that "MCP" is
what an operator searches for. Rejected on glossary consistency: the
glossary is explicit that "Farmhand" names the component and "MCP" names
the protocol it speaks, the same distinction `FarmhandHost`,
`farmhand://` resource URIs, and every other surface in this codebase
already draw. A CLI subcommand named for the protocol would be the one
place in the system using the wrong noun for what it configures.

**Refusing to start on a contradictory document.** Make the studio exit
rather than sanitize a document that fails `validate`. Rejected for the
reason given above under "Writes refuse, loads fail closed": a studio that
will not boot has taken away the only interface that could fix the file
that's blocking it. This is the same lockout argument ADR 0027 already
made for the roster specifically, generalized here to the whole document.

## References

- ADR 0026 — studio network exposure (bind address, peer allowlist, XFF
  resolution, jedi confinement) — superseded in part by this ADR
- ADR 0027 — studio authentication (the roster, the gate, the "not a
  settings bag" reasoning this ADR generalizes)
- `packages/haywire-studio/src/haywire_studio/security/document.py` —
  `SecurityDocument`, `validate`, `sanitize`, `load_document`, `save_document`
- `packages/haywire-studio/src/haywire_studio/security/operations.py` —
  `expose`, `seal`, `set_farmhand_loopback`, `write_tls_paths`
- `packages/haywire-studio/src/haywire_studio/security/posture.py` — the
  joined four-axis assessment behind `haywire security status`
- `packages/haywire-studio/src/haywire_studio/cli/networkcmd.py`,
  `securitycmd.py`, `farmhandcmd.py`, `authcmd.py`, `sslcmd.py`, `user.py`
- `packages/haywire-studio/src/haywire_studio/farmhand/identity.py` —
  `studio.json`, the `auth_required` hint
- `docs/guides/security.md` — the operator-facing guide this ADR backs
