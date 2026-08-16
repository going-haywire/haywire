# Security Document + CLI-Only Network Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every startup-read security control out of the settings system into one CLI-owned document at `~/.haywire/security.json`, so exposing the studio becomes a verb with enforced preconditions instead of a checkbox in a panel that writes a git-tracked project file.

**Architecture:** A new `haywire_studio.security` package owns one 0600 JSON document holding three blocks — `auth` (the existing roster), `network` (bind/allowlist/TLS), `farmhand` (MCP switches). Every write goes through `save_document()`, which runs `validate()`; the invariants therefore cannot be forgotten by a new caller. The settings system keeps exactly one network field (`port`). The settings panel becomes a read-only posture report rendering the same `Posture` object the CLI prints. The workspace Farmhand token is deleted outright: `/mcp` requires a roster token iff auth is enabled, and the invariant `exposed ⇒ auth enabled` closes the matrix so no configuration exists where `/mcp` is reachable off-box without a token.

**Tech Stack:** Python 3.12, stdlib only for the document (`json`, `os`, `dataclasses`, `ipaddress`). NiceGUI for the panel. pytest. No new dependencies.

## Global Constraints

- **Hard break, no migration, no backwards compatibility.** `~/.haywire/auth.json` is not read, not detected, not migrated. `SECURITY_VERSION = 1`.
- **`SecurityError` is the only exception type** for this feature. `RosterError` is deleted; every catch site becomes `SecurityError`.
- **Writes refuse, loads fail closed.** `save_document()` raises on an invariant violation. `sanitize()` downgrades a hand-edited violation to the safe value and returns reasons — it never refuses to start the studio.
- **Atomic 0600 writes.** Temp file in the same directory, `chmod(0o600)` before `os.replace`.
- **Line length 109** (`ruff` config). Run `uv run ruff check .` **and** `uv run ruff format --check .` before every commit — CI runs both.
- **`uv run mypy` must stay clean** on `packages/haywire-studio/src/`. Establish the baseline before Task 1.
- CLI vocabulary is **`haywire farmhand`**, not `haywire mcp` — the codebase calls it Farmhand everywhere (glossary, `FarmhandHost`, `farmhand://` URIs). "MCP" stays the protocol noun in help text.
- Every setting removed from a `FrameworkSettings` bag must be removed from the bag, not merely hidden. A hidden field is still writable via the workspace-tier JSON.

## Pre-Flight

- [ ] **Establish the baseline** (do this before Task 1, record the output):

```bash
uv run ruff check packages/haywire-studio/src/ barn/haybale-studio/
uv run ruff format --check packages/haywire-studio/src/ barn/haybale-studio/
uv run mypy packages/haywire-studio/src/
uv run pytest tests/auth/ tests/farmhand/ tests/studio/test_network/ tests/test_auth_cli.py -q
```

Expected: all clean, all pass. If anything already fails, stop and raise it with the user — do not start on a dirty tree.

---

## File Structure

**Created**

| Path | Responsibility |
| --- | --- |
| `packages/haywire-studio/src/haywire_studio/security/__init__.py` | Package marker |
| `packages/haywire-studio/src/haywire_studio/security/errors.py` | `SecurityError` alone — no imports, so nothing can cycle through it |
| `packages/haywire-studio/src/haywire_studio/security/roster.py` | `Principal`, `Roster` — pure model, no file I/O (moved from `auth/roster.py`) |
| `packages/haywire-studio/src/haywire_studio/security/document.py` | `SecurityDocument`, `NetworkPolicy`, `FarmhandPolicy`, `security_path`, `load_document`, `save_document`, `validate`, `sanitize` |
| `packages/haywire-studio/src/haywire_studio/security/operations.py` | Network + Farmhand rules: `expose`, `seal`, `set_farmhand_enabled`, `set_farmhand_loopback`, `write_tls_paths` |
| `packages/haywire-studio/src/haywire_studio/security/posture.py` | `Severity`, `Finding`, `Posture`, `assess`, `assess_document` (moved from `network/security.py`) |
| `packages/haywire-studio/src/haywire_studio/cli/networkcmd.py` | `haywire network expose\|seal\|status` |
| `packages/haywire-studio/src/haywire_studio/cli/farmhandcmd.py` | `haywire farmhand enable\|disable\|local-only\|allow-remote\|status` |
| `docs/adr/0028-security-document.md` | The decision record |
| `docs/guides/security.md` | The user guide, absorbing `network_config.md` |
| `tests/security/__init__.py`, `tests/security/test_document.py`, `tests/security/test_operations.py`, `tests/security/test_posture.py` | Tests for the new package |
| `tests/test_network_cli.py`, `tests/test_farmhand_cli.py` | Tests for the new subcommands |

**Deleted**

| Path | Why |
| --- | --- |
| `packages/haywire-studio/src/haywire_studio/auth/roster.py` | Model moves to `security/roster.py`; I/O moves to `security/document.py` |
| `packages/haywire-studio/src/haywire_studio/network/security.py` | Moves to `security/posture.py` (avoids a `network.security` / `security` near-collision) |
| `packages/haywire-studio/src/haywire_studio/network/tls_settings.py` | Its whole reason for existing — hand-rolled JSON to dodge `SettingsRegistry` side-effects, plus `workspace_overrides()` warning that the settings UI silently beats the CLI — evaporates when TLS leaves the settings system |
| `packages/haywire-studio/src/haywire_studio/farmhand/settings.py` | Both fields move to `FarmhandPolicy` |
| `tests/farmhand/test_farmhand_settings_unit.py` | Tests a deleted class |
| `tests/farmhand/test_network_settings_unit.py` | Tests deleted fields |
| `tests/studio/test_network/test_tls_settings.py` | Tests a deleted module |

**Modified**

| Path | Change |
| --- | --- |
| `packages/haywire-studio/src/haywire_studio/network/settings.py` | Reduced to `port` alone |
| `packages/haywire-studio/src/haywire_studio/network/tls_operations.py` | Reads/writes the document instead of `tls_settings` |
| `packages/haywire-studio/src/haywire_studio/farmhand/auth.py` | `ensure_token`, `TOKEN_FILENAME`, `BearerTokenMiddleware` deleted; `connection_command` kept |
| `packages/haywire-studio/src/haywire_studio/farmhand/host.py` | Reads `FarmhandPolicy`; no bearer middleware |
| `packages/haywire-studio/src/haywire_studio/farmhand/identity.py` | Sidecar gains `auth_required` |
| `packages/haywire-studio/src/haywire_studio/auth/operations.py` | Same rules, document I/O, `SecurityError` |
| `packages/haywire-studio/src/haywire_studio/auth/live.py` | `RosterCache` reads the document's `auth` block |
| `packages/haywire-studio/src/haywire_studio/auth/gate.py`, `login.py` | Import sites only |
| `packages/haywire-studio/src/haywire_studio/app.py` | Reads the document at startup; `sanitize()`; `setup_farmhand` signature |
| `packages/haywire-studio/src/haywire_studio/cli/__init__.py` | Registers two new subcommands |
| `packages/haywire-studio/src/haywire_studio/cli/authcmd.py` | `_offer_token_import` deleted; `--roster` → `--document` |
| `packages/haywire-studio/src/haywire_studio/cli/user.py`, `sslcmd.py`, `securitycmd.py` | Import sites, `--document`, two new axes in the report |
| `barn/haybale-studio/haybale_studio/panels/properties/setting/app.py` | `NetworkSettingsPanel` → `SecurityPanel` |
| `barn/haybale-studio/haybale_studio/editors/roster_editor.py` | Import sites |
| `docs/reference/glossary.md` | Roster/token/document vocabulary |
| `.claude/skills/haywire-live-studio/SKILL.md` | Token instructions |
| `mkdocs.yml` | Nav: `network_config.md` → `security.md` |

---

## Task 1: The security document

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/security/__init__.py`
- Create: `packages/haywire-studio/src/haywire_studio/security/errors.py`
- Create: `packages/haywire-studio/src/haywire_studio/security/roster.py`
- Create: `packages/haywire-studio/src/haywire_studio/security/document.py`
- Delete: `packages/haywire-studio/src/haywire_studio/auth/roster.py`
- Test: `tests/security/__init__.py`, `tests/security/test_document.py`

**Interfaces:**
- Consumes: `haywire.core.access.AccessTier`
- Produces:
  - `SecurityError(Exception)`
  - `Principal(name, kind, tier, password_hash="", token="", workspace="")`, `.is_user`, `.is_agent`, `.to_dict()`, `.from_dict(d)`
  - `Roster(enabled=False, session_days=30, principals=[])`, `.find(name)`, `.find_by_token(t)`, `.admins()`, `.to_dict()`, `.from_dict(d)`
  - `NetworkPolicy(exposed=False, allowed_ranges=(), public_hostname="", trusted_proxies=(), tls_certfile="", tls_keyfile="")`, `.tls_configured`, `.allowlist_open`, `.reachable_by_others`, `.to_dict()`, `.from_dict(d)`
  - `FarmhandPolicy(enabled=True, restrict_to_loopback=True)`, `.to_dict()`, `.from_dict(d)`
  - `SecurityDocument(auth: Roster, network: NetworkPolicy, farmhand: FarmhandPolicy)`, `.to_dict()`
  - `security_path() -> Path`, `load_document(path=None) -> SecurityDocument`, `save_document(doc, path=None) -> None`, `validate(doc) -> list[str]`, `sanitize(doc) -> tuple[SecurityDocument, list[str]]`
  - `SECURITY_VERSION = 1`, `SECURITY_FILENAME = "security.json"`, `KIND_USER`, `KIND_AGENT`

- [ ] **Step 1: Write the failing tests**

Create `tests/security/__init__.py` (empty file), then `tests/security/test_document.py`:

```python
"""The security document: round-trip, invariants, fail-closed loading."""

from __future__ import annotations

import json
import os
import stat

import pytest

from haywire.core.access import AccessTier

from haywire_studio.security.document import (
    SECURITY_VERSION,
    FarmhandPolicy,
    NetworkPolicy,
    SecurityDocument,
    load_document,
    sanitize,
    save_document,
    validate,
)
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.roster import KIND_AGENT, KIND_USER, Principal, Roster


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


def _admin() -> Principal:
    return Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")


def _hardened() -> SecurityDocument:
    """The one document shape that satisfies every invariant."""
    return SecurityDocument(
        auth=Roster(enabled=True, principals=[_admin()]),
        network=NetworkPolicy(
            exposed=True,
            allowed_ranges=("192.168.1.0/24",),
            tls_certfile="/tmp/c.pem",
            tls_keyfile="/tmp/k.pem",
        ),
        farmhand=FarmhandPolicy(),
    )


def test_missing_file_is_a_default_document(path):
    doc = load_document(path)
    assert doc.auth.enabled is False
    assert doc.network.exposed is False
    assert doc.farmhand.enabled is True
    assert doc.farmhand.restrict_to_loopback is True


def test_round_trip_preserves_every_block(path):
    save_document(_hardened(), path)
    doc = load_document(path)
    assert doc.auth.enabled is True
    assert doc.auth.principals[0].name == "root"
    assert doc.network.exposed is True
    assert doc.network.allowed_ranges == ("192.168.1.0/24",)
    assert doc.network.tls_certfile == "/tmp/c.pem"
    assert doc.farmhand.restrict_to_loopback is True


def test_saved_file_is_private(path):
    save_document(SecurityDocument(), path)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


def test_save_leaves_no_temp_file(path):
    save_document(SecurityDocument(), path)
    assert list(path.parent.iterdir()) == [path]


def test_unparseable_file_raises(path):
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SecurityError):
        load_document(path)


def test_wrong_version_raises(path):
    path.write_text(json.dumps({"version": 99}), encoding="utf-8")
    with pytest.raises(SecurityError):
        load_document(path)


def test_auth_enabled_without_an_admin_is_rejected(path):
    doc = SecurityDocument(auth=Roster(enabled=True, principals=[]))
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_exposed_without_auth_is_rejected(path):
    doc = _hardened()
    doc.auth.enabled = False
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_exposed_without_tls_is_rejected(path):
    doc = _hardened()
    doc.network.tls_certfile = ""
    doc.network.tls_keyfile = ""
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_exposed_without_ranges_is_rejected(path):
    doc = _hardened()
    doc.network.allowed_ranges = ()
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_half_configured_tls_is_rejected(path):
    doc = SecurityDocument(network=NetworkPolicy(tls_certfile="/tmp/c.pem"))
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_invalid_cidr_is_rejected(path):
    doc = _hardened()
    doc.network.allowed_ranges = ("not-a-cidr",)
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_hardened_document_saves(path):
    save_document(_hardened(), path)
    assert validate(load_document(path)) == []


def test_sanitize_downgrades_a_hand_edited_violation():
    """Fail closed, never refuse to start — a lockout's fix needs the UI it took away."""
    doc = _hardened()
    doc.auth.enabled = False  # hand-edited: exposed with auth off
    clean, reasons = sanitize(doc)
    assert clean.network.exposed is False
    assert reasons
    assert validate(clean) == []


def test_sanitize_leaves_a_valid_document_alone():
    clean, reasons = sanitize(_hardened())
    assert reasons == []
    assert clean.network.exposed is True


def test_agent_principal_round_trips(path):
    doc = SecurityDocument(
        auth=Roster(
            principals=[Principal(name="bot", kind=KIND_AGENT, tier=AccessTier.EDIT, token="t0ken")]
        )
    )
    save_document(doc, path)
    loaded = load_document(path)
    assert loaded.auth.find_by_token("t0ken").name == "bot"
    assert loaded.auth.find_by_token("") is None


def test_version_is_written(path):
    save_document(SecurityDocument(), path)
    assert json.loads(path.read_text())["version"] == SECURITY_VERSION
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/security/test_document.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'haywire_studio.security'`

- [ ] **Step 3: Create the package marker and the error module**

`packages/haywire-studio/src/haywire_studio/security/__init__.py`:

```python
"""The studio's security document — one CLI-owned file for every startup-read control.

See ADR 0028. The package deliberately owns *all three* axes (authentication,
network location, Farmhand) rather than one, because the invariants that matter
are the combinations: "exposed" is only safe as a statement about a document
that also has authentication on and TLS configured, and a design where those
live in different files makes the dangerous combination independently reachable.
"""
```

`packages/haywire-studio/src/haywire_studio/security/errors.py`:

```python
"""The one exception this feature raises.

Alone in its own module so that :mod:`roster` (the model) and :mod:`document`
(the I/O and rules) can both raise it without importing each other.
"""

from __future__ import annotations


class SecurityError(Exception):
    """The security document rejected a read or a write.

    Covers three cases that all mean "do not proceed on a guess": the file
    cannot be parsed, its version is not understood, or a requested change
    would violate an invariant. Never degraded into a default document —
    a default document means "authentication is off", and turning a disk
    problem into an open door is the one direction of error this feature
    must not make.
    """
