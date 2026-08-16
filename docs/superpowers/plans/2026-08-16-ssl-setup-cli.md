---
status: implemented
feature: ssl-setup-cli
adr: docs/adr/0027-studio-authentication.md
see-also:
  - docs/guides/network_config.md
  - .insights/feedback_clipboard_secure_context.md
---

# `haywire ssl` — one-command TLS for a LAN studio — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a non-expert user a single command that generates a self-signed
certificate, configures `NetworkSettings.ssl_certfile` / `ssl_keyfile`, and
explains what the browser will do — plus the three follow-up verbs that keep
that certificate usable as the machine moves between networks.

**Architecture:** Mirrors the `roster.py` / `operations.py` split that slice 2
established for auth — a *material* module that owns the files on disk, a
*rules* module that owns the operations, and a thin `cli/` module that owns
argument parsing, prompting and exit codes. The CLI never contains crypto and
the crypto module never prints.

**Tech Stack:** `cryptography` (promoted from a transitive dep to a declared
one), `psutil` (already declared), stdlib `socket`/`json`/`argparse`.

## Motivation

Two problems, one fix.

1. **The clipboard is broken on every LAN studio today.** Per
   [.insights/feedback_clipboard_secure_context.md](../../../.insights/feedback_clipboard_secure_context.md),
   `navigator.clipboard` is `undefined` outside a secure context, so every
   `hui` copy button silently no-ops when the studio is reached over plain
   HTTP at a LAN address. Browsers gate this on secure context with **no
   override** — TLS is the only fix. This is a guaranteed, every-user,
   visible-today defect, and it is the primary justification for this work.
2. **Session cookies and passwords travel in cleartext on an exposed studio.**
   [login.py:126](../../../packages/haywire-studio/src/haywire_studio/auth/login.py#L126)
   sets `secure=request.url.scheme == "https"`, so over HTTP the cookie that
   *is* the identity is readable by anyone on the segment. On a home LAN this
   is a small risk; on an institutional network it is a real one, mostly
   because of password reuse and because `days=0` kiosk cookies never expire.

**Non-goal: making the browser warning disappear by itself.** Self-signed
certs produce a full-page interstitial on first visit. `ssl trust` exists to
resolve that, and every command that changes the certificate must say so.

## Settled decisions

Decided with the user before writing this plan; do not relitigate during
implementation.

| # | Decision | Rationale |
| --- | --- | --- |
| D1 | **Global tier** — cert lives in `~/.haywire/certs/`, settings written to `~/.haywire/settings.json` | TLS is a property of the machine's network identity, matching `auth.json` and `session_secret` which are already global |
| D2 | **Reuse `_guard_running_studio()`** | SSL settings are read once at startup ([app.py:357](../../../packages/haywire-studio/src/haywire_studio/app.py#L357)); changing them under a live studio yields a process whose behaviour contradicts its own config |
| D3 | **Self-signed only** | No external binary (`mkcert`), no public DNS + ACME. The honest fit for the documented LAN case |
| D4 | **`update` reuses the private key** | One `0600` key file, no orphaned key material; the operation is honestly "amend", not "start over" |
| D5 | **10-year validity** | The cert is generated once and trusted once; an annual expiry reintroduces the re-trust chore with no security benefit for a self-signed LAN cert |
| D6 | **`.local` mDNS name is the primary SAN** | It follows the machine between networks, which is what makes one cert work at home *and* at the university without regeneration |
| D7 | **Opt-in; never a default or a nag** | Loopback users need nothing. No startup prompt, no banner |

## Global Constraints

- Line length 109; `uv run ruff check .` **and** `uv run ruff format --check .` must both pass.
- `uv run mypy` must pass for every path in the CLAUDE.md mypy command.
- **One new declared dependency:** `cryptography` on `haywire-studio`. It is
  already installed transitively via `pyjwt[crypto]`, but relying on another
  package's extra breaks on a consumer install.
- The private key is `0600`. Every write is atomic (temp file + `chmod` +
  `os.replace`), matching [roster.py:184-192](../../../packages/haywire-studio/src/haywire_studio/auth/roster.py#L184-L192).
- **No command may run `sudo` or modify the OS trust store.** `ssl trust`
  prints the platform command; the user runs it.
- Settings are written by **direct JSON merge**, never by constructing a
  `SettingsRegistry()` — see
  [project_settings_registry_construction_side_effects.md](../../../.insights/project_settings_registry_construction_side_effects.md):
  building one repoints `FrameworkSettings._registry` and drains the
  pending-global queue.

## Command surface

```
haywire ssl setup     # first run — new key + cert, write settings, explain
haywire ssl update    # cert exists — same key, new cert (--add/--remove/--refresh)
haywire ssl status    # what's covered, what's reachable here, is it trusted
haywire ssl trust     # print the platform command to trust the cert
```

`setup` refuses when a cert already exists and points at `update`; `update`
refuses when none exists and points at `setup`. Each verb's precondition is
the other's postcondition, so neither can silently destroy work.

---

### Task 0: Baseline

**Files:**
- Read: `packages/haywire-studio/src/haywire_studio/cli/__init__.py`
- Read: `packages/haywire-studio/src/haywire_studio/cli/authcmd.py`
- Read: `packages/haywire-studio/src/haywire_studio/auth/roster.py`

- [ ] **Step 1: Establish a clean baseline** (CLAUDE.md pre-edit baseline — this is a multi-file change)

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/
uv run mypy packages/haywire-studio/src/
```

Both must be clean before starting. If not, stop and raise it with the user.

- [ ] **Step 2: Confirm the shape to mirror** — `authcmd.py` exposes
      `register(subparsers)`, handlers take a `Namespace` and return an exit
      code, and never call `sys.exit`.

---

### Task 1: Declare the `cryptography` dependency

**Files:**
- Edit: `packages/haywire-studio/pyproject.toml`

- [ ] **Step 1:** Add `"cryptography>=42"` to the `dependencies` list.
- [ ] **Step 2:** `uv sync` and confirm the lock updates with no version change
      (49.0.0 is already resolved transitively).
- [ ] **Step 3:** Confirm `cryptography` needs no mypy override — it ships
      type hints. Do **not** add it to the `pyproject.toml` override list
      unless mypy actually complains.

**Verify:** `uv run mypy packages/haywire-studio/src/` still clean.

---

### Task 2: `network/names.py` — what this machine is reachable as

A pure, dependency-light module. No crypto, no files, no printing — it answers
one question: *which names and addresses should a certificate for this machine
cover?* Separated so it is testable without generating a key.

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/network/names.py`
- Create: `tests/network/test_names.py`

- [ ] **Step 1: Write the failing test first.**

```python
def test_local_names_always_includes_loopback():
    names = local_names()
    assert "localhost" in names.dns
    assert "127.0.0.1" in names.ip
```

- [ ] **Step 2: Implement `local_names()`** returning a frozen
      `LocalNames(dns: tuple[str, ...], ip: tuple[str, ...])`.

DNS names to collect:
- `localhost` (always)
- `socket.gethostname()` — bare, e.g. `MB-41545`
- the `.local` mDNS form: `hostname.split(".")[0] + ".local"` — **D6, the one
  that survives a network change**
- `socket.getfqdn()` when it differs from the hostname and contains a `.`

IP addresses to collect:
- `127.0.0.1` and `::1` (always)
- every non-loopback address from `psutil.net_if_addrs()`, IPv4 and IPv6

**Two traps found while researching this plan — both must be handled:**

1. **`socket.getaddrinfo(socket.gethostname())` raises on macOS.** Verified on
   the dev machine: `[Errno 8] nodename nor servname provided`. It is a common
   idiom and it is wrong here. Use `psutil.net_if_addrs()` for enumeration.
2. **Link-local IPv6 addresses carry a zone suffix** (`fe80::1%en0`). A `%`
   in a SAN is invalid. Strip the zone, and skip `fe80::/10` entirely — a
   link-local address is not a useful way to reach a studio.

- [ ] **Step 3: Implement `primary_address()`** — the address the machine
      would use to reach the outside world, for `ssl status` to report "you
      are reachable here as X". Use the UDP-connect trick (verified working):

```python
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))   # no packet is sent; this only picks a route
addr = s.getsockname()[0]
```

Must return `None` cleanly when there is no route (verified: raises
`[Errno 65] No route to host` on a machine with no IPv6 route). Never let this
raise — a status command on an offline laptop must still print.

**Verify:** `uv run pytest tests/network/test_names.py`

---

### Task 3: `network/certs.py` — the certificate material

Owns the two files on disk and the crypto. Knows nothing about settings, the
CLI, or printing. This is the `roster.py` of this feature.

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/network/certs.py`
- Create: `tests/network/test_certs.py`

- [ ] **Step 1: Paths and a `CertError`.**

```python
CERT_DIR = Path.home() / ".haywire" / "certs"      # honours a path arg for tests
CERT_FILENAME = "studio.crt"
KEY_FILENAME = "studio.key"
```

Every public function takes an optional `dir: Path | None = None` so tests
never touch the real `~/.haywire`, matching `load_roster(path=None)`.

- [ ] **Step 2: `generate_key()`** — RSA 2048. Chosen over EC for maximum
      compatibility with older clients on a mixed LAN; the performance
      difference is irrelevant at studio traffic volumes.

- [ ] **Step 3: `write_key(key, dir)`** — atomic + `0600`, exactly the
      [roster.py](../../../packages/haywire-studio/src/haywire_studio/auth/roster.py#L184-L192)
      pattern: write temp, `chmod`, `replace`. **Chmod before the rename** so
      the key is never briefly world-readable.

- [ ] **Step 4: `sign_cert(key, names, *, years=10)`** — build the
      certificate. Requirements, each of which is a real failure mode:

  - **Every name goes in the SAN extension.** A CN-only cert is rejected by
    every current browser. `x509.DNSName` for names, `x509.IPAddress` for
    addresses (wrapped in `ipaddress.ip_address`).
  - `basic_constraints` CA=True, self-signed, `key_cert_sign` — so the cert
    can be imported into a trust store as its own root.
  - `subject == issuer` (self-signed by definition).
  - `not_valid_before` **backdated 1 hour** — clock skew between the studio
    machine and a phone on the same LAN otherwise produces a
    `NET::ERR_CERT_NOT_YET_VALID` that looks like a broken command.
  - `not_valid_after` = now + `years` (D5).

- [ ] **Step 5: `write_cert(cert, dir)`** — `0644`, atomic. The certificate is
      public material; only the key is secret.

- [ ] **Step 6: Readers** — `load_cert(dir)`, `cert_names(cert) -> LocalNames`
      (parse the SAN extension back out), `cert_expiry(cert)`,
      `fingerprint(cert)` (SHA-256, colon-separated hex, the format every OS
      tool displays).

- [ ] **Step 7: `key_matches_cert(key, cert)`** — compare public numbers.
      Guards the `update` path: a key/cert pair that has drifted apart
      produces a uvicorn startup failure whose message names neither file.

**Tests** (all against a `tmp_path`, never `~`):
- generated cert contains every requested DNS name and IP in its SANs
- key file mode is `0o600`; cert file mode is `0o644`
- `not_valid_before` is in the past
- round-trip: `cert_names(load_cert(...))` equals what was passed to `sign_cert`
- `key_matches_cert` is True for a real pair, False for two independent keys
- an IPv6 name with a `%zone` suffix is rejected or stripped, never written raw

**Verify:** `uv run pytest tests/network/test_certs.py`

---

### Task 4: `network/tls_settings.py` — writing the two settings

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/network/tls_settings.py`
- Create: `tests/network/test_tls_settings.py`

- [ ] **Step 1: `write_tls_paths(certfile, keyfile, *, path=None)`** — merge
      into `~/.haywire/settings.json`.

The file format is a plain nested document; the two keys land as:

```json
{ "network": { "ssl_certfile": { "value": "/…/studio.crt" },
               "ssl_keyfile":  { "value": "/…/studio.key" } } }
```

**Constraints — the first is the trap:**
- **Never construct a `SettingsRegistry()`.** Read the JSON, merge two keys,
  write it back. Constructing a registry repoints `FrameworkSettings._registry`
  and drains the global pending queue.
- **Preserve every other key.** The user's real file already holds
  `expose_to_network`, `allowed_remote_ranges`, `public_hostname` and
  `trusted_proxies`. Clobbering them is the worst outcome this feature could
  produce. Read-modify-write, never write-fresh.
- Atomic write. A truncated `settings.json` is a studio that will not start.
- A missing or unparseable file is **not** silently replaced — an unparseable
  file raises, so a user with a hand-edited typo is told, not overwritten.

- [ ] **Step 2: `read_tls_paths(path=None)`** — returns the configured pair,
      for `status`.

**Tests:**
- an existing `network` block with four unrelated keys survives a write
- unrelated top-level namespaces survive
- unparseable JSON raises rather than overwriting
- writing twice is idempotent

**Verify:** `uv run pytest tests/network/test_tls_settings.py`

---

### Task 5: `network/tls_operations.py` — the rules

The `operations.py` of this feature: composes names + certs + settings into
the four operations, raising `CertError` with a user-facing message. Still no
printing.

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/network/tls_operations.py`
- Create: `tests/network/test_tls_operations.py`

- [ ] **Step 1: `setup(extra_names, *, dir=None, settings_path=None)`**
  - **if a cert exists AND settings point at it** → refuse:
    `"A certificate already exists. Use 'haywire ssl update' to change it."`
  - **if a cert exists but settings do NOT point at it** (`ORPHANED`) → do
    **not** refuse and do **not** regenerate. Write the settings to adopt the
    existing pair and say so. This happens when someone hand-edits
    `settings.json` after a successful setup; regenerating would silently
    invalidate a certificate the user has already trusted on other machines,
    which is the worst available outcome. Adopting is both the safe action and
    the one the user meant.
    Chosen over a `--use-existing` flag: the situation is unambiguous, so
    inferring it beats making the user name it.
  - collect `local_names()`, merge `extra_names`, merge `public_hostname` from
    settings if set (strip any `:port` — a SAN is a host, never a host:port)
  - generate key, sign cert, write both, write settings
  - return a result object naming what was covered, so the CLI can print it

- [ ] **Step 2: `update(*, add=(), remove=(), refresh=False, dir=None)`**
  - refuse if no cert exists → point at `setup`
  - start from the **existing cert's** SAN list (D4 — amend, don't rebuild)
  - `--refresh` re-derives `local_names()` and unions it in, preserving
    manually-added names. This is the home↔university command.
  - `--remove` drops names; loopback names are **not removable** (a cert that
    cannot serve `localhost` breaks the default case)
  - **reuse the existing private key** (D4); verify `key_matches_cert` first
  - re-sign, write cert only — the key file is untouched
  - settings already point at the same paths, so no settings write is needed

- [ ] **Step 3: `status(*, dir=None, settings_path=None)`** — a pure data
      gatherer returning: cert exists, covered names, expiry, fingerprint,
      configured-in-settings, `expose_to_network`, `primary_address()` and
      whether it is covered.
      **No trust-store probing** — that is genuinely hard to do portably and
      wrongly reporting "trusted" is worse than not reporting it. Report what
      the files say and let `trust` speak for itself.

  `status` must classify into exactly one of these states, because each has a
  different next action. This is the whole value of the command — a user who
  runs it is asking "am I OK?", and every state below answers differently.

  | State | Condition | Next action |
  | --- | --- | --- |
  | `OFF_LOOPBACK` | no TLS, `expose_to_network` off | none — this is fine |
  | `OFF_EXPOSED` | no TLS, exposed | `ssl setup` |
  | `OK` | configured, files valid, current address covered | `ssl trust` if not yet trusted |
  | `NOT_COVERED` | configured, current address not in SANs | `ssl update --refresh` |
  | `FILE_MISSING` | settings point at a nonexistent file | `ssl setup`, or clear the settings |
  | `HALF_CONFIGURED` | exactly one of the pair set | set both or neither |
  | `ORPHANED` | cert on disk, settings empty | `ssl setup` (adopts it — see Step 1) |
  | `KEY_MISMATCH` | key does not match cert | `ssl setup` to regenerate |
  | `EXPIRING` | valid < 30 days | `ssl update --refresh` |

  **`OFF_LOOPBACK` is a success, not a warning** (D7). Loopback-only is a
  correct configuration; telling that user they have a problem trains them to
  ignore the command. Every state returns exit `0` — `status` reports, it does
  not judge.

  Four of these (`FILE_MISSING`, `HALF_CONFIGURED`, `KEY_MISMATCH`, and a
  cert that cannot be parsed) are the exact conditions
  [`_ssl_kwargs()`](../../../packages/haywire-studio/src/haywire_studio/app.py#L467)
  hard-exits the studio on. Catching them in a read-only command is strictly
  better than at boot, so `status` must diagnose them in the **same words** the
  startup error uses — a user who sees both should not think they are two
  different problems.

- [ ] **Step 4: `trust_command(dir=None)`** — return the platform-appropriate
      command string. **Never execute it** (Global Constraints).

```
macOS:   sudo security add-trusted-cert -d -r trustRoot \
             -k /Library/Keychains/System.keychain <cert>
Linux:   sudo cp <cert> /usr/local/share/ca-certificates/haywire-studio.crt \
             && sudo update-ca-certificates
Windows: Import-Certificate -FilePath <cert> -CertStoreLocation Cert:\LocalMachine\Root
```

**Tests:**
- `setup` twice → second raises, first cert untouched
- `update --add` preserves existing names and the key file's bytes
- `update --refresh` unions local names without dropping manual ones
- `update --remove localhost` refuses
- `setup` merges `public_hostname` from settings, with the port stripped
- `update` on a mismatched key/cert pair raises a message naming both files

**Verify:** `uv run pytest tests/network/test_tls_operations.py`

---

### Task 6: `cli/sslcmd.py` — parsing, prompting, exit codes

Named `sslcmd.py` to match `authcmd.py`'s dodge around a stdlib name clash
(`ssl` is a stdlib module; a sibling named `ssl.py` inside a package that also
imports `ssl` transitively is a trap not worth setting).

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/cli/sslcmd.py`
- Edit: `packages/haywire-studio/src/haywire_studio/cli/__init__.py`
- Create: `tests/test_ssl_cli.py`

- [ ] **Step 1: `register(subparsers)`** with the four sub-actions.

```
haywire ssl setup  [--also NAME ...] [--dir PATH]
haywire ssl update [--add NAME ...] [--remove NAME ...] [--refresh]
haywire ssl status
haywire ssl trust
```

`--dir` is the test seam, documented as "mainly for testing" exactly like
`--roster`.

- [ ] **Step 2: Guard `setup` and `update` with `_guard_running_studio()`** (D2).

This currently lives in `authcmd.py` as a private function. **Move it** to a
shared home — `cli/_guards.py` — and have `authcmd.py` import it. Do not
copy-paste it; two copies will drift. Per CLAUDE.md, grep for callers before
moving: it is used twice in `authcmd.py` (`_enable`, `_disable`).

`status` and `trust` are read-only and must **not** be guarded — asking a user
to quit the studio to find out why HTTPS is broken is backwards.

- [ ] **Step 3: Output.** The command's whole reason to exist is that users
      don't understand this topic, so the printing is the feature, not
      decoration. `setup` must end with:

```
Certificate created and configured.

  Covers:  localhost, 127.0.0.1, ::1, MB-41545.local, 192.168.1.47
  Expires: 2036-08-16
  Key:     ~/.haywire/certs/studio.key   (private — never share this file)

Restart the studio, then visit https://… (note the s).

Your browser will show a warning the first time — "not private", or
"unknown issuer". That is expected: the certificate is signed by this
machine rather than by a company browsers already trust. The connection
is fully encrypted either way.

  To make the warning go away:  haywire ssl trust
  To use it as-is:              click "Advanced" and continue
```

Honest, specific, and it pre-empts the support question. `update` must print
the equivalent **re-trust warning**:

```
Certificate updated (the private key was reused).

Anyone who ran 'haywire ssl trust' must run it again — trust stores
pin the certificate, and this is a new one.
```

- [ ] **Step 4: `status` output — one message per state.** The table in Task 5
      Step 3 lists nine; each prints what is true, then the single next command.
      Two matter most.

`OFF_EXPOSED` — the actionable one. Naming the clipboard is what makes this
land, because it is the symptom the user has already hit and not understood:

```
TLS is not configured — the studio serves plain HTTP.

  Reachable at:      10.244.138.229, MB-41545.local
  expose_to_network: on

Two consequences right now:
  - Passwords and session cookies travel unencrypted on your network.
  - Copy buttons in the studio do not work (browsers disable the
    clipboard outside a secure context).

  Fix both:  haywire ssl setup
```

`NOT_COVERED` — the home↔university case. The final note is the payoff of the
`.local` SAN (D6): often **no action is needed at all**, and saying so beats
making the user re-run a command:

```
TLS is configured, but does not cover this network.

  Covers:            localhost, 127.0.0.1, ::1, MB-41545.local, 192.168.1.47
  Reachable here as: 10.244.138.229 — NOT covered

Browsers will reject the certificate at this address even if you
have trusted it before.

  Add this network:  haywire ssl update --refresh

  Note: MB-41545.local IS covered — if mDNS works on this network,
  https://MB-41545.local:8124 works right now with no change.
```

`OFF_LOOPBACK` states plainly that nothing is wrong and stops. No fix, no
warning glyph, no colour.

- [ ] **Step 5: Register** — add `sslcmd` to the `SUBCOMMANDS` tuple in
      `cli/__init__.py` and to the module docstring's count if it names one.

**Tests** (mirror `tests/test_auth_cli.py`'s style — patch the guard, run the
handler, assert on exit code and captured stdout):
- `setup` on a clean dir returns 0 and creates both files
- `setup` twice returns non-zero and prints the "use update" hint
- `update` with no cert returns non-zero and prints the "use setup" hint
- both `setup` and `update` refuse while the studio is running
- `status` and `trust` **succeed** while the studio is running
- `setup` output contains the browser-warning explanation
- `update` output contains the re-trust warning
- `setup` on an orphaned cert adopts it: settings written, **cert bytes
  unchanged** (assert the file hash is identical — this is the "never silently
  invalidate a trusted cert" guarantee)
- `status` returns exit `0` in every one of the nine states
- `OFF_LOOPBACK` output contains no fix command and no warning wording
- `OFF_EXPOSED` output mentions the clipboard
- `NOT_COVERED` output names a covered `.local` alternative when one exists

**Verify:** `uv run pytest tests/test_ssl_cli.py`

---

### Task 7: Point the existing surfaces at the new commands

Three places already tell the user about this problem in the vocabulary of
hand-edited settings. Each becomes a command.

**Files:**
- Edit: `packages/haywire-studio/src/haywire_studio/app.py`
- Already done (2026-08-16, ahead of this plan): `packages/haywire-studio/src/haywire_studio/init.py`

- [ ] **Step 1: Startup warning names the command.**
      [app.py:373-378](../../../packages/haywire-studio/src/haywire_studio/app.py#L373-L378)
      currently ends `"Set ssl_certfile/ssl_keyfile, or terminate TLS at a
      reverse proxy."` — which is the hand-editing instruction this whole
      feature exists to remove. Replace with `"Run 'haywire ssl setup' to
      serve HTTPS, or terminate TLS at a reverse proxy."`

- [ ] **Step 2: `_ssl_kwargs` errors name the diagnostic command.** The two
      hard-exit messages at
      [app.py:483](../../../packages/haywire-studio/src/haywire_studio/app.py#L483)
      and [app.py:491](../../../packages/haywire-studio/src/haywire_studio/app.py#L491)
      should end with `"Run 'haywire ssl status' to see the current state."`
      These are `HALF_CONFIGURED` and `FILE_MISSING` — the same states `status`
      classifies, so the wording must match (Task 5 Step 3).

- [ ] **Step 3: `haywire init` next-steps block — already landed.** The
      scaffold now prints, after the publish block:

```
Check your current security exposure:
  uv run haywire auth status   # who may connect
  uv run haywire ssl status    # whether traffic is encrypted
```

  Unconditional by explicit decision — it runs before any network setting
  exists, so it cannot branch on `expose_to_network`, and the point is
  discoverability rather than a warning. This is the one place in the feature
  that mentions TLS without being asked; it is a menu line, not a nag, and
  `ssl status` on a fresh loopback install answers "nothing to do" (D7).

  **Note for the implementer:** no test asserts on this block; verified at
  plan time. Adding one is optional — but if you touch the wording, grep
  `tests/test_init_cli.py` first in case that changed.

---

### Task 8: Documentation

**Files:**
- Edit: `docs/guides/network_config.md`
- Edit: `.insights/feedback_clipboard_secure_context.md`

- [ ] **Step 1:** Add a `## 9. Serving HTTPS` section to the network guide.
      The two settings are currently documented as bare paths the user must
      produce somehow; this section makes `haywire ssl setup` the answer.
      Cover: what the command does, the browser warning and why, `ssl trust`,
      and the home↔university story with `ssl update --refresh`.

- [ ] **Step 2:** Update the settings table in §2 — it says "five settings"
      and lists five; `ssl_certfile`/`ssl_keyfile` are missing from it
      entirely. Add them and fix the count, or the table contradicts the new
      section.

- [ ] **Step 3:** Point the clipboard insight at the fix. It currently
      describes the trap and says configuring the two settings resolves it;
      add the one-line command that now does that.

- [ ] **Step 4:** Follow `docs/reference/doc-authoring.md` for front matter and
      nav wiring. No new nav entry is needed — this extends an existing page.

---

### Task 9: Full verification

- [ ] **Step 1:** `uv run ruff check .` **and** `uv run ruff format --check .`
      — both, per CLAUDE.md; CI runs both and they catch disjoint problems.
- [ ] **Step 2:** `uv run mypy` over every path in the CLAUDE.md command.
- [ ] **Step 3:** Full gate: `uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"`
- [ ] **Step 4: Manual end-to-end** — the part no test covers, because the
      thing being verified is a browser's behaviour:
  1. `uv run haywire ssl setup`
  2. start the studio, visit `https://<lan-ip>:8124` from another device
  3. confirm the interstitial appears and can be clicked through
  4. **confirm a `hui` copy button now works** — this is the motivating defect
  5. `uv run haywire ssl status` reports the address you used as covered
  6. **`OFF_LOOPBACK` sanity check** — with `expose_to_network` off and the
     two settings cleared, `ssl status` must read as "nothing to do" to
     someone who has never seen it. If it reads as a warning, the wording is
     wrong (D7). This is a judgement call no assertion can make, which is why
     it is here rather than in the test suite.
- [ ] **Step 5:** Fill in the Drift Log below and flip `status:` to `implemented`.

---

## Risks

| Risk | Handling |
| --- | --- |
| Clobbering a user's `settings.json` | Read-modify-write + atomic + unparseable-raises (Task 4). The most damaging possible failure; tested explicitly |
| Key file briefly world-readable | `chmod` before `replace`, per the roster pattern (Task 3 Step 3) |
| Cert invalid on a second network | `.local` SAN (D6) + `update --refresh`; documented in Task 7 |
| User thinks `update` re-trusts automatically | Mandatory re-trust warning in `update` output (Task 6 Step 3) |
| `getaddrinfo` idiom silently fails on macOS | Verified failing on the dev machine; `psutil` used instead (Task 2) |
| Clock skew → `ERR_CERT_NOT_YET_VALID` | Backdate `not_valid_before` by 1 hour (Task 3 Step 4) |

## Out of scope

- `mkcert` / ACME / real CA integration (D3)
- Executing trust-store changes (`sudo`) on the user's behalf
- Any UI surface — this is CLI-only; a settings-panel button is a later question
- Auto-renewal, expiry warnings at startup, or any nag (D7)
- Making the studio prefer HTTPS or redirect HTTP→HTTPS

## Drift Log

Implemented 2026-08-16. Deviations from the plan as written:

1. **`_guards.py` exposes `guard_running_studio(subject)`, and `authcmd.py`
   keeps its private wrappers.** The plan said to move the guard and have
   `authcmd` import it. `tests/test_auth_cli.py` patches
   `authcmd._studio_is_running` by name, so removing that module-level name
   would have broken two passing tests for no gain. `authcmd._studio_is_running`
   is now a one-line delegate to the shared implementation; there is still only
   one copy of the logic. The guard takes a *subject* string so its message can
   name what is read at startup ("Authentication" / "TLS configuration").

2. **`status` gained a tenth state, `UNREADABLE`.** The plan listed nine. A
   certificate file that exists but does not parse is a distinct condition from
   `FILE_MISSING`, and it is one of the states that stops the studio booting, so
   it needed its own message rather than falling through to a generic branch.

3. **`setup --use-existing` was not added.** The plan already leaned this way;
   confirmed during implementation. The orphaned-certificate case is detected
   and adopted automatically, guarded by a test asserting the certificate bytes
   are unchanged.

4. **Type annotations use `Iterable[str] | None`, not `object`.** The first
   draft used `object` for the repeatable-name parameters, which mypy correctly
   rejected as non-iterable. No behaviour change.

5. **Docs: the settings table said "five settings" and listed five.** Adding
   `ssl_certfile`/`ssl_keyfile` made it seven, which changed the heading and
   therefore broke three in-page anchors (`#2-the-five-settings`). All three
   were updated. The plan anticipated the count fix but not the anchor fallout.

### Verification performed

- `uv run ruff check .` — clean.
- `uv run ruff format --check` — clean over every file this work touched.
  (Two files unrelated to this work, `haywire/core/farmhand/identity.py` and
  `haywire/ui/editor/identity.py`, were already unformatted in the working tree
  before this session and were left alone.)
- `uv run mypy` over the full CLAUDE.md path list — `Success: no issues found
  in 1109 source files`.
- `uv run pytest -m "not browser and not perf"` — **3942 passed, 3 failed**.
  The three failures are in `tests/test_auth_cli.py` and are **pre-existing**:
  verified identical on a stashed working tree before any of this work.
  `authcmd._offer_token_import` calls `input()` through an unpatched
  `_confirm`, which raises under pytest's capture whenever the repo has a real
  `.haywire/farmhand_token` — as this one does. Environment-dependent, unrelated
  to TLS, and out of scope here.
- **New tests: 121 passing** across `tests/studio/test_network/` (names, certs,
  tls_settings, tls_operations) and `tests/test_ssl_cli.py`.

### Manual end-to-end (Task 9 Step 4)

Run against a throwaway `HOME`, so nothing touched the real `~/.haywire`:

- `ssl status` on a clean loopback install printed the `OFF_LOOPBACK` text with
  no fix command and no warning wording — the D7 readability check.
- `ssl setup` covered `localhost, MB-41545, MB-41545.local, 127.0.0.1, ::1,
  10.244.138.229`; key `0600`, certificate `0644`.
- **OpenSSL confirmed the material independently**: SAN list as above,
  `CA:TRUE`, `Not Before` 08:47:54 against a 09:47 generation time (the 1-hour
  skew backdate), expiry 2036, and the key/certificate public keys identical.
- **A real uvicorn server was started with the generated pair.** `curl` without
  the certificate failed with exit 60 (certificate verify failed); `curl
  --cacert <the certificate>` returned the body and exit 0. This is the
  end-to-end proof that the pair serves genuine TLS and that trusting the
  certificate is what resolves the warning.
- `ssl update --add 192.168.1.99` left the key file's SHA-256 unchanged while
  the certificate's changed, and printed the re-trust warning.

**Not verified by machine:** that a browser's clipboard returns over the new
HTTPS origin. That needs a second device pointed at a LAN-exposed studio and is
the one item from Task 9 Step 4 left for the author.