```

- [ ] **Step 4: Create the roster model**

`packages/haywire-studio/src/haywire_studio/security/roster.py` — this is `auth/roster.py` with every file-I/O function removed and `RosterError` replaced by `SecurityError`. `Roster` gains a `from_dict` so `document.py` has one place to parse the `auth` block:

```python
"""Principals and the roster — the ``auth`` block of the security document.

Pure model: no paths, no file I/O, no crypto. The document owns reading and
writing (:mod:`haywire_studio.security.document`), the operations modules own
the rules. This split is what lets the CLI and the roster UI call the same
functions and be unable to drift into two sets of rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from haywire.core.access import AccessTier

from haywire_studio.security.errors import SecurityError

KIND_USER = "user"
KIND_AGENT = "agent"


@dataclass
class Principal:
    """Anything that can authenticate — a person or an agent.

    The model does not split people from machines: one roster answers "who can
    reach this studio" completely. ``kind`` selects the credential, not the
    privilege — both carry one :class:`AccessTier`.

    ``password_hash`` is set for users, ``token`` for agents. Tokens are stored
    in plaintext while passwords are hashed: passwords are hashed because humans
    reuse them across services, and a 256-bit token exists nowhere but this
    studio, so hashing it would protect nothing beyond a machine already lost —
    while costing the ability to re-copy the connection command.

    ``workspace`` scopes an agent to one project path; empty means every
    workspace on this machine.
    """

    name: str
    kind: str
    tier: AccessTier
    password_hash: str = ""
    token: str = ""
    workspace: str = ""

    @property
    def is_user(self) -> bool:
        return self.kind == KIND_USER

    @property
    def is_agent(self) -> bool:
        return self.kind == KIND_AGENT

    def to_dict(self) -> dict:
        data: dict[str, object] = {"name": self.name, "kind": self.kind, "tier": self.tier.value}
        if self.password_hash:
            data["password_hash"] = self.password_hash
        if self.token:
            data["token"] = self.token
        if self.workspace:
            data["workspace"] = self.workspace
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Principal":
        try:
            tier = AccessTier(data["tier"])
        except (KeyError, ValueError) as exc:
            raise SecurityError(f"Principal {data.get('name')!r} has an unusable tier: {exc}") from exc
        name = data.get("name")
        if not isinstance(name, str) or not name:
            raise SecurityError("Every principal needs a non-empty name.")
        kind = data.get("kind", KIND_USER)
        if kind not in (KIND_USER, KIND_AGENT):
            raise SecurityError(f"Principal {name!r} has unknown kind {kind!r}.")
        return cls(
            name=name,
            kind=kind,
            tier=tier,
            password_hash=data.get("password_hash", ""),
            token=data.get("token", ""),
            workspace=data.get("workspace", ""),
        )


@dataclass
class Roster:
    """Who can reach this studio, and whether anyone has to prove it."""

    enabled: bool = False
    session_days: int = 30
    principals: list[Principal] = field(default_factory=list)

    def find(self, name: str) -> Principal | None:
        """Exact-match lookup. Names are case-sensitive so two principals cannot
        collide under one casefold and silently share a tier."""
        for principal in self.principals:
            if principal.name == name:
                return principal
        return None

    def find_by_token(self, token: str) -> Principal | None:
        """Agent lookup by bearer token. An empty token never matches, so a
        user principal (which has no token) can never be reached this way."""
        if not token:
            return None
        for principal in self.principals:
            if principal.token and principal.token == token:
                return principal
        return None

    def admins(self) -> list[Principal]:
        return [p for p in self.principals if p.tier is AccessTier.ADMIN]

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "session_days": self.session_days,
            "principals": [p.to_dict() for p in self.principals],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Roster":
        if not isinstance(data, dict):
            raise SecurityError("The 'auth' block must be a JSON object.")
        entries = data.get("principals", [])
        if not isinstance(entries, list):
            raise SecurityError("'auth.principals' must be a list.")
        return cls(
            enabled=bool(data.get("enabled", False)),
            session_days=int(data.get("session_days", 30)),
            principals=[Principal.from_dict(entry) for entry in entries],
        )
```

- [ ] **Step 5: Create the document**

`packages/haywire-studio/src/haywire_studio/security/document.py`:

```python
"""``~/.haywire/security.json`` — one document for every startup-read control (ADR 0028).

**One document, deliberately.** "Authentication is on", "an admin exists",
"the studio is exposed" and "TLS is configured" are not independent facts that
happen to sit near each other — they are a chain, and the dangerous states are
the combinations. Split across files they are independently editable, so
"exposed with authentication off" becomes a reachable state that every guard
against it is a check someone must remember to write and keep working. As
fields of one document written through one validating path, the state does not
exist.

**Not a settings bag.** The settings UI writes the *workspace* tier
(``<workspace>/.haywire/settings.json``), a per-project file that travels into
git and onto other machines — so flipping "expose" in a panel committed a
machine's exposure decision into a project. The global settings tier avoids
that but is hand-edit-only, so a bag would render fields in the settings UI
that silently do nothing when edited. Both objections were already recorded in
ADR 0027 for the roster; ADR 0028 applies them to the rest.

**Writes refuse; loads fail closed.** :func:`save_document` raises on any
invariant violation, so a bad state cannot be written through the API. A
*hand-edited* violation is handled by :func:`sanitize`, which downgrades to the
safe value and reports why — never by refusing to start, because a studio that
will not boot has taken away the only UI that could repair it.
"""

from __future__ import annotations

import ipaddress
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from haywire_studio.security.errors import SecurityError
from haywire_studio.security.roster import Roster

SECURITY_VERSION = 1
SECURITY_FILENAME = "security.json"


def security_path() -> Path:
    """``~/.haywire/security.json`` — global, never per-workspace.

    Machine-and-operator policy, not project data: a certificate path or an
    allowlist committed into a project would follow it onto machines where it
    means something different, or nothing at all.
    """
    return Path.home() / ".haywire" / SECURITY_FILENAME


@dataclass
class NetworkPolicy:
    """Where the studio can be reached from, and whether the wire is encrypted.

    ``allowed_ranges`` and ``trusted_proxies`` are tuples of CIDR strings rather
    than one comma-joined string: the comma-joined form was a settings-system
    artifact (a ``STRING`` field), and parsing it at four call sites is how a
    stray space becomes a silently-dropped range.
    """

    exposed: bool = False
    allowed_ranges: tuple[str, ...] = ()
    public_hostname: str = ""
    trusted_proxies: tuple[str, ...] = ()
    tls_certfile: str = ""
    tls_keyfile: str = ""

    @property
    def tls_configured(self) -> bool:
        """Both halves set. Sequential rather than ``and`` so each is separately
        readable — exactly one of the pair is the half-configured state that
        :func:`validate` rejects, so the two are not interchangeable."""
        if not self.tls_certfile:
            return False
        if not self.tls_keyfile:
            return False
        return True

    @property
    def allowlist_open(self) -> bool:
        """True when the allowlist admits addresses beyond loopback.

        **This mirrors** ``IPAllowlistMiddleware``: its ``_is_allowed`` is
        ``any(ip in network ...)`` over the parsed ranges, which for an empty
        sequence is always False — so an empty list is **closed**, not open,
        and only loopback bypasses it. That is the opposite of the usual "unset
        means unrestricted" convention, and getting it backwards is how the
        security report once came to claim an empty list allowed everyone.
        """
        return bool(self.allowed_ranges)

    @property
    def reachable_by_others(self) -> bool:
        """True when a machine other than this one can actually connect.

        Two sequential rejections rather than ``exposed and allowlist_open`` so
        each precondition is separately readable and separately testable.
        """
        if not self.exposed:
            return False
        if not self.allowlist_open:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "exposed": self.exposed,
            "allowed_ranges": list(self.allowed_ranges),
            "public_hostname": self.public_hostname,
            "trusted_proxies": list(self.trusted_proxies),
            "tls_certfile": self.tls_certfile,
            "tls_keyfile": self.tls_keyfile,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NetworkPolicy":
        if not isinstance(data, dict):
            raise SecurityError("The 'network' block must be a JSON object.")
        return cls(
            exposed=bool(data.get("exposed", False)),
            allowed_ranges=_str_tuple(data.get("allowed_ranges"), "network.allowed_ranges"),
            public_hostname=str(data.get("public_hostname", "")),
            trusted_proxies=_str_tuple(data.get("trusted_proxies"), "network.trusted_proxies"),
            tls_certfile=str(data.get("tls_certfile", "")),
            tls_keyfile=str(data.get("tls_keyfile", "")),
        )


@dataclass
class FarmhandPolicy:
    """The Farmhand MCP mount's switches.

    ``restrict_to_loopback`` is DNS-rebinding protection: it configures the MCP
    SDK's ``TransportSecuritySettings`` to reject requests whose ``Host``/
    ``Origin`` header is not loopback. It is a **header** check, so it does not
    stop ``curl`` — it stops a malicious page in the operator's own browser
    resolving an attacker DNS name to 127.0.0.1 and talking to the local MCP
    server as if same-origin. That is exactly the attack a browser cannot be
    talked out of, and exactly the one a header check catches.
    """

    enabled: bool = True
    restrict_to_loopback: bool = True

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "restrict_to_loopback": self.restrict_to_loopback}

    @classmethod
    def from_dict(cls, data: dict) -> "FarmhandPolicy":
        if not isinstance(data, dict):
            raise SecurityError("The 'farmhand' block must be a JSON object.")
        return cls(
            enabled=bool(data.get("enabled", True)),
            restrict_to_loopback=bool(data.get("restrict_to_loopback", True)),
        )


@dataclass
class SecurityDocument:
    """The whole security picture as one value."""

    auth: Roster = field(default_factory=Roster)
    network: NetworkPolicy = field(default_factory=NetworkPolicy)
    farmhand: FarmhandPolicy = field(default_factory=FarmhandPolicy)

    def to_dict(self) -> dict:
        return {
            "version": SECURITY_VERSION,
            "auth": self.auth.to_dict(),
            "network": self.network.to_dict(),
            "farmhand": self.farmhand.to_dict(),
        }


def validate(doc: SecurityDocument) -> list[str]:
    """Every invariant this document must satisfy, as human-readable violations.

    Empty list means the document is writable. Returned rather than raised so
    that one caller (:func:`save_document`) can refuse, another
    (:func:`sanitize`) can repair, and a third (the security report) can print —
    all reading the same rules, which is the only way three surfaces stay
    agreed about what "safe" means.
    """
    problems: list[str] = []

    if doc.auth.enabled and not doc.auth.admins():
        problems.append(
            "Authentication is enabled but no admin principal exists — "
            "the roster editor and account panel are ADMIN-gated, so nobody could open them."
        )

    if bool(doc.network.tls_certfile) != bool(doc.network.tls_keyfile):
        missing = "tls_keyfile" if doc.network.tls_certfile else "tls_certfile"
        problems.append(f"TLS is half-configured: {missing} is empty. Set both, or neither.")

    for label, entries in (
        ("network.allowed_ranges", doc.network.allowed_ranges),
        ("network.trusted_proxies", doc.network.trusted_proxies),
    ):
        for entry in entries:
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError:
                problems.append(f"{label} contains {entry!r}, which is not a CIDR range.")

    if doc.network.exposed:
        if not doc.auth.enabled:
            problems.append(
                "The studio cannot be exposed with authentication off — anyone who could "
                "reach it would be a full operator. Run 'haywire auth enable' first."
            )
        if not doc.network.tls_configured:
            problems.append(
                "The studio cannot be exposed without TLS — passwords and session cookies "
                "would cross the network in cleartext. Run 'haywire ssl setup' first."
            )
        if not doc.network.allowlist_open:
            problems.append(
                "The studio cannot be exposed with an empty allowlist — every remote peer "
                "would be rejected, which is indistinguishable from not being exposed. "
                "Pass --ranges to 'haywire network expose'."
            )

    return problems


def sanitize(doc: SecurityDocument) -> tuple[SecurityDocument, list[str]]:
    """Return a valid document plus the reasons it had to be changed.

    Only ever used on the startup path, for a document a human edited by hand.
    **It never refuses.** Refusing to start is a lockout whose fix requires the
    UI that just went away, so every violation resolves in the safe direction:
    exposure off, TLS off, authentication off. The reasons are logged at
    CRITICAL, and ``haywire security status`` reports the same list.
    """
    reasons = validate(doc)
    if not reasons:
        return doc, []

    network = NetworkPolicy(
        exposed=doc.network.exposed,
        allowed_ranges=tuple(e for e in doc.network.allowed_ranges if _is_cidr(e)),
        public_hostname=doc.network.public_hostname,
        trusted_proxies=tuple(e for e in doc.network.trusted_proxies if _is_cidr(e)),
        tls_certfile=doc.network.tls_certfile,
        tls_keyfile=doc.network.tls_keyfile,
    )
    if not (network.tls_certfile and network.tls_keyfile):
        network.tls_certfile = ""
        network.tls_keyfile = ""

    auth = doc.auth
    if auth.enabled and not auth.admins():
        auth.enabled = False

    if not auth.enabled or not network.tls_configured or not network.allowlist_open:
        network.exposed = False

    return SecurityDocument(auth=auth, network=network, farmhand=doc.farmhand), reasons


def load_document(path: Path | None = None) -> SecurityDocument:
    """Read the document. A missing file is the default, all-off document.

    Raises :class:`SecurityError` on an unparseable or future-versioned file
    rather than degrading to the default: the default means "authentication is
    off", so a disk problem must never read as an open door.
    """
    target = path or security_path()
    if not target.exists():
        return SecurityDocument()

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SecurityError(f"Cannot read {target}: {exc}") from exc

    if not isinstance(raw, dict):
        raise SecurityError(f"{target} does not contain a JSON object.")

    version = raw.get("version")
    if version != SECURITY_VERSION:
        raise SecurityError(
            f"{target} has version {version!r}, but this studio understands version "
            f"{SECURITY_VERSION}. Upgrade haywire, or move the file aside to start over."
        )

    return SecurityDocument(
        auth=Roster.from_dict(raw.get("auth", {})),
        network=NetworkPolicy.from_dict(raw.get("network", {})),
        farmhand=FarmhandPolicy.from_dict(raw.get("farmhand", {})),
    )


def save_document(doc: SecurityDocument, path: Path | None = None) -> None:
    """Validate, then write atomically at ``0600``.

    Validation lives here rather than in each caller so that a future writer
    cannot forget it. Temp file in the same directory (so ``os.replace`` stays
    on one filesystem and is therefore atomic), ``chmod`` before the rename so
    the secrets are never briefly world-readable, then replace: a truncated
    document would lock every principal out of the only UI that could repair it.
    """
    problems = validate(doc)
    if problems:
        raise SecurityError("\n".join(problems))

    target = path or security_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(json.dumps(doc.to_dict(), indent=2) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    os.replace(tmp, target)


def _is_cidr(entry: str) -> bool:
    try:
        ipaddress.ip_network(entry, strict=False)
    except ValueError:
        return False
    return True


def _str_tuple(value: Any, label: str) -> tuple[str, ...]:
    """Parse a JSON list of strings. Absent is empty; anything else is an error."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SecurityError(f"{label} must be a list of CIDR strings.")
    return tuple(str(entry).strip() for entry in value if str(entry).strip())
```

- [ ] **Step 6: Delete the old roster module**

```bash
git rm packages/haywire-studio/src/haywire_studio/auth/roster.py
```

This breaks imports in `auth/operations.py`, `auth/live.py`, `auth/gate.py`, `auth/login.py`, `network/security.py`, `cli/*.py` and `barn/haybale-studio/.../roster_editor.py`. Tasks 3, 4 and 7 repair them. Until then only `tests/security/` will pass — that is expected and is why this task's verification is scoped to that directory.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/security/test_document.py -q`
Expected: `17 passed`

- [ ] **Step 8: Lint, format and type-check the new package**

```bash
uv run ruff check packages/haywire-studio/src/haywire_studio/security/ tests/security/
uv run ruff format packages/haywire-studio/src/haywire_studio/security/ tests/security/
uv run mypy packages/haywire-studio/src/haywire_studio/security/
```

Expected: no findings from `ruff check`, no errors from `mypy`.

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/security/ tests/security/
git add -u packages/haywire-studio/src/haywire_studio/auth/
git commit -m "feat(security): one security document for every startup-read control

Introduces ~/.haywire/security.json holding auth, network and farmhand blocks.
Invariants live in validate() and run inside save_document(), so a writer
cannot forget them; sanitize() repairs a hand-edited file at startup instead
of refusing to boot.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Network and Farmhand operations

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/security/operations.py`
- Test: `tests/security/test_operations.py`

**Interfaces:**
- Consumes: `load_document`, `save_document`, `SecurityDocument`, `NetworkPolicy`, `SecurityError` (Task 1)
- Produces:
  - `expose(ranges, *, public_hostname=None, trusted_proxies=None, path=None) -> SecurityDocument`
  - `seal(*, path=None) -> SecurityDocument`
  - `set_farmhand_enabled(enabled, *, path=None) -> SecurityDocument`
  - `set_farmhand_loopback(restrict, *, path=None) -> SecurityDocument`
  - `write_tls_paths(certfile, keyfile, *, path=None) -> SecurityDocument`

- [ ] **Step 1: Write the failing tests**

Create `tests/security/test_operations.py`:

```python
"""The rules for changing the network and Farmhand blocks."""

from __future__ import annotations

import pytest

from haywire.core.access import AccessTier

from haywire_studio.security.document import (
    NetworkPolicy,
    SecurityDocument,
    load_document,
    save_document,
)
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.operations import (
    expose,
    seal,
    set_farmhand_enabled,
    set_farmhand_loopback,
    write_tls_paths,
)
from haywire_studio.security.roster import KIND_USER, Principal, Roster


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


def _ready(path, tmp_path):
    """A document with auth on and TLS configured — everything expose() needs."""
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("cert")
    key.write_text("key")
    doc = SecurityDocument(
        auth=Roster(
            enabled=True,
            principals=[Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")],
        ),
        network=NetworkPolicy(tls_certfile=str(cert), tls_keyfile=str(key)),
    )
    save_document(doc, path)
    return doc


def test_expose_refuses_without_auth(path, tmp_path):
    save_document(SecurityDocument(), path)
    with pytest.raises(SecurityError, match="authentication off"):
        expose(["192.168.1.0/24"], path=path)


def test_expose_refuses_without_tls(path, tmp_path):
    save_document(
        SecurityDocument(
            auth=Roster(
                enabled=True,
                principals=[
                    Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")
                ],
            )
        ),
        path,
    )
    with pytest.raises(SecurityError, match="without TLS"):
        expose(["192.168.1.0/24"], path=path)


def test_expose_refuses_empty_ranges(path, tmp_path):
    _ready(path, tmp_path)
    with pytest.raises(SecurityError, match="empty allowlist"):
        expose([], path=path)


def test_expose_refuses_a_bad_cidr(path, tmp_path):
    _ready(path, tmp_path)
    with pytest.raises(SecurityError, match="not a CIDR"):
        expose(["192.168.1.0/24", "nonsense"], path=path)


def test_expose_writes_the_ranges(path, tmp_path):
    _ready(path, tmp_path)
    expose(["192.168.1.0/24", " 10.0.0.0/8 "], path=path)
    net = load_document(path).network
    assert net.exposed is True
    assert net.allowed_ranges == ("192.168.1.0/24", "10.0.0.0/8")


def test_expose_records_hostname_and_proxies(path, tmp_path):
    _ready(path, tmp_path)
    expose(
        ["192.168.1.0/24"],
        public_hostname="studio.example.com",
        trusted_proxies=["10.1.0.0/16"],
        path=path,
    )
    net = load_document(path).network
    assert net.public_hostname == "studio.example.com"
    assert net.trusted_proxies == ("10.1.0.0/16",)


def test_expose_leaves_hostname_alone_when_not_given(path, tmp_path):
    _ready(path, tmp_path)
    expose(["192.168.1.0/24"], public_hostname="studio.example.com", path=path)
    expose(["10.0.0.0/8"], path=path)
    assert load_document(path).network.public_hostname == "studio.example.com"


def test_seal_turns_exposure_off_and_keeps_the_ranges(path, tmp_path):
    _ready(path, tmp_path)
    expose(["192.168.1.0/24"], path=path)
    seal(path=path)
    net = load_document(path).network
    assert net.exposed is False
    assert net.allowed_ranges == ("192.168.1.0/24",)


def test_seal_on_a_sealed_document_is_a_no_op(path):
    save_document(SecurityDocument(), path)
    seal(path=path)
    assert load_document(path).network.exposed is False


def test_farmhand_enabled_toggles(path):
    save_document(SecurityDocument(), path)
    set_farmhand_enabled(False, path=path)
    assert load_document(path).farmhand.enabled is False
    set_farmhand_enabled(True, path=path)
    assert load_document(path).farmhand.enabled is True


def test_allow_remote_refuses_without_auth(path):
    save_document(SecurityDocument(), path)
    with pytest.raises(SecurityError, match="authentication"):
        set_farmhand_loopback(False, path=path)


def test_allow_remote_is_permitted_with_auth_on(path, tmp_path):
    _ready(path, tmp_path)
    set_farmhand_loopback(False, path=path)
    assert load_document(path).farmhand.restrict_to_loopback is False


def test_local_only_never_needs_auth(path):
    save_document(SecurityDocument(), path)
    set_farmhand_loopback(True, path=path)
    assert load_document(path).farmhand.restrict_to_loopback is True


def test_write_tls_paths_sets_both(path, tmp_path):
    save_document(SecurityDocument(), path)
    write_tls_paths("/tmp/c.pem", "/tmp/k.pem", path=path)
    net = load_document(path).network
    assert net.tls_certfile == "/tmp/c.pem"
    assert net.tls_keyfile == "/tmp/k.pem"


def test_write_tls_paths_refuses_one_alone(path):
    save_document(SecurityDocument(), path)
    with pytest.raises(SecurityError, match="half-configured"):
        write_tls_paths("/tmp/c.pem", "", path=path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/security/test_operations.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'haywire_studio.security.operations'`

- [ ] **Step 3: Write the operations module**

`packages/haywire-studio/src/haywire_studio/security/operations.py`:

```python
"""The rules for changing the network and Farmhand blocks (ADR 0028).

:mod:`document` is the document — read it, write it, validate it. This module
is the *verbs*: what "expose" means, what it demands first, and what it leaves
alone. They live apart for the reason ``auth/operations.py`` already does — the
CLI and any future UI call the same functions and cannot drift into two sets of
rules.

**Exposure is a verb, not a boolean.** ``expose_to_network`` used to be one bit
in a settings panel, but safe exposure is three or four coordinated decisions
and a checkbox cannot express a precondition. Every refusal here names the one
command that fixes it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from haywire_studio.security.document import (
    NetworkPolicy,
    SecurityDocument,
    load_document,
    save_document,
)
from haywire_studio.security.errors import SecurityError


def expose(
    ranges: Sequence[str],
    *,
    public_hostname: str | None = None,
    trusted_proxies: Iterable[str] | None = None,
    path: Path | None = None,
) -> SecurityDocument:
    """Bind beyond loopback, admitting *ranges*.

    Refuses unless authentication is on, TLS is configured and at least one
    range is given — those three checks live in
    :func:`~haywire_studio.security.document.validate`, so this function does
    not restate them; it assembles the document it wants and lets the write
    path reject it. That is deliberate: a second copy of the preconditions here
    is a second copy that can disagree with the one the studio boots against.

    ``public_hostname`` and ``trusted_proxies`` are left untouched when not
    given, so re-running ``expose`` to change subnets does not silently drop a
    reverse-proxy configuration.
    """
    doc = load_document(path)
    doc.network = NetworkPolicy(
        exposed=True,
        allowed_ranges=_clean(ranges),
        public_hostname=(
            doc.network.public_hostname if public_hostname is None else public_hostname.strip()
        ),
        trusted_proxies=(
            doc.network.trusted_proxies if trusted_proxies is None else _clean(trusted_proxies)
        ),
        tls_certfile=doc.network.tls_certfile,
        tls_keyfile=doc.network.tls_keyfile,
    )
    save_document(doc, path)
    return doc


def seal(*, path: Path | None = None) -> SecurityDocument:
    """Bind to loopback again.

    **The allowlist is kept.** Sealing is usually temporary — a laptop leaving
    the venue — and discarding the ranges would make the return trip a
    re-typing exercise. Exposure is the bit that decides reachability; the
    ranges are inert while it is off.
    """
    doc = load_document(path)
    doc.network.exposed = False
    save_document(doc, path)
    return doc


def set_farmhand_enabled(enabled: bool, *, path: Path | None = None) -> SecurityDocument:
    """Serve, or stop serving, the MCP endpoint at ``/mcp``."""
    doc = load_document(path)
    doc.farmhand.enabled = enabled
    save_document(doc, path)
    return doc


def set_farmhand_loopback(restrict: bool, *, path: Path | None = None) -> SecurityDocument:
    """Turn the DNS-rebinding ``Host``/``Origin`` check on or off.

    Turning it **off** demands authentication, and that check lives here rather
    than in ``validate`` because it constrains a transition, not a state: a
    document with the check off and authentication off is not corrupt, it is
    simply what you get when someone disables authentication afterwards — and
    refusing to load that would be a lockout. Refusing to *enter* it is enough,
    and ``haywire security status`` reports the combination if it is reached
    another way.
    """
    doc = load_document(path)
    if not restrict and not doc.auth.enabled:
        raise SecurityError(
            "Farmhand cannot accept remote MCP clients while authentication is off — "
            "the DNS-rebinding check would be the only thing standing between a web page "
            "in your browser and this studio's tools.\n"
            "  Run 'haywire auth enable' first."
        )
    doc.farmhand.restrict_to_loopback = restrict
    save_document(doc, path)
    return doc


def write_tls_paths(certfile: str, keyfile: str, *, path: Path | None = None) -> SecurityDocument:
    """Point the studio at a certificate and key.

    Both are written together, always — exactly one of the pair is the
    half-configured state ``validate`` rejects, and it is not a state this
    function is permitted to create.
    """
    doc = load_document(path)
    doc.network.tls_certfile = certfile
    doc.network.tls_keyfile = keyfile
    save_document(doc, path)
    return doc


def _clean(entries: Iterable[str]) -> tuple[str, ...]:
    """Strip and drop blanks, preserving order. Validation happens on write."""
    return tuple(entry.strip() for entry in entries if entry.strip())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/security/test_operations.py -q`
Expected: `15 passed`

- [ ] **Step 5: Lint, format, type-check**

```bash
uv run ruff check packages/haywire-studio/src/haywire_studio/security/ tests/security/
uv run ruff format packages/haywire-studio/src/haywire_studio/security/ tests/security/
uv run mypy packages/haywire-studio/src/haywire_studio/security/
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/security/operations.py tests/security/test_operations.py
git commit -m "feat(security): expose/seal/farmhand operations over the document

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Rewire the auth modules onto the document

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/auth/operations.py`
- Modify: `packages/haywire-studio/src/haywire_studio/auth/live.py`
- Modify: `packages/haywire-studio/src/haywire_studio/auth/gate.py` (imports only)
- Modify: `packages/haywire-studio/src/haywire_studio/auth/login.py` (imports only)
- Modify: `tests/auth/conftest.py`, `tests/auth/test_roster.py`, `tests/auth/test_operations.py`, `tests/auth/test_live.py`
- Test: existing `tests/auth/`

**Interfaces:**
- Consumes: everything from Tasks 1–2
- Produces: `auth/operations.py` unchanged in signature (`add_user`, `add_agent`, `remove_principal`, `set_password`, `set_tier`, `authenticate`, `enable_auth`, `disable_auth`) but now raising `SecurityError` and taking `path` = the **document** path. `RosterCache.roster()` still returns a `Roster`.

- [ ] **Step 1: Find every reference to the deleted module**

```bash
grep -rn "auth.roster\|RosterError\|load_roster\|save_roster\|roster_path" \
  packages/ barn/ tests/ --include="*.py" | grep -v __pycache__
```

Record the list — Steps 2–6 and Task 7 must clear all of it.

- [ ] **Step 2: Rewrite `auth/operations.py`**

Replace the import block and every `load_roster`/`save_roster` pair with document reads. The rules themselves are unchanged. New header and the changed functions:

```python
"""The rules for changing the roster (ADR 0027, ADR 0028).

``security/document.py`` is the document — read it, write it, validate it. This
module is the *rules* for its ``auth`` block: last-admin protection, name
collisions, the password policy gate, and the credential check that guards
enable/disable.

They live apart so the CLI and the roster UI call the same functions and cannot
drift into two different sets of rules.

Every write goes through ``save_document``, which validates the **whole**
document — so ``disable_auth`` on an exposed studio is refused here for free,
by the invariant rather than by a check this module has to remember.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from haywire.core.access import AccessTier

from haywire_studio.auth.passwords import dummy_verify, hash_password, password_problem, verify_password
from haywire_studio.security.document import load_document, save_document
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.roster import KIND_AGENT, KIND_USER, Principal, Roster

TOKEN_BYTES = 32


def _require_password_ok(password: str, username: str) -> None:
    problem = password_problem(password, username=username)
    if problem is not None:
        raise SecurityError(problem)


def _require_absent(roster: Roster, name: str) -> None:
    if not name:
        raise SecurityError("A principal needs a name.")
    if roster.find(name) is not None:
        raise SecurityError(f"A principal named {name!r} already exists.")


def _require_present(roster: Roster, name: str) -> Principal:
    principal = roster.find(name)
    if principal is None:
        raise SecurityError(f"No principal named {name!r}.")
    return principal


def _require_not_last_admin(roster: Roster, principal: Principal) -> None:
    """Refuse a change that would leave an enabled roster with no admin.

    Only enforced while ``enabled`` is set: with authentication off there is no
    lockout to protect against, and forcing an admin to exist would be noise.
    """
    if not roster.enabled:
        return
    if principal.tier is not AccessTier.ADMIN:
        return
    if len(roster.admins()) <= 1:
        raise SecurityError(
            f"{principal.name!r} is the last admin and authentication is enabled — "
            "removing or demoting them would lock everyone out. Add another admin first, "
            "or run 'haywire auth disable'."
        )


def add_user(name: str, password: str, tier: AccessTier, *, path: Path | None = None) -> Principal:
    """Create a password principal."""
    doc = load_document(path)
    _require_absent(doc.auth, name)
    _require_password_ok(password, name)
    principal = Principal(name=name, kind=KIND_USER, tier=tier, password_hash=hash_password(password))
    doc.auth.principals.append(principal)
    save_document(doc, path)
    return principal


def add_agent(name: str, tier: AccessTier, *, workspace: str = "", path: Path | None = None) -> Principal:
    """Create a token principal and mint its bearer token."""
    doc = load_document(path)
    _require_absent(doc.auth, name)
    principal = Principal(
        name=name,
        kind=KIND_AGENT,
        tier=tier,
        token=secrets.token_urlsafe(TOKEN_BYTES),
        workspace=workspace,
    )
    doc.auth.principals.append(principal)
    save_document(doc, path)
    return principal


def remove_principal(name: str, *, path: Path | None = None) -> None:
    doc = load_document(path)
    principal = _require_present(doc.auth, name)
    _require_not_last_admin(doc.auth, principal)
    doc.auth.principals = [p for p in doc.auth.principals if p.name != name]
    save_document(doc, path)


def set_password(name: str, password: str, *, path: Path | None = None) -> None:
    doc = load_document(path)
    principal = _require_present(doc.auth, name)
    if not principal.is_user:
        raise SecurityError(f"{name!r} is an agent — agents authenticate with a token, not a password.")
    _require_password_ok(password, name)
    principal.password_hash = hash_password(password)
    save_document(doc, path)


def set_tier(name: str, tier: AccessTier, *, path: Path | None = None) -> None:
    doc = load_document(path)
    principal = _require_present(doc.auth, name)
    if tier is not AccessTier.ADMIN:
        _require_not_last_admin(doc.auth, principal)
    principal.tier = tier
    save_document(doc, path)


def authenticate(username: str, password: str, *, path: Path | None = None) -> Principal | None:
    """Verify user credentials. Returns the principal, or ``None``.

    Always spends one scrypt hash even when the username is unknown, so a
    missing account and a wrong password take the same time — response timing
    cannot be used to enumerate the roster.
    """
    doc = load_document(path)
    principal = doc.auth.find(username)
    if principal is None or not principal.is_user or not principal.password_hash:
        dummy_verify()
        return None
    if not verify_password(password, principal.password_hash):
        return None
    return principal


def _require_admin_credentials(username: str, password: str, path: Path | None) -> None:
    doc = load_document(path)
    if not doc.auth.admins():
        raise SecurityError(
            "No admin principal exists yet. Create one first:\n  haywire user add <name> --tier admin"
        )
    principal = authenticate(username, password, path=path)
    if principal is None:
        raise SecurityError("Those credentials were not accepted.")
    if principal.tier is not AccessTier.ADMIN:
        raise SecurityError(f"{username!r} is not an admin.")


def enable_auth(username: str, password: str, *, path: Path | None = None) -> None:
    """Turn authentication on, but only for someone who can prove they can get back in.

    Anyone who can run this can also edit the JSON by hand, so the credential
    check is not a barrier against an attacker. It is a **proof of
    recoverability**: it makes the realistic failure unreachable — turning on
    authentication with a roster whose passwords nobody remembers, on a machine
    whose UI is now the only way to fix it.
    """
    _require_admin_credentials(username, password, path)
    doc = load_document(path)
    doc.auth.enabled = True
    save_document(doc, path)


def disable_auth(username: str, password: str, *, path: Path | None = None) -> None:
    """Turn authentication off. Requires the same proof as enabling it.

    Refused while the studio is exposed — not by a check here, but by the
    document invariant ``exposed ⇒ auth enabled`` inside ``save_document``.
    Run ``haywire network seal`` first.
    """
    _require_admin_credentials(username, password, path)
    doc = load_document(path)
    doc.auth.enabled = False
    save_document(doc, path)
```

- [ ] **Step 3: Rewrite `auth/live.py`'s cache to read the document**

Replace the import block and `RosterCache.__init__`/`roster()`:

```python
from haywire_studio.security.document import load_document, security_path
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.roster import Roster
```

```python
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or security_path()
        self._stamp: tuple[float, int] | None = None
        self._roster: Roster = Roster()

    def roster(self) -> Roster:
        stamp = self._current_stamp()
        if stamp != self._stamp:
            try:
                self._roster = load_document(self._path).auth
                self._stamp = stamp
            except SecurityError:
                logger.warning(
                    "Security document at %s could not be read; keeping the last good roster",
                    self._path,
                )
        return self._roster
```

Its docstring's first line becomes `"""Live document reads behind core's resolver hook (ADR 0027, ADR 0028)."""`.

- [ ] **Step 4: Fix the import sites in `gate.py` and `login.py`**

In both files, replace `from haywire_studio.auth.roster import ...` with the equivalent `from haywire_studio.security.roster import ...`, and every `RosterError` with `SecurityError` imported from `haywire_studio.security.errors`. No logic changes.

Verify nothing was missed:

```bash
grep -rn "auth.roster\|RosterError" packages/haywire-studio/src/haywire_studio/auth/
```

Expected: no output.

- [ ] **Step 5: Update the auth tests**

In `tests/auth/conftest.py`, `tests/auth/test_roster.py`, `tests/auth/test_operations.py`, `tests/auth/test_live.py`:

- `from haywire_studio.auth.roster import ...` → `from haywire_studio.security.roster import ...`
- `RosterError` → `SecurityError` (from `haywire_studio.security.errors`)
- `load_roster(p)` → `load_document(p).auth`
- `save_roster(roster, p)` → `save_document(SecurityDocument(auth=roster), p)`
- Any fixture writing an `auth.json` filename → `security.json`

Rename `tests/auth/test_roster.py` to `tests/auth/test_roster_model.py` (the document tests now live in `tests/security/test_document.py`, and two files called "test_roster" would be confusing):

```bash
git mv tests/auth/test_roster.py tests/auth/test_roster_model.py
```

- [ ] **Step 6: Run the auth tests**

Run: `uv run pytest tests/auth/ -q`
Expected: all pass. `tests/auth/test_app_wiring.py` and `test_end_to_end.py` may still fail on `app.py` imports — those are Task 5's; note which and move on only if the failure is exclusively an `app.py` symbol.

- [ ] **Step 7: Commit**

```bash
git add -A packages/haywire-studio/src/haywire_studio/auth/ tests/auth/
git commit -m "refactor(auth): read and write the roster through the security document

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: The posture module

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/network/tls_operations.py`
- Delete: `packages/haywire-studio/src/haywire_studio/network/tls_settings.py`
- Create: `packages/haywire-studio/src/haywire_studio/security/posture.py`
- Delete: `packages/haywire-studio/src/haywire_studio/network/security.py`
- Delete: `tests/studio/test_network/test_tls_settings.py`
- Test: `tests/security/test_posture.py`, `tests/studio/test_network/test_tls_operations.py`
- Move: `tests/studio/test_network/test_no_false_negatives.py` → `tests/security/test_no_false_negatives.py`
- Move: `tests/studio/test_network/test_allowlist_agreement.py` → `tests/security/test_allowlist_agreement.py`

**Interfaces:**
- Consumes: `SecurityDocument`, `validate`, `load_document` (Task 1); `write_tls_paths` (Task 2)
- Produces:
  - `tls_operations.status(*, directory=None, path=None, document=None) -> TlsStatus`, plus `setup`/`update` taking `path` (the document) in place of `settings_path`
  - `Severity`, `Finding(severity, headline, detail=(), fix="")`
  - `Posture(document, tls, findings, document_error="", studio_running=False)` with properties `exposed`, `reachable_at`, `auth_enabled`, `principals`, `admins`, `allowed_ranges`, `trusted_proxies`, `ranges`, `worst`, `tls_on`, `allowlist_open`, `fenced`, `reachable_by_others`, `farmhand_enabled`, `farmhand_loopback`, `covers_own_address()`
  - `assess_document(doc, tls) -> Posture` — pure, for the studio panel
  - `assess(*, directory=None, path=None) -> Posture` — reads files, for the CLI

**Design note for the implementer:** `Posture` now *holds* the document rather than copying eight scalars off it. The old shape existed because the values came from two unrelated files; they no longer do. Keep the derived properties — `securitycmd` and `authcmd` read them by name.

`tls_operations` is rewired here rather than in Task 5 because `assess()` calls `status(document=...)`: the posture module cannot be independently testable until that signature exists.

- [ ] **Step 1: Point `tls_operations.py` at the document**

Replace the `tls_settings` import block with:

```python
from haywire_studio.security.document import SecurityDocument, load_document
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.operations import write_tls_paths
```

Then, mechanically through the module:

- every `settings_path: Path | None = None` parameter becomes `path: Path | None = None` — it is the *document* path now, and `setup`/`update`/`status` all carry it
- `read_tls_paths(path=settings_path)` becomes a document read at the top of each function:
  ```python
  doc = load_document(path)
  configured_cert, configured_key = doc.network.tls_certfile, doc.network.tls_keyfile
  ```
- `write_tls_paths(str(cert), str(key), path=settings_path)` becomes `write_tls_paths(str(cert), str(key), path=path)` — the same name, now the Task 2 function, which validates before writing
- `read_network_setting("expose_to_network", path=settings_path)` in `status()` becomes `doc.network.exposed`
- `read_network_setting("public_hostname", path=settings_path)` in `_names_for_setup` becomes `doc.network.public_hostname`

`status()` additionally accepts a pre-loaded document, so the studio panel (Task 8) does not re-read disk, and keeps its "never raises" contract:

```python
def status(
    *,
    directory: Path | None = None,
    path: Path | None = None,
    document: SecurityDocument | None = None,
) -> TlsStatus:
    """Classify the current TLS setup. Never raises.

    *document* short-circuits the disk read — that is what lets the studio's
    Security panel report the configuration actually in force rather than
    whatever has since been written to the file.

    Deliberately does **not** probe any OS trust store: doing that portably is
    genuinely hard, and wrongly reporting "trusted" is worse than not reporting
    it at all. Report what the files say; let ``trust`` speak for itself.
    """
    doc = document if document is not None else _document_quietly(path)
    certfile, keyfile = doc.network.tls_certfile, doc.network.tls_keyfile
    exposed = doc.network.exposed
    # ... the rest of the existing body, unchanged ...


def _document_quietly(path: Path | None) -> SecurityDocument:
    """The document, or an empty one. ``status`` runs against whatever is on
    disk — including a broken file, which is precisely the situation the user
    needs reported, so it must not raise here."""
    try:
        return load_document(path)
    except SecurityError:
        return SecurityDocument()
```

Delete the dead module and its tests:

```bash
git rm packages/haywire-studio/src/haywire_studio/network/tls_settings.py
git rm tests/studio/test_network/test_tls_settings.py
```

In `tests/studio/test_network/test_tls_operations.py`: every `settings_path=` keyword becomes `path=`, and any fixture that wrote a settings JSON now calls `save_document(SecurityDocument(network=NetworkPolicy(...)), path)`.

**Expected collateral, repaired in Task 7:** `cli/sslcmd.py:36-38` imports `SettingsWriteError` and `workspace_overrides` from the module just deleted, and calls `workspace_overrides("ssl_certfile", "ssl_keyfile")` at lines 184 and 302. `haywire ssl` will not import until Task 7 Step 6 replaces those. Do not patch it here — a half-fix in two places is how the two ended up disagreeing before.

Run: `uv run pytest tests/studio/test_network/test_tls_operations.py -q`
Expected: all pass.

- [ ] **Step 2: Write the failing posture tests**

Create `tests/security/test_posture.py`:

```python
"""The joined report: which findings fire, and which stay silent."""

from __future__ import annotations

import pytest

from haywire.core.access import AccessTier

from haywire_studio.network.tls_operations import TlsState, TlsStatus
from haywire_studio.network.names import LocalNames
from haywire_studio.security.document import FarmhandPolicy, NetworkPolicy, SecurityDocument
from haywire_studio.security.posture import Severity, assess_document
from haywire_studio.security.roster import KIND_USER, Principal, Roster


def _tls(state: TlsState, *, reachable: str | None = "192.168.1.5") -> TlsStatus:
    return TlsStatus(
        state=state,
        certfile="/tmp/c.pem" if state is TlsState.OK else "",
        keyfile="/tmp/k.pem" if state is TlsState.OK else "",
        covered=LocalNames.empty(),
        reachable_at=reachable,
        exposed=False,
        expires=None,
        fingerprint=None,
        detail="",
    )


def _admin() -> Principal:
    return Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")


def _hardened() -> SecurityDocument:
    return SecurityDocument(
        auth=Roster(enabled=True, principals=[_admin()]),
        network=NetworkPolicy(
            exposed=True,
            allowed_ranges=("192.168.1.0/24",),
            trusted_proxies=("10.1.0.0/16",),
            tls_certfile="/tmp/c.pem",
            tls_keyfile="/tmp/k.pem",
        ),
    )


def _headlines(posture):
    return " ".join(f.headline for f in posture.findings)


def test_loopback_default_is_clean():
    posture = assess_document(SecurityDocument(), _tls(TlsState.OFF_LOOPBACK))
    assert posture.findings == ()
    assert posture.reachable_by_others is False


def test_hardened_and_exposed_raises_nothing_above_a_note():
    """A hardened studio still gets the "/mcp is reachable" NOTE — that is a fact
    worth knowing, not a gap. Nothing louder may fire."""
    posture = assess_document(_hardened(), _tls(TlsState.OK))
    assert posture.worst in (None, Severity.NOTE)
    assert posture.reachable_by_others is True


def test_hand_edited_violation_is_critical():
    doc = _hardened()
    doc.auth.enabled = False  # only reachable by hand-editing
    posture = assess_document(doc, _tls(TlsState.OK))
    assert posture.worst is Severity.CRITICAL
    assert "not in force" in _headlines(posture)


def test_broken_tls_is_critical_even_on_loopback():
    posture = assess_document(SecurityDocument(), _tls(TlsState.KEY_MISMATCH))
    assert posture.worst is Severity.CRITICAL


def test_no_admin_is_reported_without_exposure():
    doc = SecurityDocument(auth=Roster(enabled=True, principals=[]))
    posture = assess_document(doc, _tls(TlsState.OFF_LOOPBACK))
    assert "no admin" in _headlines(posture)


def test_broad_allowlist_warns_when_reachable():
    doc = _hardened()
    doc.network.allowed_ranges = ("10.0.0.0/8",)
    posture = assess_document(doc, _tls(TlsState.OK))
    assert "very broad" in _headlines(posture)


def test_broad_allowlist_is_silent_when_sealed():
    doc = _hardened()
    doc.network.exposed = False
    doc.network.allowed_ranges = ("10.0.0.0/8",)
    posture = assess_document(doc, _tls(TlsState.OK))
    assert "very broad" not in _headlines(posture)


def test_farmhand_remote_without_auth_is_critical():
    doc = SecurityDocument(farmhand=FarmhandPolicy(restrict_to_loopback=False))
    posture = assess_document(doc, _tls(TlsState.OFF_LOOPBACK))
    assert posture.worst is Severity.CRITICAL
    assert "DNS-rebinding" in _headlines(posture)


def test_farmhand_remote_with_auth_is_a_note():
    doc = _hardened()
    doc.farmhand.restrict_to_loopback = False
    posture = assess_document(doc, _tls(TlsState.OK))
    assert posture.worst is Severity.NOTE
    assert "DNS-rebinding" in _headlines(posture)


def test_farmhand_disabled_is_silent():
    doc = SecurityDocument(farmhand=FarmhandPolicy(enabled=False))
    posture = assess_document(doc, _tls(TlsState.OFF_LOOPBACK))
    assert posture.findings == ()
    assert posture.farmhand_enabled is False


def test_no_trusted_proxies_is_a_note_when_reachable():
    doc = _hardened()
    doc.network.trusted_proxies = ()
    posture = assess_document(doc, _tls(TlsState.OK))
    assert any(f.severity is Severity.NOTE for f in posture.findings)


def test_covers_own_address_is_true_for_a_matching_subnet():
    posture = assess_document(_hardened(), _tls(TlsState.OK, reachable="192.168.1.5"))
    assert posture.covers_own_address() is True


def test_covers_own_address_is_false_for_a_foreign_subnet():
    posture = assess_document(_hardened(), _tls(TlsState.OK, reachable="10.9.9.9"))
    assert posture.covers_own_address() is False


@pytest.mark.parametrize(
    "exposed,ranges,expected",
    [
        (False, (), False),
        (False, ("192.168.1.0/24",), False),
        (True, (), False),
        (True, ("192.168.1.0/24",), True),
    ],
)
def test_reachable_by_others_truth_table(exposed, ranges, expected):
    doc = _hardened()
    doc.network.exposed = exposed
    doc.network.allowed_ranges = ranges
    posture = assess_document(doc, _tls(TlsState.OK))
    assert posture.reachable_by_others is expected
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/security/test_posture.py -q`
Expected: `ModuleNotFoundError: No module named 'haywire_studio.security.posture'`

- [ ] **Step 4: Write `security/posture.py`**

Start from `network/security.py` and apply these changes; everything not listed keeps its existing docstring and body verbatim.

1. Module docstring first paragraph becomes:

```python
"""The joined view of the studio's four defence axes (ADR 0028).

Exposure, authentication, TLS and the Farmhand mount are not independent
settings that happen to sit near each other — they are a chain. Exposure
decides whether the others matter at all: on loopback, an empty roster and
plain HTTP are both correct, and warning about them there trains users to
ignore the warning.

Two entry points, one rule set. :func:`assess_document` is pure and takes the
document the studio actually booted with — that is what the settings panel
renders. :func:`assess` reads the files, for a CLI running against a stopped
studio. Splitting them is what lets the panel report what is *in force* rather
than what happens to be on disk.
"""
```

2. Imports become:

```python
from haywire_studio.network.tls_operations import TlsState, TlsStatus
from haywire_studio.network.tls_operations import status as tls_status
from haywire_studio.security.document import SecurityDocument, load_document, validate
from haywire_studio.security.errors import SecurityError
```

3. `Posture` holds the document:

```python
@dataclass(frozen=True)
class Posture:
    """The whole security picture, gathered without printing any of it."""

    document: SecurityDocument
    tls: TlsStatus
    findings: tuple[Finding, ...]
    document_error: str = ""
    studio_running: bool = False

    @property
    def exposed(self) -> bool:
        return self.document.network.exposed

    @property
    def reachable_at(self) -> str | None:
        return self.tls.reachable_at

    @property
    def auth_enabled(self) -> bool:
        return self.document.auth.enabled

    @property
    def principals(self) -> int:
        return len(self.document.auth.principals)

    @property
    def admins(self) -> int:
        return len(self.document.auth.admins())

    @property
    def farmhand_enabled(self) -> bool:
        return self.document.farmhand.enabled

    @property
    def farmhand_loopback(self) -> bool:
        return self.document.farmhand.restrict_to_loopback

    @property
    def ranges(self) -> tuple[str, ...]:
        return self.document.network.allowed_ranges

    @property
    def allowed_ranges(self) -> str:
        """The ranges as one comma-joined string, for printing."""
        return ", ".join(self.ranges)

    @property
    def trusted_proxies(self) -> str:
        return ", ".join(self.document.network.trusted_proxies)
```

Keep `worst`, `tls_on`, `fenced`, `covers_own_address()` exactly as they are. Replace `allowlist_open` and `reachable_by_others` with delegations, preserving the original docstrings:

```python
    @property
    def allowlist_open(self) -> bool:
        """True when the allowlist permits addresses beyond loopback.

        **This mirrors** ``IPAllowlistMiddleware``; it does not consult it. An
        empty list is **closed**, not open — the opposite of the usual "unset
        means unrestricted" convention, and getting it backwards is how this
        report once came to warn that an empty list allowed everyone.
        ``tests/security/test_allowlist_agreement.py`` pins both against the
        same cases so a divergence fails loudly.
        """
        return self.document.network.allowlist_open

    @property
    def reachable_by_others(self) -> bool:
        """True when a machine other than this one can actually connect.

        **The single most load-bearing value in this module.** Most rules are
        gated on it, so a wrong ``True`` costs a spurious finding while a wrong
        ``False`` hides real ones — the failure this command must not have. The
        complete truth table is asserted in ``test_posture.py``.
        """
        return self.document.network.reachable_by_others
```

4. The two entry points replace `assess`:

```python
def assess_document(
    doc: SecurityDocument,
    tls: TlsStatus,
    *,
    document_error: str = "",
    studio_running: bool = False,
) -> Posture:
    """Classify an already-loaded document. Pure — no file reads, never raises."""
    posture = Posture(
        document=doc,
        tls=tls,
        findings=(),
        document_error=document_error,
        studio_running=studio_running,
    )
    return _with_findings(posture)


def assess(*, directory: Path | None = None, path: Path | None = None) -> Posture:
    """Read every axis off disk and classify it. Never raises.

    A corrupt document is carried as :attr:`Posture.document_error` rather than
    propagated: this command's entire job is to report on a broken security
    setup, so failing to run because the setup is broken would be exactly
    backwards.
    """
    doc, error = _load_quietly(path)
    tls = tls_status(directory=directory, document=doc)
    return assess_document(doc, tls, document_error=error)


def _load_quietly(path: Path | None) -> tuple[SecurityDocument, str]:
    try:
        return load_document(path), ""
    except SecurityError as exc:
        return SecurityDocument(), str(exc)
```

5. `_with_findings` rebuilds from the new fields:

```python
def _with_findings(posture: Posture) -> Posture:
    """Attach the ordered finding list to a gathered posture."""
    findings = sorted(_findings(posture), key=lambda f: _ORDER[f.severity])
    return Posture(
        document=posture.document,
        tls=posture.tls,
        findings=tuple(findings),
        document_error=posture.document_error,
        studio_running=posture.studio_running,
    )
```

6. Rules: keep `_rule_broken_tls`, `_rule_auth_off_while_reachable`, `_rule_plain_http_while_reachable`, `_rule_no_admin`, `_rule_broad_allowlist`, `_rule_no_trusted_proxies`, `_rule_closed_allowlist` **verbatim**, with three text edits:

- `_rule_roster_unreadable` → renamed `_rule_document_unreadable`, reading `posture.document_error`, fix text `"Fix ~/.haywire/security.json by hand, or move it aside and run 'haywire auth enable'."`
- `_rule_no_trusted_proxies` fix text → `"haywire network expose --ranges <cidr> --trusted-proxies <cidr>"`
- `_rule_broad_allowlist` fix text → `"haywire network expose --ranges <a tighter subnet>"`
- `_rule_closed_allowlist` fix text → `"haywire network expose --ranges <your subnet>"`
- `_rule_plain_http_while_reachable`'s auth-off detail line about the Farmhand token is deleted (there is no separate token any more); the remaining line stays.

Every other `posture.roster_error` reference becomes `posture.document_error`.

7. Three new rules and the updated `RULES` tuple:

```python
def _rule_invariants_violated(posture: Posture) -> list[Finding]:
    """The document on disk describes a state the studio will not enter.

    Only reachable by hand-editing: every write path validates. Reported as
    CRITICAL because the gap between what the file says and what the studio
    does is exactly the misunderstanding that gets someone exposed — they read
    the file, believe it, and are wrong.
    """
    if posture.document_error:
        return []  # already reported; a default document has no violations to find
    problems = validate(posture.document)
    if not problems:
        return []
    return [
        Finding(
            Severity.CRITICAL,
            "The security document contradicts itself, so parts of it are not in force.",
            tuple(problems),
            "haywire network seal, then re-apply the settings you want through the CLI.",
        )
    ]


def _rule_farmhand_remote_without_auth(posture: Posture) -> list[Finding]:
    """The DNS-rebinding check is off and nothing else is guarding /mcp.

    CRITICAL without authentication, because with the check off and no token a
    web page the operator visits can drive this studio's tools. A NOTE with
    authentication on, where the gate demands a roster token regardless of what
    Host header the request carried.
    """
    if not posture.farmhand_enabled:
        return []
    if posture.farmhand_loopback:
        return []
    if posture.auth_enabled:
        return [
            Finding(
                Severity.NOTE,
                "Farmhand accepts MCP requests from any Host (DNS-rebinding check off).",
                ("Authentication is on, so a bearer token is still required.",),
                "haywire farmhand local-only  (to turn the check back on)",
            )
        ]
    return [
        Finding(
            Severity.CRITICAL,
            "Farmhand's DNS-rebinding check is off with authentication off.",
            (
                "Any web page you visit can post to this studio's /mcp endpoint and",
                "run its tools — including adding and executing a Python node.",
            ),
            "haywire farmhand local-only",
        )
    ]


def _rule_farmhand_reachable(posture: Posture) -> list[Finding]:
    """The MCP endpoint is served on a studio others can reach.

    A NOTE, not a warning: the gate requires a roster token here (exposure
    implies authentication), so this is a fact worth knowing rather than a gap.
    It exists because "the studio is exposed" and "an agent API is exposed with
    it" are not the same sentence in most operators' heads.
    """
    if not posture.farmhand_enabled:
        return []
    if not posture.reachable_by_others:
        return []
    return [
        Finding(
            Severity.NOTE,
            "The Farmhand MCP endpoint is reachable from the network at /mcp.",
            ("Agent principals with a roster token can drive this studio remotely.",),
            "haywire farmhand disable  (if no remote agent needs it)",
        )
    ]


RULES: tuple[Callable[[Posture], list[Finding]], ...] = (
    _rule_document_unreadable,
    _rule_invariants_violated,
    _rule_broken_tls,
    _rule_auth_off_while_reachable,
    _rule_plain_http_while_reachable,
    _rule_no_admin,
    _rule_farmhand_remote_without_auth,
    _rule_broad_allowlist,
    _rule_no_trusted_proxies,
    _rule_closed_allowlist,
    _rule_farmhand_reachable,
)
```

- [ ] **Step 5: Delete the old module and move its tests**

```bash
git rm packages/haywire-studio/src/haywire_studio/network/security.py
git mv tests/studio/test_network/test_no_false_negatives.py tests/security/test_no_false_negatives.py
git mv tests/studio/test_network/test_allowlist_agreement.py tests/security/test_allowlist_agreement.py
```

In both moved files: `from haywire_studio.network.security import ...` → `from haywire_studio.security.posture import ...`; build `Posture` via `assess_document(doc, tls)` instead of the old keyword constructor; `roster_error` → `document_error`.

- [ ] **Step 6: Run the tests**

```bash
uv run pytest tests/security/ tests/studio/test_network/ -q
```

Expected: all pass (`test_posture.py` reports `16 passed` — 12 cases plus the 4-way parametrize).

- [ ] **Step 7: Lint, format, type-check, commit**

```bash
uv run ruff check packages/haywire-studio/src/haywire_studio/security/ tests/security/
uv run ruff format packages/haywire-studio/src/haywire_studio/security/ tests/security/
uv run mypy packages/haywire-studio/src/haywire_studio/security/
git add -A packages/haywire-studio/src/haywire_studio/ tests/security/ tests/studio/test_network/
git commit -m "feat(security): posture module with pure and file-reading entry points

Adds three Farmhand/invariant rules, moves network/security.py to
security/posture.py (named after what it produces), and points tls_operations
at the document so tls_settings.py can go.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: Startup reads the document

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/network/settings.py`
- Modify: `packages/haywire-studio/src/haywire_studio/app.py`
- Delete: `packages/haywire-studio/src/haywire_studio/farmhand/settings.py`
- Delete: `tests/farmhand/test_farmhand_settings_unit.py`, `tests/farmhand/test_network_settings_unit.py`
- Test: `tests/auth/test_app_wiring.py`, new `tests/security/test_startup_sanitize.py`

**Interfaces:**
- Consumes: `load_document`, `sanitize`, `SecurityError` (Task 1); `tls_operations.status(document=...)` (Task 4)
- Produces: `HaywireApp.security_document: SecurityDocument | None` — the in-force document, read once in `run()` and the value the panel in Task 8 renders; `HaywireApp._load_security_document()`; `HaywireApp._install_auth(document)`; `HaywireApp.setup_farmhand(port, document, *, tls=False)`; `HaywireApp._install_ip_allowlist(network)`.

- [ ] **Step 1: Trim `NetworkSettings` to one field**

Replace the whole of `packages/haywire-studio/src/haywire_studio/network/settings.py`:

```python
"""Studio socket configuration (read once at startup; restart to apply)."""

from haywire.barn.builtin.types import INT
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


class NetworkSettings(FrameworkSettings, namespace="network"):
    """Where the studio's web server listens.

    **One field, deliberately.** Everything else that used to live here —
    exposure, the peer allowlist, TLS paths, the proxy list — moved to
    ``~/.haywire/security.json`` (ADR 0028), because the settings UI writes the
    *workspace* tier, a per-project file that travels into git and onto other
    machines. A port is a local convenience; an exposure decision is not, and a
    checkbox cannot express the preconditions safe exposure needs.

    A port number is not a security control: binding 8125 instead of 8124
    exposes nothing that 8124 did not.
    """

    port = setting[INT](
        8124,
        label="Studio Port",
        description="Port the studio's web server listens on. Read once at startup; restart to apply.",
        category="network",
        min=1024,
        max=65535,
    )
```

- [ ] **Step 2: Delete `FarmhandSettings` and the two settings tests**

```bash
git rm packages/haywire-studio/src/haywire_studio/farmhand/settings.py
git rm tests/farmhand/test_farmhand_settings_unit.py
git rm tests/farmhand/test_network_settings_unit.py
```

`farmhand/host.py` still imports the deleted class at this point; Task 6 removes that import. Until then `tests/farmhand/` does not collect, which is why this task verifies against `tests/security/`, `tests/auth/` and `tests/studio/test_network/` only.

- [ ] **Step 3: Write the failing startup test**

Create `tests/security/test_startup_sanitize.py`:

```python
"""Startup never refuses over a hand-edited document — it fails closed and says so."""

from __future__ import annotations

import json

from haywire.core.access import AccessTier

from haywire_studio.security.document import (
    SECURITY_VERSION,
    NetworkPolicy,
    SecurityDocument,
    load_document,
    sanitize,
)
from haywire_studio.security.roster import KIND_USER, Principal, Roster


def test_hand_edited_exposure_without_auth_boots_on_loopback(tmp_path):
    """The file claims exposure with auth off; a studio must boot, but sealed."""
    path = tmp_path / "security.json"
    path.write_text(
        json.dumps(
            {
                "version": SECURITY_VERSION,
                "auth": {"enabled": False, "session_days": 30, "principals": []},
                "network": {
                    "exposed": True,
                    "allowed_ranges": ["0.0.0.0/0"],
                    "tls_certfile": "",
                    "tls_keyfile": "",
                },
                "farmhand": {"enabled": True, "restrict_to_loopback": True},
            }
        ),
        encoding="utf-8",
    )
    clean, reasons = sanitize(load_document(path))
    assert clean.network.exposed is False
    assert len(reasons) == 2  # auth off AND no TLS


def test_hand_edited_half_tls_is_cleared_not_fatal(tmp_path):
    doc = SecurityDocument(network=NetworkPolicy(tls_certfile="/tmp/only-cert.pem"))
    clean, reasons = sanitize(doc)
    assert clean.network.tls_certfile == ""
    assert clean.network.tls_keyfile == ""
    assert reasons


def test_enabled_auth_without_an_admin_is_disabled_not_fatal():
    doc = SecurityDocument(auth=Roster(enabled=True, principals=[]))
    clean, reasons = sanitize(doc)
    assert clean.auth.enabled is False
    assert reasons


def test_a_valid_document_passes_through_untouched(tmp_path):
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")
    doc = SecurityDocument(
        auth=Roster(
            enabled=True,
            principals=[Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")],
        ),
        network=NetworkPolicy(
            exposed=True,
            allowed_ranges=("192.168.1.0/24",),
            tls_certfile=str(cert),
            tls_keyfile=str(key),
        ),
    )
    clean, reasons = sanitize(doc)
    assert reasons == []
    assert clean.network.exposed is True
```

Run: `uv run pytest tests/security/test_startup_sanitize.py -q`
Expected: `4 passed` (this exercises Task 1 code — it is here to pin the startup contract before `app.py` depends on it).

- [ ] **Step 4: Rewrite `HaywireApp.run()` and its helpers**

In `packages/haywire-studio/src/haywire_studio/app.py`:

```python
    def run(self, *, open_browser: bool = True):
        """Run the application."""
        print("Starting Haywire...")
        self.create_ui()

        from haywire_studio.network.settings import NetworkSettings

        port = NetworkSettings().port
        document = self._load_security_document()
        self.security_document = document

        network = document.network
        host = "0.0.0.0" if network.exposed else "127.0.0.1"
        ssl_kwargs = _ssl_kwargs(network.tls_certfile, network.tls_keyfile)

        # Install the gate BEFORE the Farmhand mount so the root wrapper covers
        # /mcp too — one boundary, not a boundary with a documented hole beside it.
        self._install_auth(document)

        self.setup_farmhand(port, document, tls=bool(ssl_kwargs))

        if network.exposed:
            self._install_ip_allowlist(network)

        try:
            ui.run(
                host=host,
                port=port,
                show=open_browser,
                title="Haywire",
                reload=False,
                **ssl_kwargs,  # type: ignore[arg-type]
            )
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
        finally:
            if not self._is_shutting_down:
                self.cleanup()

    @staticmethod
    def _load_security_document():
        """Read the security document, repairing a hand-edited one loudly.

        An unreadable document is fatal — it could equally be a disabled one,
        and guessing the benign reading is how a studio comes up unprotected.
        A *contradictory* document is not: it is repaired in the safe direction
        and every reason is logged at CRITICAL. Refusing to start there would be
        a lockout whose fix needs the UI it just took away.
        """
        from haywire_studio.security.document import load_document, sanitize
        from haywire_studio.security.errors import SecurityError

        try:
            raw = load_document()
        except SecurityError as exc:
            print(f"ERROR: Haywire cannot start — the security document is unreadable.\n  {exc}")
            raise SystemExit(1) from exc

        document, reasons = sanitize(raw)
        for reason in reasons:
            logger.critical("Security: %s", reason)
        if reasons:
            logger.critical(
                "Security: the document above was applied in its safe form. "
                "Run 'haywire security status' to see what is actually in force."
            )
        return document
```

`_install_auth` takes the document instead of building its own cache read:

```python
    def _install_auth(self, document) -> bool:
        """Install the gate, the login routes and the tier resolver, if enabled.

        Returns whether authentication is on. Everything here is skipped when
        the document says disabled, so an auth-off install runs exactly the code
        it ran before this feature existed.

        The *document* argument is the sanitized one ``run()`` already read and
        validated; the cache below re-reads the same file live, which is what
        makes "remove a principal" an actual revocation rather than a request.
        """
        from nicegui import app as nicegui_app

        from haywire_studio.auth.cookies import load_or_create_secret
        from haywire_studio.auth.gate import AuthGateMiddleware
        from haywire_studio.auth.live import RosterCache, install_resolver
        from haywire_studio.auth.login import register_login_routes

        if not document.auth.enabled:
            return False

        cache = RosterCache()
        secret = load_or_create_secret()
        install_resolver(cache)
        register_login_routes(cache=cache, secret=secret)
        nicegui_app.add_middleware(
            AuthGateMiddleware,
            cache=cache,
            secret=secret,
            workspace_root=self.workspace_root,
        )
        self._auth_cache = cache
        print(f"🔒 Authentication enabled — {len(document.auth.principals)} principal(s)")
        return True
```

The old "no admin exists" `SystemExit` block is deleted — `sanitize()` already turned that document into an auth-off one, and `validate()` makes it unwritable through the API.

`setup_farmhand` takes the document:

```python
    def setup_farmhand(self, port: int, document, *, tls: bool = False) -> None:
        """Mount the Farmhand MCP server if enabled (read once; restart to apply)."""
        from haywire_studio.farmhand.host import FarmhandHost

        if not document.farmhand.enabled:
            logging.getLogger(__name__).info("Farmhand: disabled (farmhand.enabled = false)")
            return
        self.farmhand_host = FarmhandHost(self.library_service, self.workspace_root)
        self.farmhand_host.mount(port, document, tls=tls)

        from pathlib import Path

        from haywire_studio.farmhand.identity import write_identity

        try:
            write_identity(Path(self.workspace_root), port, auth_required=document.auth.enabled)
        except Exception:
            logging.getLogger(__name__).warning(
                "Farmhand: failed to write studio identity sidecar", exc_info=True
            )
```

`_install_ip_allowlist` takes a `NetworkPolicy` and loses its string-splitting (the document already holds tuples). The trusted-proxies warning and the eager-validation block stay verbatim; only these lines change:

```python
    @staticmethod
    def _install_ip_allowlist(network) -> None:
        # ... existing docstring, unchanged ...
        from haywire_studio.network.ip_filter import IPAllowlistMiddleware

        allowed_ranges = list(network.allowed_ranges)
        trusted_proxies = list(network.trusted_proxies)
```

and the error message's last line becomes:

```python
                "Run 'haywire security status' to see the current configuration."
```

`_ssl_kwargs`'s half-configured message becomes:

```python
            "ERROR: Haywire cannot start — incomplete TLS configuration.\n"
            "  Set BOTH the certificate and key, or neither.\n"
            "  Run 'haywire ssl status' to see the current state."
```

Finally, `HaywireApp.__init__` gains `self.security_document = None` beside the other instance attributes, so the panel in Task 8 has a name to read whether or not `run()` has executed.

- [ ] **Step 5: Update `tests/auth/test_app_wiring.py`**

Every call to `_install_auth()` now passes a document; every fixture that wrote an `auth.json` writes a `security.json` via `save_document`. The deleted "no admin exits" test is replaced by an assertion that `_load_security_document` sanitizes instead:

```python
def test_no_admin_disables_auth_instead_of_exiting(tmp_path, monkeypatch):
    """The old behaviour was SystemExit; sanitize() makes that unreachable."""
    from haywire_studio.security.document import SecurityDocument, sanitize
    from haywire_studio.security.roster import Roster

    doc, reasons = sanitize(SecurityDocument(auth=Roster(enabled=True, principals=[])))
    assert doc.auth.enabled is False
    assert reasons
```

- [ ] **Step 6: Run the tests**

```bash
uv run pytest tests/security/ tests/auth/ tests/studio/test_network/ -q
```

Expected: all pass. `tests/farmhand/` will still fail to collect — that is Task 6.

- [ ] **Step 7: Lint, format, type-check, commit**

```bash
uv run ruff check packages/haywire-studio/src/ tests/
uv run ruff format packages/haywire-studio/src/ tests/
uv run mypy packages/haywire-studio/src/
git add -A
git commit -m "feat(security): studio startup reads the security document

NetworkSettings keeps only 'port'; FarmhandSettings is deleted. A
contradictory document is repaired at boot and logged at CRITICAL rather than
refusing to start.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: Delete the workspace Farmhand token

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/farmhand/auth.py`
- Modify: `packages/haywire-studio/src/haywire_studio/farmhand/host.py`
- Modify: `packages/haywire-studio/src/haywire_studio/farmhand/identity.py`
- Modify: `tests/farmhand/conftest.py`, `tests/farmhand/test_auth_unit.py`, `tests/farmhand/test_host_unit.py`, `tests/farmhand/test_server_integration.py`, `tests/farmhand/test_identity_unit.py`, `tests/farmhand/test_identity_startup.py`

**Interfaces:**
- Consumes: `FarmhandPolicy`, `SecurityDocument` (Task 1)
- Produces:
  - `connection_command(port, token, *, tls=False) -> str` (unchanged name, new `tls` keyword)
  - `write_identity(workspace_root, port, *, auth_required=False) -> dict`
  - `FarmhandHost.mount(port, document, app_target=None, *, tls=False) -> None`
  - `FarmhandHost._connection_hint(port, document, *, tls) -> str`

**Why this is safe:** `AuthGateMiddleware` sits on the root app and `/mcp` is mounted inside it, so an authenticated studio already demands a roster token on every `/mcp` request. The invariant `exposed ⇒ auth enabled` means an unauthenticated studio is loopback-only. There is therefore no configuration in which `/mcp` is reachable off-box without a token, and `BearerTokenMiddleware` guards nothing the gate does not.

- [ ] **Step 1: Replace `farmhand/auth.py` entirely**

```python
"""How an agent connects to the Farmhand mount.

**There is no separate MCP credential.** `/mcp` is mounted inside the studio's
own ASGI app, so ``AuthGateMiddleware`` (ADR 0027) already demands a roster
bearer token on every request when authentication is on. When it is off, the
security document's invariants guarantee the studio is loopback-only — so the
matrix is closed: no configuration exists in which `/mcp` is reachable from
another machine without a token.

The workspace token file this module used to mint (`<ws>/.haywire/farmhand_token`)
is gone with ADR 0028. It was a second credential with a second lifetime,
guarding an endpoint the bind address already guarded, and its existence made
"is /mcp protected?" a question with two answers.
"""

from __future__ import annotations


def connection_command(port: int, token: str | None, *, tls: bool = False) -> str:
    """The ``claude mcp add`` line for this studio.

    *token* is a roster agent's token, or ``None`` when authentication is off
    and no header is needed. The scheme follows actual TLS, because a client
    told ``http://`` against an HTTPS studio fails in a way that looks like the
    server is down.
    """
    scheme = "https" if tls else "http"
    base = f"claude mcp add --transport http farmhand {scheme}://127.0.0.1:{port}/mcp"
    if token is None:
        return base
    return f'{base} --header "Authorization: Bearer {token}"'
```

- [ ] **Step 2: Rewrite `FarmhandHost.mount()`**

Replace the import of `.auth` and `.settings`, and the body of `mount`:

```python
from .auth import connection_command
```

```python
    def mount(self, port: int, document, app_target: Any = None, *, tls: bool = False) -> None:
        """Mount /mcp on the studio app.

        No bearer middleware of its own: the root ``AuthGateMiddleware`` covers
        this mount, and a second token check beneath it would be a settings flag
        acting as a security control — the exact shape ADR 0027 set out to avoid.
        """
        target = app_target if app_target is not None else nicegui_app
        policy = document.farmhand

        if policy.restrict_to_loopback:
            allowed_hosts = [f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"]
            scheme = _origin_scheme(tls=tls)
            allowed_origins = [f"{scheme}://127.0.0.1:{port}", f"{scheme}://localhost:{port}"]

            public_hostname = document.network.public_hostname
            if public_hostname:
                allowed_hosts.append(public_hostname)
                if ":" not in public_hostname:
                    allowed_hosts.append(f"{public_hostname}:{port}")
                allowed_origins.append(f"http://{public_hostname}")
                allowed_origins.append(f"https://{public_hostname}")

            security = TransportSecuritySettings(
                allowed_hosts=allowed_hosts,
                allowed_origins=allowed_origins,
            )
        else:
            security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        self._session_manager = StreamableHTTPSessionManager(app=self._server, security_settings=security)

        async def asgi(scope, receive, send):
            assert self._session_manager is not None
            await self._session_manager.handle_request(scope, receive, send)

        target.mount("/mcp", asgi)
        if target is nicegui_app:
            nicegui_app.on_startup(self._on_startup)
            nicegui_app.on_shutdown(self._on_shutdown)

        hint = self._connection_hint(port, document, tls=tls)
        logger.info(f"Farmhand MCP server will serve at /mcp — connect with:\n  {hint}")
        print(f"🤝 Farmhand: {hint}")

    @staticmethod
    def _connection_hint(port: int, document, *, tls: bool) -> str:
        """The connect line, naming a real agent token when one exists.

        With authentication on, printing a header-less command would hand the
        operator something that returns 401. Printing the *first* agent
        principal's token is right far more often than not — most studios have
        exactly one — and when there is none, saying so beats a command that
        cannot work.
        """
        if not document.auth.enabled:
            return connection_command(port, None, tls=tls)
        agents = [p for p in document.auth.principals if p.is_agent]
        if not agents:
            return (
                "authentication is on but no agent principal exists — create one with:\n"
                "  haywire user add <name> --agent --tier edit"
            )
        return connection_command(port, agents[0].token, tls=tls)
```

Delete the now-unused `from ..network.settings import NetworkSettings` and `from .settings import FarmhandSettings` imports.

- [ ] **Step 3: Add `auth_required` to the sidecar**

In `packages/haywire-studio/src/haywire_studio/farmhand/identity.py`, change the module docstring's second paragraph to drop the `farmhand_token` reference, and:

```python
def write_identity(workspace_root: Path | str, port: int, *, auth_required: bool = False) -> dict:
    """Write the current process's studio identity to <workspace>/.haywire/studio.json.

    ``auth_required`` tells an out-of-process client (the farmhand4claude proxy)
    whether `/mcp` will demand a bearer token, so it can connect header-less
    against an unauthenticated studio instead of guessing. It is a *hint*, never
    a credential — the sidecar is machine-local and gitignored, but it is not
    0600 and must never carry a token.

    Returns the dict written. Ensures the sidecar is gitignored.
    """
    root = Path(workspace_root).resolve()
    haywire_dir = root / ".haywire"
    haywire_dir.mkdir(parents=True, exist_ok=True)
    _ensure_gitignored(haywire_dir)

    ident = {
        "pid": os.getpid(),
        "port": port,
        "project": root.name,
        "project_path": str(root),
        "started_at": time.time(),
        "host": socket.gethostname(),
        "role": "haywire-studio",
        "url": f"http://127.0.0.1:{port}",
        "auth_required": auth_required,
    }
    (haywire_dir / IDENTITY_FILENAME).write_text(json.dumps(ident, indent=2), encoding="utf-8")
    return ident
```

- [ ] **Step 4: Rewrite `tests/farmhand/test_auth_unit.py`**

The token tests are gone; what remains is the connection command:

```python
"""The Farmhand connection command. There is no separate MCP token any more."""

from __future__ import annotations

from haywire_studio.farmhand.auth import connection_command


def test_connection_command_contains_endpoint_and_header():
    line = connection_command(8082, "sekrit")
    assert "http://127.0.0.1:8082/mcp" in line
    assert 'Authorization: Bearer sekrit' in line


def test_connection_command_omits_header_when_token_is_none():
    line = connection_command(8082, None)
    assert "Authorization" not in line
    assert "http://127.0.0.1:8082/mcp" in line


def test_connection_command_uses_https_under_tls():
    line = connection_command(8082, None, tls=True)
    assert "https://127.0.0.1:8082/mcp" in line
```

- [ ] **Step 5: Update the remaining Farmhand tests**

- `tests/farmhand/conftest.py`: drop the `ensure_token` import and the `token=` argument; where a `FarmhandHost` is mounted, pass a `SecurityDocument()`.
- `tests/farmhand/test_host_unit.py:158`: the assertion that no token file exists stays but its import changes; add a positive assertion that no `BearerTokenMiddleware` wraps the mount.
- `tests/farmhand/test_server_integration.py:159-166`: delete the `ensure_token`-during-mount test entirely and replace with:

```python
def test_mount_writes_no_token_file(workspace):
    """ADR 0028: /mcp carries no credential of its own."""
    assert not (workspace / ".haywire" / "farmhand_token").exists()
```

- `tests/farmhand/test_identity_unit.py`: add

```python
def test_identity_records_auth_required(tmp_path):
    ident = write_identity(tmp_path, 8124, auth_required=True)
    assert ident["auth_required"] is True
    assert json.loads((tmp_path / ".haywire" / "studio.json").read_text())["auth_required"] is True


def test_identity_defaults_auth_required_false(tmp_path):
    assert write_identity(tmp_path, 8124)["auth_required"] is False
```

- [ ] **Step 6: Run the Farmhand tests**

Run: `uv run pytest tests/farmhand/ -q`
Expected: all pass.

- [ ] **Step 7: Confirm the token is gone from the source tree**

```bash
grep -rn "farmhand_token\|ensure_token\|BearerTokenMiddleware" packages/ barn/ tests/ --include="*.py"
```

Expected: no output.

- [ ] **Step 8: Lint, format, type-check, commit**

```bash
uv run ruff check packages/haywire-studio/src/ tests/
uv run ruff format packages/haywire-studio/src/ tests/
uv run mypy packages/haywire-studio/src/
git add -A
git commit -m "feat(farmhand): delete the workspace token; the root gate is the only credential

/mcp is mounted inside the gated app, and 'exposed implies auth enabled' means
an unauthenticated studio is loopback-only — so no configuration exists where
/mcp is reachable off-box without a roster token. studio.json gains
auth_required so an out-of-process client knows which to send.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: The CLI

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/cli/networkcmd.py`
- Create: `packages/haywire-studio/src/haywire_studio/cli/farmhandcmd.py`
- Modify: `packages/haywire-studio/src/haywire_studio/cli/__init__.py`
- Modify: `packages/haywire-studio/src/haywire_studio/cli/authcmd.py`
- Modify: `packages/haywire-studio/src/haywire_studio/cli/user.py`
- Modify: `packages/haywire-studio/src/haywire_studio/cli/sslcmd.py`
- Modify: `packages/haywire-studio/src/haywire_studio/cli/securitycmd.py`
- Modify: `tests/test_auth_cli.py`
- Test: `tests/test_network_cli.py`, `tests/test_farmhand_cli.py`

**Interfaces:**
- Consumes: `expose`, `seal`, `set_farmhand_enabled`, `set_farmhand_loopback` (Task 2); `assess` (Task 4); `guard_running_studio` (existing)
- Produces: two `register(subparsers)` functions matching the `_SubcommandModule` protocol

- [ ] **Step 1: Write the failing CLI tests**

Create `tests/test_network_cli.py`:

```python
"""``haywire network`` — exposure is a verb with preconditions."""

from __future__ import annotations

import argparse

import pytest

from haywire.core.access import AccessTier

from haywire_studio.cli import networkcmd
from haywire_studio.security.document import (
    NetworkPolicy,
    SecurityDocument,
    load_document,
    save_document,
)
from haywire_studio.security.roster import KIND_USER, Principal, Roster


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


@pytest.fixture(autouse=True)
def studio_stopped(monkeypatch):
    monkeypatch.setattr(networkcmd, "_studio_is_running", lambda: False)


def _parse(argv, path):
    """Parse, then stamp the document path on.

    Stamped afterwards rather than passed as ``--document`` in *argv*: the flag
    is declared on the parent ``network`` parser, so argparse only accepts it
    *before* the subcommand. Setting the attribute is what ``tests/test_auth_cli.py``
    already does, and it keeps the argv in these tests looking like what a user
    actually types.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    networkcmd.register(subparsers)
    args = parser.parse_args(argv)
    args.document = str(path)
    return args


def _ready(path, tmp_path):
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")
    save_document(
        SecurityDocument(
            auth=Roster(
                enabled=True,
                principals=[
                    Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")
                ],
            ),
            network=NetworkPolicy(tls_certfile=str(cert), tls_keyfile=str(key)),
        ),
        path,
    )


def test_expose_requires_ranges(path):
    with pytest.raises(SystemExit):
        _parse(["network", "expose"], path)


def test_expose_refuses_without_auth(path, capsys):
    save_document(SecurityDocument(), path)
    args = _parse(["network", "expose", "--ranges", "192.168.1.0/24"], path)
    assert args.handler(args) == 1
    assert "haywire auth enable" in capsys.readouterr().out


def test_expose_succeeds_when_ready(path, tmp_path, capsys):
    _ready(path, tmp_path)
    args = _parse(["network", "expose", "--ranges", "192.168.1.0/24"], path)
    assert args.handler(args) == 0
    assert load_document(path).network.exposed is True
    assert "192.168.1.0/24" in capsys.readouterr().out


def test_expose_accepts_a_comma_list(path, tmp_path):
    _ready(path, tmp_path)
    args = _parse(["network", "expose", "--ranges", "192.168.1.0/24,10.0.0.0/16"], path)
    assert args.handler(args) == 0
    assert load_document(path).network.allowed_ranges == ("192.168.1.0/24", "10.0.0.0/16")


def test_seal_turns_exposure_off(path, tmp_path):
    _ready(path, tmp_path)
    expose_args = _parse(["network", "expose", "--ranges", "192.168.1.0/24"], path)
    expose_args.handler(expose_args)
    seal_args = _parse(["network", "seal"], path)
    assert seal_args.handler(seal_args) == 0
    assert load_document(path).network.exposed is False


def test_expose_refuses_while_the_studio_runs(path, tmp_path, monkeypatch, capsys):
    _ready(path, tmp_path)
    monkeypatch.setattr(networkcmd, "_studio_is_running", lambda: True)
    args = _parse(["network", "expose", "--ranges", "192.168.1.0/24"], path)
    assert args.handler(args) == 1
    assert "a studio is running" in capsys.readouterr().out


def test_status_always_exits_zero(path, tmp_path, capsys):
    save_document(SecurityDocument(), path)
    args = _parse(["network", "status"], path)
    args.dir = str(tmp_path / "certs")  # never read the real ~/.haywire/certs
    assert args.handler(args) == 0
    assert "loopback" in capsys.readouterr().out.lower()
```

Create `tests/test_farmhand_cli.py`:

```python
"""``haywire farmhand`` — the MCP mount's two switches."""

from __future__ import annotations

import argparse

import pytest

from haywire.core.access import AccessTier

from haywire_studio.cli import farmhandcmd
from haywire_studio.security.document import SecurityDocument, load_document, save_document
from haywire_studio.security.roster import KIND_USER, Principal, Roster


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


@pytest.fixture(autouse=True)
def studio_stopped(monkeypatch):
    monkeypatch.setattr(farmhandcmd, "_studio_is_running", lambda: False)


def _parse(argv, path):
    """Parse, then stamp the document path on.

    Stamped afterwards rather than passed as ``--document`` in *argv*: the flag
    is declared on the parent ``farmhand`` parser, so argparse only accepts it
    *before* the subcommand. Matches ``tests/test_auth_cli.py``.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    farmhandcmd.register(subparsers)
    args = parser.parse_args(argv)
    args.document = str(path)
    return args


def test_disable_turns_the_mount_off(path):
    save_document(SecurityDocument(), path)
    args = _parse(["farmhand", "disable"], path)
    assert args.handler(args) == 0
    assert load_document(path).farmhand.enabled is False


def test_enable_turns_it_back_on(path):
    save_document(SecurityDocument(), path)
    for verb in ("disable", "enable"):
        args = _parse(["farmhand", verb], path)
        args.handler(args)
    assert load_document(path).farmhand.enabled is True


def test_allow_remote_refuses_without_auth(path, capsys):
    save_document(SecurityDocument(), path)
    args = _parse(["farmhand", "allow-remote"], path)
    assert args.handler(args) == 1
    assert "haywire auth enable" in capsys.readouterr().out


def test_allow_remote_works_with_auth_on(path):
    save_document(
        SecurityDocument(
            auth=Roster(
                enabled=True,
                principals=[
                    Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")
                ],
            )
        ),
        path,
    )
    args = _parse(["farmhand", "allow-remote"], path)
    assert args.handler(args) == 0
    assert load_document(path).farmhand.restrict_to_loopback is False


def test_local_only_needs_no_auth(path):
    save_document(SecurityDocument(), path)
    args = _parse(["farmhand", "local-only"], path)
    assert args.handler(args) == 0
    assert load_document(path).farmhand.restrict_to_loopback is True


def test_status_reports_both_switches(path, capsys):
    save_document(SecurityDocument(), path)
    args = _parse(["farmhand", "status"], path)
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "/mcp" in out
    assert "local" in out.lower()
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_network_cli.py tests/test_farmhand_cli.py -q`
Expected: `ModuleNotFoundError: No module named 'haywire_studio.cli.networkcmd'`

- [ ] **Step 3: Write `cli/networkcmd.py`**

```python
"""``haywire network`` — where the studio can be reached from.

Exposure used to be a checkbox in a settings panel. It is a verb here because
safe exposure is three coordinated decisions, and a checkbox cannot express a
precondition: it can only be flipped, after which the studio is open and the
operator finds out what that meant later.

Every refusal names the one command that clears it. The refusals themselves
live in the document's ``validate`` (ADR 0028), not here — a second copy in the
CLI is a second copy that can disagree with the one the studio boots against.

Named ``networkcmd`` to match the ``authcmd``/``sslcmd``/``securitycmd`` dodge
around stdlib and namespace collisions.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from haywire_studio.cli._guards import studio_is_running
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.operations import expose, seal
from haywire_studio.security.posture import assess


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("network", help="Expose the studio to the network, or seal it")
    parser.add_argument(
        "--document",
        default=None,
        help="Security document to operate on (default: ~/.haywire/security.json). Mainly for testing.",
    )
    parser.add_argument(
        "--dir",
        default=None,
        help="Certificate directory (default: ~/.haywire/certs). Mainly for testing.",
    )
    actions = parser.add_subparsers(dest="network_command", required=True)

    opened = actions.add_parser("expose", help="Bind beyond loopback for the given CIDR ranges")
    opened.add_argument(
        "--ranges",
        required=True,
        help="Comma-separated CIDR ranges allowed to reach the studio (e.g. '192.168.1.0/24')",
    )
    opened.add_argument(
        "--hostname",
        default=None,
        help="Public hostname the studio is reachable at, for the MCP Host/Origin list",
    )
    opened.add_argument(
        "--trusted-proxies",
        default=None,
        help="Comma-separated CIDR ranges whose X-Forwarded-For headers are trusted",
    )
    opened.set_defaults(handler=_expose)

    closed = actions.add_parser("seal", help="Bind to loopback again (the allowlist is kept)")
    closed.set_defaults(handler=_seal)

    report = actions.add_parser("status", help="Show where the studio can be reached from")
    report.set_defaults(handler=_status)


def _path(args: argparse.Namespace, name: str) -> Path | None:
    raw = getattr(args, name, None)
    return Path(raw) if raw else None


def _studio_is_running() -> bool:
    """Module-level seam, so tests can pin it (mirrors ``authcmd``)."""
    return studio_is_running()


def _guard() -> bool:
    if _studio_is_running():
        print(
            "ERROR: a studio is running in this workspace.\n"
            "  The bind address is read once at startup, so it must be changed with the "
            "studio stopped.\n"
            "  Quit the studio and run this again."
        )
        return True
    return False


def _split(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [entry.strip() for entry in raw.split(",") if entry.strip()]


def _expose(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    path = _path(args, "document")
    try:
        doc = expose(
            _split(args.ranges) or [],
            public_hostname=args.hostname,
            trusted_proxies=_split(args.trusted_proxies),
            path=path,
        )
    except SecurityError as exc:
        print(f"ERROR: the studio was not exposed.\n  {exc}")
        return 1

    print("The studio is now exposed beyond loopback.")
    print(f"  Allowed: {', '.join(doc.network.allowed_ranges)}")
    print("  Authentication is on and TLS is configured.")
    if not doc.network.trusted_proxies:
        print(
            "\nNote: no trusted proxies are configured, so X-Forwarded-For headers are\n"
            "  ignored. Only matters behind a reverse proxy — there, every client would\n"
            "  otherwise appear to be the proxy."
        )
    print("\nStart the studio for this to take effect.")
    return 0


def _seal(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    try:
        doc = seal(path=_path(args, "document"))
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    kept = ", ".join(doc.network.allowed_ranges)
    print("The studio is now loopback-only. Restart it for this to take effect.")
    if kept:
        print(f"  The allowlist was kept ({kept}) and applies again after 'haywire network expose'.")
    return 0


def _status(args: argparse.Namespace) -> int:
    """Always exits 0 — reports rather than judges, like ``ssl status``."""
    posture = assess(directory=_path(args, "dir"), path=_path(args, "document"))
    net = posture.document.network

    if not posture.exposed:
        print("Network: loopback only (127.0.0.1) — nothing leaves this machine.")
    elif not posture.allowlist_open:
        print("Network: bound beyond loopback, but the allowlist is empty — only loopback connects.")
    else:
        where = posture.reachable_at or "this machine"
        print(f"Network: exposed at {where}")
        print(f"  Allowed:  {posture.allowed_ranges}")

    if net.trusted_proxies:
        print(f"  Proxies:  {posture.trusted_proxies}")
    if net.public_hostname:
        print(f"  Hostname: {net.public_hostname}")

    print("\nFull picture:  haywire security status")
    return 0
```

- [ ] **Step 4: Write `cli/farmhandcmd.py`**

```python
"""``haywire farmhand`` — the MCP endpoint's two switches.

Both are read once at startup. Neither is a settings field any more (ADR 0028):
``enabled`` decides whether an agent API exists at all, and
``restrict_to_loopback`` is the DNS-rebinding defence — a control whose whole
value is that a user cannot casually toggle it while reading a tooltip.

MCP is the protocol; Farmhand is the component. The command is named for the
component, matching ``FarmhandHost``, ``farmhand://`` resource URIs and the
glossary.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from haywire_studio.cli._guards import studio_is_running
from haywire_studio.security.document import load_document
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.operations import set_farmhand_enabled, set_farmhand_loopback


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("farmhand", help="Configure the Farmhand MCP endpoint at /mcp")
    parser.add_argument(
        "--document",
        default=None,
        help="Security document to operate on (default: ~/.haywire/security.json). Mainly for testing.",
    )
    actions = parser.add_subparsers(dest="farmhand_command", required=True)

    on = actions.add_parser("enable", help="Serve the MCP endpoint at /mcp")
    on.set_defaults(handler=_enable)

    off = actions.add_parser("disable", help="Stop serving the MCP endpoint")
    off.set_defaults(handler=_disable)

    local = actions.add_parser("local-only", help="Reject MCP requests whose Host is not loopback")
    local.set_defaults(handler=_local_only)

    remote = actions.add_parser("allow-remote", help="Accept MCP requests from any Host")
    remote.set_defaults(handler=_allow_remote)

    report = actions.add_parser("status", help="Show the Farmhand configuration")
    report.set_defaults(handler=_status)


def _path(args: argparse.Namespace) -> Path | None:
    raw = getattr(args, "document", None)
    return Path(raw) if raw else None


def _studio_is_running() -> bool:
    """Module-level seam, so tests can pin it (mirrors ``authcmd``)."""
    return studio_is_running()


def _guard() -> bool:
    if _studio_is_running():
        print(
            "ERROR: a studio is running in this workspace.\n"
            "  Farmhand configuration is read once at startup, so it must be changed with "
            "the studio stopped.\n"
            "  Quit the studio and run this again."
        )
        return True
    return False


def _enable(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    try:
        set_farmhand_enabled(True, path=_path(args))
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    print("Farmhand enabled — the studio will serve MCP at /mcp. Restart it to apply.")
    return 0


def _disable(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    try:
        set_farmhand_enabled(False, path=_path(args))
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    print("Farmhand disabled — /mcp will not be served. Restart the studio to apply.")
    return 0


def _local_only(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    try:
        set_farmhand_loopback(True, path=_path(args))
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(
        "Farmhand now rejects MCP requests whose Host/Origin is not loopback.\n"
        "  This is DNS-rebinding protection: it stops a web page in your browser from\n"
        "  driving this studio's tools. Restart the studio to apply."
    )
    return 0


def _allow_remote(args: argparse.Namespace) -> int:
    if _guard():
        return 1
    try:
        set_farmhand_loopback(False, path=_path(args))
    except SecurityError as exc:
        print(f"ERROR: Farmhand still accepts loopback requests only.\n  {exc}")
        return 1
    print(
        "Farmhand now accepts MCP requests from any Host.\n"
        "  The DNS-rebinding check is off; the roster bearer token is what guards /mcp.\n"
        "  Restart the studio to apply."
    )
    return 0


def _status(args: argparse.Namespace) -> int:
    """Always exits 0 — reports rather than judges."""
    try:
        doc = load_document(_path(args))
    except SecurityError as exc:
        print(f"Farmhand state is UNKNOWN — the security document could not be read.\n  {exc}")
        return 0

    if not doc.farmhand.enabled:
        print("Farmhand: disabled — /mcp is not served.")
        return 0

    print("Farmhand: enabled — serving MCP at /mcp")
    if doc.farmhand.restrict_to_loopback:
        print("  Hosts:  loopback only (DNS-rebinding protection on)")
    else:
        print("  Hosts:  any (DNS-rebinding protection OFF)")
    if doc.auth.enabled:
        agents = [p for p in doc.auth.principals if p.is_agent]
        print(f"  Token:  required — {len(agents)} agent principal(s) in the roster")
    else:
        print("  Token:  not required (authentication is off, so the studio is loopback-only)")

    print("\nFull picture:  haywire security status")
    return 0
```

- [ ] **Step 5: Register both subcommands**

In `packages/haywire-studio/src/haywire_studio/cli/__init__.py`, add `farmhandcmd` and `networkcmd` to the import block and to `SUBCOMMANDS`, ordered so the security axes read together:

```python
from haywire_studio.cli import (
    authcmd,
    deps,
    docs,
    farmhandcmd,
    init,
    networkcmd,
    rename,
    securitycmd,
    share,
    sslcmd,
    user,
    verify,
)

SUBCOMMANDS: Sequence[_SubcommandModule] = (
    init,
    share,
    rename,
    deps,
    docs,
    verify,
    user,
    authcmd,
    sslcmd,
    networkcmd,
    farmhandcmd,
    securitycmd,
)
```

- [ ] **Step 6: Rewire the three existing security subcommands**

**`authcmd.py`:** delete `_offer_token_import` entirely and its call in `_enable`; delete the now-unused `Principal`/`AccessTier`/`save_roster` imports. Rename `--roster` to `--document` (help text: `"Security document to operate on (default: ~/.haywire/security.json). Mainly for testing."`) and `_roster_path` to `_document_path`. Replace `RosterError` with `SecurityError`, and `from haywire_studio.network.security import assess, Severity` with `from haywire_studio.security.posture import assess, Severity`; `assess(roster_path=...)` becomes `assess(path=...)`, and `posture.roster_error` becomes `posture.document_error`. `_disable`'s success message gains a line:

```python
    print("Authentication disabled. Everyone who can reach the studio is now a full operator.")
```

and its `except` branch gains the seal hint, because the exposure invariant is the likeliest refusal:

```python
    except SecurityError as exc:
        print(f"ERROR: {exc}")
        if "exposed" in str(exc):
            print("  Run 'haywire network seal' first.")
        return 1
```

**`user.py`:** `--roster` → `--document`, `_roster_path` → `_document_path`, `RosterError` → `SecurityError`, `load_roster(p)` → `load_document(p).auth`. `_add`'s agent branch gains the connection hint:

```python
            print("  Give this to the agent — it is stored in the roster and can be re-read at any time.")
            print(f"  Connect with:  haywire farmhand status")
```

**`sslcmd.py`:** delete the whole `from haywire_studio.network.tls_settings import (...)` block at lines 36–38 and add `from haywire_studio.security.errors import SecurityError`. The two `except (CertError, SettingsWriteError)` clauses (lines 91, 118) become `except (CertError, SecurityError)`. Delete the `shadowed = workspace_overrides("ssl_certfile", "ssl_keyfile")` calls at lines 184 and 302 **together with the warning blocks that consume them** — the workspace settings tier can no longer shadow TLS, so the warning has nothing left to warn about. Every `settings_path=` keyword on a `tls_operations` call becomes `path=`.

Verify:

```bash
grep -n "tls_settings\|SettingsWriteError\|workspace_overrides" packages/haywire-studio/src/haywire_studio/cli/sslcmd.py
```

Expected: no output.

**`securitycmd.py`:** `--roster` → `--document`; `assess(directory=..., roster_path=...)` → `assess(directory=..., path=...)`; `posture.roster_error` → `posture.document_error`; import from `haywire_studio.security.posture`. `_print_axes` gains a fourth line and `_clean_verdict`'s closing hint is updated:

```python
def _print_axes(posture: Posture) -> None:
    """The verdict first, then the four axes as facts behind it."""
    print("-" * 60)
    print(f" Security status: {_general_assesment(posture)}")
    print("-" * 60)
    print()
    print(f"  Network:  {_network_line(posture)}")
    print(f"  Auth:     {_auth_line(posture)}")
    print(f"  TLS:      {_tls_line(posture)}")
    print(f"  Farmhand: {_farmhand_line(posture)}")


def _farmhand_line(posture: Posture) -> str:
    if not posture.farmhand_enabled:
        return "disabled — /mcp is not served"
    hosts = "loopback only" if posture.farmhand_loopback else "ANY host (rebinding check off)"
    token = "roster token required" if posture.auth_enabled else "no token (studio is loopback-only)"
    return f"enabled at /mcp — {hosts}, {token}"
```

and in `_clean_verdict`, the pre-exposure hint becomes:

```python
            "Before opening it up, run:  haywire auth enable  and  haywire ssl setup\n"
            "Then:  haywire network expose --ranges <your subnet>"
```

- [ ] **Step 7: Update `tests/test_auth_cli.py`**

Five edits:

1. Delete `test_enable_imports_an_existing_farmhand_token`, its sibling at line 125, and `test_enable_without_a_farmhand_token_asks_nothing` — the behaviour they pin no longer exists.
2. **Delete the `_neutral_workspace` autouse fixture (lines 34–47).** It exists solely because `_offer_token_import` read `<cwd>/.haywire/farmhand_token` and would otherwise block the suite on an interactive prompt. Both the function and the file are gone, so the fixture now guards nothing.
3. Line 9: `from haywire_studio.auth.roster import load_roster` → `from haywire_studio.security.document import load_document`, and every `load_roster(path)` call site becomes `load_document(path).auth`.
4. Line 25 in `_run`: `args.roster = str(path)` → `args.document = str(path)`.
5. Line 31: the `path` fixture returns `tmp_path / "security.json"`.

Then add one test for the new refusal. It uses the file's existing `_run` helper, which stamps the path onto the namespace **after** parsing (the `--document` flag is declared on the parent `auth` parser, so argparse would only accept it before the subcommand) and returns the handler's exit code:

```python
def _ready_and_exposed(path, tmp_path):
    """Auth on with an admin, TLS configured, and exposed — the one state in
    which 'auth disable' must be refused."""
    from haywire.core.access import AccessTier

    from haywire_studio.auth.passwords import hash_password
    from haywire_studio.security.document import (
        NetworkPolicy,
        SecurityDocument,
        save_document,
    )
    from haywire_studio.security.operations import expose
    from haywire_studio.security.roster import KIND_USER, Principal, Roster

    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")
    save_document(
        SecurityDocument(
            auth=Roster(
                enabled=True,
                principals=[
                    Principal(
                        name="root",
                        kind=KIND_USER,
                        tier=AccessTier.ADMIN,
                        # STRONG, module-level — the password policy rejects weak ones
                        # and add_user is not on this path to check it for us.
                        password_hash=hash_password(STRONG),
                    )
                ],
            ),
            network=NetworkPolicy(tls_certfile=str(cert), tls_keyfile=str(key)),
        ),
        path,
    )
    expose(["192.168.1.0/24"], path=path)


def test_disable_refuses_while_exposed(path, tmp_path, monkeypatch, capsys):
    """The exposure invariant makes 'disable auth on an exposed studio' unwritable."""
    from haywire_studio.security.document import load_document

    _ready_and_exposed(path, tmp_path)
    assert _run(["auth", "disable"], monkeypatch, path, username="root", password=STRONG) == 1
    assert "haywire network seal" in capsys.readouterr().out
    assert load_document(path).auth.enabled is True
```

- [ ] **Step 8: Run the CLI tests**

```bash
uv run pytest tests/test_network_cli.py tests/test_farmhand_cli.py tests/test_auth_cli.py -q
```

Expected: all pass.

- [ ] **Step 9: Smoke-test the real CLI**

```bash
uv run haywire --help
uv run haywire network --help
uv run haywire farmhand --help
uv run haywire security status
```

Expected: `network` and `farmhand` appear in the top-level help; `security status` prints four axis lines.

- [ ] **Step 10: Lint, format, type-check, commit**

```bash
uv run ruff check packages/haywire-studio/src/ tests/
uv run ruff format packages/haywire-studio/src/ tests/
uv run mypy packages/haywire-studio/src/
git add -A
git commit -m "feat(cli): haywire network expose|seal and haywire farmhand

security status becomes report-only across four axes; the workspace token
import in 'auth enable' is deleted with the token it imported.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: The read-only Security panel

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/panels/properties/setting/app.py`
- Modify: `barn/haybale-studio/haybale_studio/editors/roster_editor.py` (imports only)
- Test: `tests/barn/test_security_panel.py`

**Interfaces:**
- Consumes: `HaywireApp.security_document` (Task 5); `assess_document`, `Severity` (Task 4); `status as tls_status` from `network/tls_operations.py`
- Produces: `SecurityPanel` — an `AppFocus` panel at `access=AccessTier.ADMIN`

**Design note:** the panel renders what is **in force** (the document the running studio booted with), never a fresh disk read. A panel that re-read the file would report a change the studio has not applied, which is the same false confidence the settings checkbox produced.

- [ ] **Step 1: Write the failing test**

Create `tests/barn/test_security_panel.py`:

```python
"""The Security panel reports the in-force document, and writes nothing."""

from __future__ import annotations

import inspect

from haywire.core.access import AccessTier


def test_panel_is_admin_gated():
    from haybale_studio.panels.properties.setting.app import SecurityPanel

    assert SecurityPanel.class_identity.access is AccessTier.ADMIN


def test_network_settings_panel_is_gone():
    """The writable panel must not survive alongside the read-only one."""
    import haybale_studio.panels.properties.setting.app as module

    assert not hasattr(module, "NetworkSettingsPanel")


def test_panel_renders_no_security_schema():
    """render_schema on NetworkSettings would put 'port' in front of an admin —
    fine — but any other bag here would be a writable security control."""
    from haybale_studio.panels.properties.setting.app import SecurityPanel

    source = inspect.getsource(SecurityPanel)
    assert "FarmhandSettings" not in source
    assert "render_schema(NetworkSettings" in source


def test_panel_reads_the_in_force_document_not_disk():
    """A disk read here would report a change the running studio has not applied."""
    from haybale_studio.panels.properties.setting.app import SecurityPanel

    source = inspect.getsource(SecurityPanel)
    assert "security_document" in source
    assert "load_document" not in source
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/barn/test_security_panel.py -q`
Expected: `ImportError: cannot import name 'SecurityPanel'`

- [ ] **Step 3: Replace `NetworkSettingsPanel` with `SecurityPanel`**

In `barn/haybale-studio/haybale_studio/panels/properties/setting/app.py`, update the module docstring's last line to `SecurityPanel — read-only posture report plus the studio port` and replace the two Farmhand/Network imports with:

```python
from haywire.core.access import AccessTier
from haywire_studio.network.settings import NetworkSettings
from haywire_studio.network.tls_operations import status as tls_status
from haywire_studio.security.posture import Severity, assess_document
```

Then replace the whole `NetworkSettingsPanel` class with:

```python
_MARKERS = {
    Severity.CRITICAL: ("CRITICAL", "text-red-400"),
    Severity.WARNING: ("WARNING", "text-amber-400"),
    Severity.NOTE: ("note", "text-slate-400"),
}


@panel(
    focus=AppFocus,
    label="Security",
    icon=hui.icon.severity,
    order=40,
    default_open=False,
    access=AccessTier.ADMIN,
)
class SecurityPanel(BasePanel):
    """What this studio's defences currently are — read-only (ADR 0028).

    **Deliberately not editable.** Exposure, the peer allowlist, TLS and the
    Farmhand switches all left the settings system precisely because a panel
    that writes them writes the *workspace* settings tier, a per-project file
    that travels into git and onto other machines. They are changed with
    ``haywire network``, ``haywire auth``, ``haywire ssl`` and
    ``haywire farmhand``, with the studio stopped, because every one of them is
    read once at startup.

    The port stays here: it is a local convenience, not a security control.
    """

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        document = getattr(ctx.app, "security_document", None)
        if document is None:
            hui.label("Security state is unavailable — the studio was started without one.")
            return

        posture = assess_document(document, tls_status(document=document))
        self._draw_axes(posture)
        self._draw_findings(posture)

        registry = ctx.app.library_service.get_settings_registry()
        render_schema(NetworkSettings, registry)

    def _draw_axes(self, posture) -> None:
        network = (
            f"exposed at {posture.reachable_at or 'this machine'} ({posture.allowed_ranges})"
            if posture.reachable_by_others
            else "loopback only"
        )
        auth = f"{posture.principals} principal(s)" if posture.auth_enabled else "off"
        tls = "on — HTTPS" if posture.tls_on else "off — plain HTTP"
        farmhand = "off" if not posture.farmhand_enabled else (
            "/mcp, loopback only" if posture.farmhand_loopback else "/mcp, ANY host"
        )
        for label, value in (
            ("Network", network),
            ("Auth", auth),
            ("TLS", tls),
            ("Farmhand", farmhand),
        ):
            with hui.row():
                hui.label(label).classes("w-24 opacity-70")
                hui.label(value)

    def _draw_findings(self, posture) -> None:
        if not posture.findings:
            hui.label("Nothing to fix.").classes("mt-2 opacity-70")
            return
        for finding in posture.findings:
            marker, colour = _MARKERS[finding.severity]
            with hui.column().classes("mt-2 gap-0"):
                hui.label(f"[{marker}] {finding.headline}").classes(colour)
                for line in finding.detail:
                    hui.label(line).classes("text-xs opacity-70")
                if finding.fix:
                    # Copyable, because the fix is a command to paste into a
                    # terminal — with the studio stopped, which is the one moment
                    # this panel is no longer on screen to read it from.
                    hui.code(finding.fix).classes("text-xs")
```

- [ ] **Step 4: Fix `roster_editor.py`'s imports**

```bash
grep -n "auth.roster\|RosterError\|load_roster\|save_roster" \
  barn/haybale-studio/haybale_studio/editors/roster_editor.py
```

Replace each with the `haywire_studio.security.*` equivalent: `Principal`/`Roster` from `security.roster`, `SecurityError` from `security.errors`, and roster reads through `load_document(...).auth`. No behaviour changes — the editor's operations already go through `auth/operations.py`, which Task 3 rewired.

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/barn/test_security_panel.py -q`
Expected: `4 passed`

- [ ] **Step 6: See it in the real app**

```bash
uv run haywire
```

Open the settings properties panel, confirm: a **Security** panel exists (admin only), it shows four axis lines and the Studio Port field, and there is no toggle anywhere for exposure, TLS or Farmhand. Quit.

- [ ] **Step 7: Lint, format, type-check, commit**

```bash
uv run ruff check barn/haybale-studio/ tests/barn/
uv run ruff format barn/haybale-studio/ tests/barn/
uv run mypy barn/haybale-studio/haybale_studio/
git add -A
git commit -m "feat(ui): Security panel replaces the writable Network settings panel

Renders the in-force Posture read-only at access=admin; only 'port' remains
an editable setting.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 9: ADR 0028, the security guide, and the vocabulary

**Files:**
- Create: `docs/adr/0028-security-document.md`
- Create: `docs/guides/security.md`
- Delete: `docs/guides/network_config.md`
- Modify: `mkdocs.yml`, `docs/reference/glossary.md`, `docs/adr/0026-studio-network-exposure.md`, `docs/adr/0027-studio-authentication.md`, `.claude/skills/haywire-live-studio/SKILL.md`, `CLAUDE.md`

- [ ] **Step 1: Write ADR 0028**

`docs/adr/0028-security-document.md`, following the house shape (front matter with `name`/`description`/`status`/`level`, then prose that argues rather than lists). It must cover, each as its own section:

1. **The defect.** ADR 0027 gave two reasons the roster is not a settings bag — the settings UI writes the workspace tier, which travels into git; and the global tier is hand-edit-only, so a bag renders fields that silently do nothing. Both apply verbatim to every network knob, and neither was applied. `expose_to_network` was one checkbox that committed a machine's exposure decision into a project file.
2. **One document.** `~/.haywire/security.json`, 0600, three blocks. The invariants and why they live inside `save_document` rather than in each caller.
3. **Writes refuse, loads fail closed.** Why `sanitize` never refuses to start, quoting ADR 0027's lockout reasoning.
4. **Exposure is a verb.** Why a checkbox cannot express a precondition; the `--ranges` requirement; the "keep the allowlist on seal" choice.
5. **The MCP rule.** `/mcp` requires a roster token iff auth is enabled; `exposed ⇒ auth enabled` closes the matrix; therefore `require_auth` and `BearerTokenMiddleware` and the workspace token are all deleted rather than merely redundant. Note the `studio.json` `auth_required` hint and that it must never carry a token.
6. **`restrict_to_loopback` survives as a CLI-only control.** It is a header check, not a network control; it defeats DNS rebinding specifically; turning it off demands authentication because that is a transition constraint, not a state invariant.
7. **What ADR 0026 keeps.** Pure-ASGI over `BaseHTTPMiddleware` (with the Socket.IO argument intact), the XFF rightmost-untrusted resolution, loopback's exemption from the allowlist, jedi path confinement. Only the *placement* of the controls changes.
8. **Consequences.** Hard break, no migration. `NetworkSettings` keeps `port`. The settings panel is read-only and admin-gated. The farmhand4claude proxy must read `auth_required` from `studio.json` and stop reading `farmhand_token` — a cross-repo change this ADR does not make.
9. **Alternatives considered.** (a) Hiding the fields rather than deleting them — rejected, the workspace-tier JSON path stays open. (b) A read-only setting kind in the settings system — rejected, a new framework concept to solve a placement problem. (c) `haywire mcp` instead of `haywire farmhand` — rejected on glossary consistency. (d) Refusing to start on a contradictory document — rejected, lockout.

- [ ] **Step 2: Write `docs/guides/security.md`**

Fold `docs/guides/network_config.md` in whole. Follow `docs/reference/doc-authoring.md` for front matter and live-source links. Required sections, in order:

1. **Default: local only** — adapted from network_config §1.
2. **The four axes** — replaces §2's "seven settings" table with: network location (`haywire network`), authentication (`haywire auth`, `haywire user`), TLS (`haywire ssl`), Farmhand (`haywire farmhand`). One command column, one "read at startup" note.
3. **What you are exposing** — network_config §4 verbatim; this is the section that earns the whole guide. A graph executes arbitrary Python in-process.
4. **Opening the studio up** — the `haywire network expose` walkthrough, the three preconditions, and what each refusal means.
5. **CIDR syntax** — network_config §3 verbatim.
6. **The MCP endpoint** — `haywire farmhand`, and **an explicit `restrict_to_loopback` subsection**: what DNS rebinding is, why a header check defeats it, why it does not stop `curl`, when you would legitimately turn it off (an MCP client on another machine), and that doing so requires authentication. This is the user's stated requirement for the guide — it must be findable by someone who does not already know the setting exists.
7. **Running on a server** — network_config §5 in full: VPN/Tailscale, reverse proxy, `ssh -L`.
8. **Serving HTTPS** — network_config §9 in full.
9. **Managing principals** — network_config §8 §"Managing principals", plus the roster editor.
10. **The security document** — where it lives, its 0600 permissions, what hand-editing does (sanitized at boot, reported by `haywire security status`), and that it is machine-global and must not be committed.
11. **No sandbox, no multi-tenancy** — network_config §7 verbatim.

Delete `docs/guides/network_config.md`. Section 6 of network_config ("Machine-wide defaults: the global settings tier") is **dropped, not folded** — the settings tiers no longer govern any security control, and carrying it forward would teach the exact mental model this change removes.

- [ ] **Step 3: Update nav and cross-references**

`mkdocs.yml`, in the Guides block:

```yaml
      - Security: guides/security.md
```

replacing the `Network configuration` line.

`docs/adr/0026-studio-network-exposure.md`: change the front-matter `status:` to `superseded-in-part` and add, immediately after the title:

```markdown
> **Superseded in part by [ADR 0028](0028-security-document.md).** The layered
> model below — pure-ASGI filtering, `X-Forwarded-For` resolution, loopback's
> exemption from the allowlist, jedi path confinement — is unchanged and still
> current. What moved is *where the controls live*: `NetworkSettings` no longer
> carries `expose_to_network`, `allowed_remote_ranges`, `public_hostname`,
> `trusted_proxies`, `ssl_certfile` or `ssl_keyfile`. Read every mention of
> those as fields of `~/.haywire/security.json`.
```

`docs/adr/0027-studio-authentication.md`: add the same style of note after the title, naming the three amendments — `auth.json` → `security.json`, the workspace `farmhand_token` and `BearerTokenMiddleware` deleted, `require_auth` deleted.

`docs/reference/glossary.md`: update the **Farmhand proxy** row (reads `auth_required` from `studio.json`, no token file), the **Studio identity sidecar** row (drop "Sits beside `farmhand_token`", add `auth_required`), and add a **Security document** row.

`.claude/skills/haywire-live-studio/SKILL.md:94`: replace the `.haywire/farmhand_token` instructions with: `/mcp` needs no header when `studio.json` has `auth_required: false`; when true, use a roster agent token from `haywire user add <name> --agent --tier edit`.

`CLAUDE.md`: no trap-list entry is needed — this plan removes traps rather than adding one. Verify no existing entry references the deleted modules:

```bash
grep -n "expose_to_network\|farmhand_token\|tls_settings\|FarmhandSettings" CLAUDE.md .insights/*.md
```

Update anything that hits.

- [ ] **Step 4: Build the docs**

```bash
uv run mkdocs build --strict
```

Expected: exit 0. `--strict` fails on a broken internal link, which is the whole point of running it here.

- [ ] **Step 5: Full test suite**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/security-doc.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/security-doc.log
grep -E "passed|failed" /tmp/security-doc.log | tail -1
```

Expected: `exit=0`. Investigate every FAILED before continuing — a failure here is almost certainly a stale import this plan's earlier greps missed.

- [ ] **Step 6: Full repo lint, format and type-check**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "docs: ADR 0028 and docs/guides/security.md

Folds network_config.md into a four-axis security guide with an explicit
restrict_to_loopback section. ADR 0026 and 0027 gain supersession notes.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 8: Browser tests**

```bash
uv run pytest -m browser -q > /tmp/security-browser.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/security-browser.log
```

Expected: `exit=0`. The Security panel is admin-gated and the harness runs auth-off (which resolves to ADMIN), so it should render — if a harness route fails on `ctx.app.security_document` being `None`, the panel's guard clause is the fix, not the harness.

---

## Follow-up, out of scope for this plan

**farmhand4claude proxy (separate repo).** It reads `<ws>/.haywire/farmhand_token` lazily; that file no longer exists. It must instead read `auth_required` from `<ws>/.haywire/studio.json` and send no `Authorization` header when it is `false`. When `true`, the operator supplies a roster agent token out of band (`haywire user add <name> --agent --tier edit` prints it). Until that change ships, the proxy will attach no header — which is correct against an unauthenticated studio and will 401 against an authenticated one. Raise this with the user when this plan lands; it is a coordinated release, not a silent break.
