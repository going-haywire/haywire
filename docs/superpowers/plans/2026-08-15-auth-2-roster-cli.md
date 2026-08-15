---
status: planned
slice: 2 of 6
feature: studio-authentication
adr: docs/adr/0027-studio-authentication.md
previous: 2026-08-15-auth-1-core-access.md
next: 2026-08-15-auth-3-gate-login.md
---

# Slice 2 — Roster + CLI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the roster — `~/.haywire/auth.json`, holding the enabled flag and every principal — plus scrypt password hashing, the password policy, and the `haywire user` / `haywire auth` CLI subcommands that manage it.

**Architecture:** One JSON document owned by one module. Everything here is pure Python: no NiceGUI, no ASGI, no browser, so the whole slice is testable headless in milliseconds. The roster is a single document deliberately — split across two files, "auth is enabled" and "an admin exists" could disagree, and every guard against that state is a check someone has to remember to keep working (ADR 0027).

**Tech Stack:** Python 3.12 stdlib only — `hashlib.scrypt`, `secrets`, `json`, `getpass`, `argparse`. No new dependencies.

## Chain position

- **Previous slice:** `2026-08-15-auth-1-core-access.md` — provides `AccessTier`, `set_access_resolver`, `resolve_tier`.
- **Next slice:** `2026-08-15-auth-3-gate-login.md` — consumes `load_roster`, `Roster.find`, `verify_password`, `Roster.enabled`, and installs the resolver built here.
- **This slice is still behaviour-neutral for the running studio.** Nothing reads the roster at runtime yet; the CLI writes a file the studio does not yet consult.

## Chain protocol

1. **Task 0** re-affirms current state and reconciles against Slice 1's Drift Log before any implementation.
2. **The final task** fills in this document's Drift Log and flips `status:` to `implemented`.
3. A slice that finds the plan wrong **edits the plan** and records why. Silent deviation is the failure this protocol prevents.

## Global Constraints

- Line length 109; `uv run ruff check .` **and** `uv run ruff format --check .` must both pass.
- `uv run mypy` must pass for every path in the CLAUDE.md mypy command.
- **No new runtime dependencies.**
- Roster file is `0600`. Every write is atomic (temp file + `os.replace`) — a crash mid-write must never leave a truncated roster that locks everyone out.
- Password policy (ADR 0027 / Q20-D): **≥12 chars with at least one lower, one upper, one digit and one special — OR ≥20 chars of anything.**
- Agent tokens are stored in **plaintext**; passwords are **hashed**. This asymmetry is deliberate — see ADR 0027.

---

### Task 0: Affirm current state and reconcile Slice 1 drift

**Files:**
- Read: `docs/superpowers/plans/2026-08-15-auth-1-core-access.md` (Delivered + Drift Log)
- Read: `packages/haywire-studio/src/haywire_studio/cli/__init__.py`

- [ ] **Step 1: Confirm Slice 1 is implemented**

```bash
grep -n "^status:" docs/superpowers/plans/2026-08-15-auth-1-core-access.md
```

Expected: `status: implemented`. If it says `planned`, stop — Slice 1 must land first.

- [ ] **Step 2: Read Slice 1's Drift Log and Delivered sections**

If Slice 1 drifted — different module path, different function names, `AccessTier` shaped differently — **edit this plan now** to match what actually exists, before writing any code. Record in this plan's Drift Log that Task 0 made corrections and which ones.

- [ ] **Step 3: Verify the Slice 1 surface is importable as this plan assumes**

```bash
uv run python -c "
from haywire.core.access import AccessTier, resolve_tier, set_access_resolver
print(AccessTier.EDIT, AccessTier.ADMIN.satisfies(AccessTier.EDIT))
"
```

Expected: `edit True`

- [ ] **Step 4: Confirm the CLI registry shape**

Read `packages/haywire-studio/src/haywire_studio/cli/__init__.py`. It must expose `SUBCOMMANDS` as a tuple of modules each having `register(subparsers)`. Confirm the current tuple is `(init, share, rename, deps, docs, verify)`. If it differs, adjust Task 5 accordingly.

- [ ] **Step 5: Confirm baseline clean**

```bash
uv run ruff check packages/haywire-studio/src/
uv run mypy packages/haywire-studio/src/
```

Expected: no errors.

---

### Task 1: Password hashing and policy

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/auth/__init__.py`
- Create: `packages/haywire-studio/src/haywire_studio/auth/passwords.py`
- Test: `tests/auth/__init__.py`, `tests/auth/test_passwords.py`

**Interfaces:**
- Consumes: nothing from Slice 1.
- Produces: `hash_password(password: str) -> str`, `verify_password(password: str, encoded: str) -> bool`, `password_problem(password: str, *, username: str = "") -> str | None`, `POLICY_HELP: str`.

- [ ] **Step 1: Write the failing test**

Create `tests/auth/__init__.py` empty, then `tests/auth/test_passwords.py`:

```python
"""scrypt password hashing + the ADR 0027 password policy."""

import pytest

from haywire_studio.auth.passwords import (
    hash_password,
    password_problem,
    verify_password,
)

GOOD = "Correct-Horse9"  # 14 chars, all four classes


def test_hash_is_not_the_password():
    assert GOOD not in hash_password(GOOD)


def test_hash_has_the_documented_shape():
    encoded = hash_password(GOOD)
    parts = encoded.split("$")
    assert parts[0] == "scrypt"
    assert parts[1:4] == ["16384", "8", "1"]
    assert len(parts) == 6


def test_salt_differs_between_hashes_of_the_same_password():
    assert hash_password(GOOD) != hash_password(GOOD)


def test_verify_accepts_the_right_password():
    assert verify_password(GOOD, hash_password(GOOD)) is True


def test_verify_rejects_the_wrong_password():
    assert verify_password("Wrong-Horse9!!", hash_password(GOOD)) is False


@pytest.mark.parametrize(
    "encoded",
    ["", "garbage", "scrypt$16384$8", "scrypt$x$8$1$aaaa$bbbb", "bcrypt$16384$8$1$aaaa$bbbb"],
)
def test_verify_returns_false_on_malformed_hash_never_raises(encoded):
    assert verify_password(GOOD, encoded) is False


# --- policy -----------------------------------------------------------


@pytest.mark.parametrize(
    "password",
    [
        "Correct-Horse9",  # 14, all four classes
        "Aa1!aaaaaaaa",  # exactly 12, all four classes
        "correct horse battery staple",  # 28, no classes but long
        "aaaaaaaaaaaaaaaaaaaa",  # exactly 20
    ],
)
def test_policy_accepts(password):
    assert password_problem(password) is None


@pytest.mark.parametrize(
    "password",
    [
        "Aa1!aaaaaaa",  # 11 — one short of the composition path
        "aaaaaaaaaaaaaaaaaaa",  # 19 — one short of the length path
        "Password1234",  # 12 but no special
        "password123!",  # 12 but no uppercase
        "PASSWORD123!",  # 12 but no lowercase
        "Password!!!!",  # 12 but no digit
        "",
    ],
)
def test_policy_rejects(password):
    assert password_problem(password) is not None


def test_policy_rejects_password_containing_the_username():
    assert password_problem("Alice-Password9", username="alice") is not None


def test_policy_username_check_is_case_insensitive():
    assert password_problem("XxALICExx-9aB", username="Alice") is not None


def test_rejection_message_states_both_paths():
    message = password_problem("short")
    assert message is not None
    assert "12" in message and "20" in message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/auth/test_passwords.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.auth'`

- [ ] **Step 3: Write the implementation**

Create `packages/haywire-studio/src/haywire_studio/auth/__init__.py`:

```python
"""Studio authentication — roster, password hashing, the gate, and login routes.

Core owns the access *vocabulary* (``haywire.core.access``); this package owns
the *mechanism*. See ADR 0027.
"""
```

Create `packages/haywire-studio/src/haywire_studio/auth/passwords.py`:

```python
"""Password hashing and the account password policy (ADR 0027).

scrypt from the standard library rather than bcrypt or argon2: memory-hard,
zero new dependencies in a package distributed as a wheel through the
marketplace, and ~36 ms per hash on a 2026 laptop, which also serves as the
rate limit on ``POST /login``.

Be clear about what the hash defends. Anyone who can read the roster already
has shell access to the machine and therefore to the graphs, the signing
secret, and arbitrary Python — so the hash is not holding a security boundary
here. Its job is narrower and still worth doing: never store the plaintext, so
a password the operator reuses elsewhere does not leak from a backup, a
screen-share, or a synced home directory.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

# scrypt cost parameters. n=2**14 measures ~36 ms/hash locally. They are baked
# into every encoded hash so raising them later does not invalidate old ones.
_N = 16384
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16

MIN_LENGTH_WITH_CLASSES = 12
MIN_LENGTH_WITHOUT_CLASSES = 20

POLICY_HELP = (
    f"at least {MIN_LENGTH_WITH_CLASSES} characters including an uppercase letter, "
    f"a lowercase letter, a digit and a symbol — or at least "
    f"{MIN_LENGTH_WITHOUT_CLASSES} characters of anything"
)


def hash_password(password: str) -> str:
    """Hash ``password`` into ``scrypt$n$r$p$salt_b64$hash_b64``."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return "$".join(
        [
            "scrypt",
            str(_N),
            str(_R),
            str(_P),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check of ``password`` against an encoded hash.

    Returns ``False`` — never raises — for a malformed or unknown-scheme hash,
    so a corrupted roster entry denies access rather than crashing the login
    route.
    """
    try:
        scheme, n_s, r_s, p_s, salt_b64, hash_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_s),
            r=int(r_s),
            p=int(p_s),
            dklen=len(expected),
        )
    except Exception:
        return False
    return hmac.compare_digest(actual, expected)


def dummy_verify() -> None:
    """Burn one scrypt hash for an unknown username.

    ``POST /login`` calls this when no principal matches, so a missing account
    and a wrong password take the same time and response timing cannot be used
    to enumerate the roster.
    """
    hashlib.scrypt(b"dummy", salt=b"0123456789abcdef", n=_N, r=_R, p=_P, dklen=_DKLEN)


def password_problem(password: str, *, username: str = "") -> str | None:
    """``None`` if the password is acceptable, otherwise a human-readable reason.

    Two accepted paths (ADR 0027): composition at 12+, or raw length at 20+.
    The length path exists because a composition rule on its own rejects
    stronger passwords than it accepts — ``correct horse battery staple`` has
    no digit or symbol and is far stronger than ``Password123!``, which passes
    every composition clause and sits in every cracking wordlist.
    """
    if username and username.casefold() in password.casefold():
        return "Password must not contain the username."

    if len(password) >= MIN_LENGTH_WITHOUT_CLASSES:
        return None

    if len(password) >= MIN_LENGTH_WITH_CLASSES:
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = any(not c.isalnum() for c in password)
        if has_lower and has_upper and has_digit and has_symbol:
            return None

    return f"Password must be {POLICY_HELP}."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/auth/test_passwords.py -v`
Expected: PASS, 25 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/auth/ tests/auth/
git commit -m "feat(auth): scrypt password hashing and the two-path password policy"
```

---

### Task 2: The roster document

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/auth/roster.py`
- Test: `tests/auth/test_roster.py`

**Interfaces:**
- Consumes: `AccessTier` (Slice 1), `hash_password` (Task 1).
- Produces:
  - `ROSTER_VERSION: int = 1`
  - `roster_path() -> Path` — `~/.haywire/auth.json`
  - `@dataclass Principal(name: str, kind: str, tier: AccessTier, password_hash: str = "", token: str = "", workspace: str = "")` with `is_user`/`is_agent` properties
  - `@dataclass Roster(enabled: bool = False, session_days: int = 30, principals: list[Principal] = ...)` with `find(name) -> Principal | None`, `find_by_token(token) -> Principal | None`, `admins() -> list[Principal]`
  - `load_roster(path: Path | None = None) -> Roster`
  - `save_roster(roster: Roster, path: Path | None = None) -> None`
  - `RosterError(Exception)`

- [ ] **Step 1: Write the failing test**

Create `tests/auth/test_roster.py`:

```python
"""The roster document — ~/.haywire/auth.json, one file, atomic writes."""

import json
import stat

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.passwords import hash_password
from haywire_studio.auth.roster import (
    Principal,
    Roster,
    RosterError,
    load_roster,
    save_roster,
)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "auth.json"


def test_load_missing_file_returns_disabled_empty_roster(path):
    roster = load_roster(path)
    assert roster.enabled is False
    assert roster.principals == []
    assert roster.session_days == 30


def test_round_trip(path):
    roster = Roster(
        enabled=True,
        session_days=7,
        principals=[
            Principal(name="alice", kind="user", tier=AccessTier.ADMIN, password_hash=hash_password("x" * 20)),
            Principal(name="agent1", kind="agent", tier=AccessTier.EDIT, token="tok", workspace="/w"),
        ],
    )
    save_roster(roster, path)
    loaded = load_roster(path)

    assert loaded.enabled is True
    assert loaded.session_days == 7
    assert [p.name for p in loaded.principals] == ["alice", "agent1"]
    assert loaded.find("alice").tier is AccessTier.ADMIN
    assert loaded.find("agent1").workspace == "/w"


def test_saved_file_is_0600(path):
    save_roster(Roster(), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_saved_file_carries_a_version(path):
    save_roster(Roster(), path)
    assert json.loads(path.read_text())["version"] == 1


def test_unknown_version_refuses_to_load(path):
    path.write_text(json.dumps({"version": 99, "enabled": True, "principals": []}))
    with pytest.raises(RosterError, match="version"):
        load_roster(path)


def test_corrupt_json_refuses_to_load_rather_than_defaulting_open(path):
    path.write_text("{not json")
    with pytest.raises(RosterError):
        load_roster(path)


def test_find_is_exact_not_case_folded(path):
    roster = Roster(principals=[Principal(name="alice", kind="user", tier=AccessTier.VIEW)])
    assert roster.find("alice") is not None
    assert roster.find("Alice") is None
    assert roster.find("bob") is None


def test_find_by_token_ignores_empty_tokens(path):
    roster = Roster(
        principals=[
            Principal(name="alice", kind="user", tier=AccessTier.ADMIN, password_hash="h"),
            Principal(name="agent1", kind="agent", tier=AccessTier.EDIT, token="secret"),
        ]
    )
    assert roster.find_by_token("secret").name == "agent1"
    assert roster.find_by_token("") is None


def test_admins_lists_only_admin_tier():
    roster = Roster(
        principals=[
            Principal(name="a", kind="user", tier=AccessTier.ADMIN),
            Principal(name="b", kind="user", tier=AccessTier.EDIT),
            Principal(name="c", kind="agent", tier=AccessTier.ADMIN),
        ]
    )
    assert [p.name for p in roster.admins()] == ["a", "c"]


def test_is_user_and_is_agent():
    user = Principal(name="a", kind="user", tier=AccessTier.VIEW)
    agent = Principal(name="b", kind="agent", tier=AccessTier.VIEW)
    assert (user.is_user, user.is_agent) == (True, False)
    assert (agent.is_user, agent.is_agent) == (False, True)


def test_save_leaves_no_temp_file_behind(path):
    save_roster(Roster(), path)
    assert [p.name for p in path.parent.iterdir()] == ["auth.json"]


def test_save_creates_the_parent_directory(tmp_path):
    nested = tmp_path / "deep" / "auth.json"
    save_roster(Roster(), nested)
    assert nested.exists()


def test_unknown_tier_string_refuses_to_load(path):
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "enabled": True,
                "principals": [{"name": "a", "kind": "user", "tier": "superuser"}],
            }
        )
    )
    with pytest.raises(RosterError):
        load_roster(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/auth/test_roster.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.auth.roster'`

- [ ] **Step 3: Write the implementation**

Create `packages/haywire-studio/src/haywire_studio/auth/roster.py`:

```python
"""The roster — ``~/.haywire/auth.json`` (ADR 0027).

**One document, deliberately.** The enabled flag and the principals live in the
same file so "authentication is on" and "an admin exists" cannot disagree.
Split across two files they are independently editable, so ``enabled: true``
with an empty roster becomes a reachable state that every guard against it is a
check someone must remember to write and keep working. As fields of one
document written through one path, the state does not exist.

**Not a settings bag.** The settings UI writes the *workspace* tier
(``<workspace>/.haywire/settings.json``), a per-project file that travels into
git and onto other machines. Session lifetime and the roster are
machine-and-operator policy, not project data. The global settings tier avoids
that but is hand-edit-only, so an ``AuthSettings`` bag would render fields in
the settings UI that silently do nothing when edited.

Every write is atomic (temp file + ``os.replace``) and the result is ``0600``.
A truncated roster would lock every principal out of the only UI that could
repair it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from haywire.core.access import AccessTier

ROSTER_VERSION = 1
ROSTER_FILENAME = "auth.json"

KIND_USER = "user"
KIND_AGENT = "agent"


class RosterError(Exception):
    """The roster exists but cannot be trusted — unreadable, corrupt, or a future version.

    Always raised rather than silently returning an empty roster: an empty
    roster means "authentication is off", and degrading a corrupt file into
    "off" would turn a disk problem into an open door.
    """


def roster_path() -> Path:
    """``~/.haywire/auth.json`` — global, not per-workspace."""
    return Path.home() / ".haywire" / ROSTER_FILENAME


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
            raise RosterError(f"Principal {data.get('name')!r} has an unusable tier: {exc}") from exc
        name = data.get("name")
        if not isinstance(name, str) or not name:
            raise RosterError("Every principal needs a non-empty name.")
        kind = data.get("kind", KIND_USER)
        if kind not in (KIND_USER, KIND_AGENT):
            raise RosterError(f"Principal {name!r} has unknown kind {kind!r}.")
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
    """The whole authentication document."""

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
            "version": ROSTER_VERSION,
            "enabled": self.enabled,
            "session_days": self.session_days,
            "principals": [p.to_dict() for p in self.principals],
        }


def load_roster(path: Path | None = None) -> Roster:
    """Read the roster. A missing file is a disabled, empty roster — not an error."""
    target = path or roster_path()
    if not target.exists():
        return Roster()

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RosterError(f"Cannot read {target}: {exc}") from exc

    version = raw.get("version")
    if version != ROSTER_VERSION:
        raise RosterError(
            f"{target} has version {version!r}, but this studio understands version "
            f"{ROSTER_VERSION}. Upgrade haywire, or move the file aside to start over."
        )

    return Roster(
        enabled=bool(raw.get("enabled", False)),
        session_days=int(raw.get("session_days", 30)),
        principals=[Principal.from_dict(entry) for entry in raw.get("principals", [])],
    )


def save_roster(roster: Roster, path: Path | None = None) -> None:
    """Write the roster atomically at ``0600``.

    Temp file in the same directory (so ``os.replace`` stays on one filesystem
    and is therefore atomic), chmod before the rename so the secrets are never
    briefly world-readable, then replace.
    """
    target = path or roster_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(json.dumps(roster.to_dict(), indent=2) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    os.replace(tmp, target)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/auth/test_roster.py -v`
Expected: PASS, 13 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/auth/roster.py tests/auth/test_roster.py
git commit -m "feat(auth): roster document with atomic 0600 writes"
```

---

### Task 3: Roster mutation operations

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/auth/operations.py`
- Test: `tests/auth/test_operations.py`

**Interfaces:**
- Consumes: Task 1 + Task 2.
- Produces (each raises `RosterError` on a rule violation, and each loads → mutates → saves through the given path):
  - `add_user(name, password, tier, *, path=None) -> Principal`
  - `add_agent(name, tier, *, workspace="", path=None) -> Principal` (mints `secrets.token_urlsafe(32)`)
  - `remove_principal(name, *, path=None) -> None`
  - `set_password(name, password, *, path=None) -> None`
  - `set_tier(name, tier, *, path=None) -> None`
  - `enable_auth(username, password, *, path=None) -> None`
  - `disable_auth(username, password, *, path=None) -> None`
  - `authenticate(username, password, *, path=None) -> Principal | None`

**Why these live apart from `roster.py`:** `roster.py` is the document — read, write, look up. This module is the *rules* about changing it (last-admin protection, name collisions, the enable precondition). Slice 5's roster UI calls exactly these functions, so the rules cannot diverge between the CLI and the UI.

- [ ] **Step 1: Write the failing test**

Create `tests/auth/test_operations.py`:

```python
"""Roster mutation rules — shared by the CLI (slice 2) and the roster UI (slice 5)."""

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.operations import (
    add_agent,
    add_user,
    authenticate,
    disable_auth,
    enable_auth,
    remove_principal,
    set_password,
    set_tier,
)
from haywire_studio.auth.roster import RosterError, load_roster

STRONG = "Correct-Horse9"
OTHER = "Battery-Staple7"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "auth.json"


def test_add_user_hashes_the_password(path):
    principal = add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert principal.is_user
    assert STRONG not in principal.password_hash
    assert load_roster(path).find("alice").tier is AccessTier.ADMIN


def test_add_user_rejects_a_weak_password(path):
    with pytest.raises(RosterError, match="12"):
        add_user("alice", "short", AccessTier.ADMIN, path=path)


def test_add_user_rejects_a_password_containing_the_username(path):
    with pytest.raises(RosterError):
        add_user("alice", "Alice-Password9", AccessTier.ADMIN, path=path)


def test_add_user_rejects_a_duplicate_name(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    with pytest.raises(RosterError, match="already"):
        add_user("alice", OTHER, AccessTier.VIEW, path=path)


def test_add_user_rejects_an_empty_name(path):
    with pytest.raises(RosterError):
        add_user("", STRONG, AccessTier.ADMIN, path=path)


def test_add_agent_mints_a_token(path):
    agent = add_agent("builder", AccessTier.EDIT, path=path)
    assert agent.is_agent
    assert len(agent.token) >= 40
    assert agent.password_hash == ""


def test_add_agent_records_the_workspace_scope(path):
    add_agent("builder", AccessTier.EDIT, workspace="/proj", path=path)
    assert load_roster(path).find("builder").workspace == "/proj"


def test_agent_tokens_are_unique(path):
    a = add_agent("one", AccessTier.EDIT, path=path)
    b = add_agent("two", AccessTier.EDIT, path=path)
    assert a.token != b.token


def test_remove_principal(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    add_user("bob", OTHER, AccessTier.VIEW, path=path)
    remove_principal("bob", path=path)
    assert load_roster(path).find("bob") is None


def test_remove_unknown_principal_raises(path):
    with pytest.raises(RosterError, match="No principal"):
        remove_principal("nobody", path=path)


def test_cannot_remove_the_last_admin_while_auth_is_enabled(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    with pytest.raises(RosterError, match="last admin"):
        remove_principal("alice", path=path)


def test_can_remove_an_admin_when_another_remains(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    add_user("carol", OTHER, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    remove_principal("carol", path=path)
    assert load_roster(path).find("carol") is None


def test_cannot_demote_the_last_admin_while_auth_is_enabled(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    with pytest.raises(RosterError, match="last admin"):
        set_tier("alice", AccessTier.VIEW, path=path)


def test_set_password_changes_the_hash_and_still_verifies(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    set_password("alice", OTHER, path=path)
    assert authenticate("alice", OTHER, path=path) is not None
    assert authenticate("alice", STRONG, path=path) is None


def test_set_password_enforces_the_policy(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    with pytest.raises(RosterError):
        set_password("alice", "weak", path=path)


def test_set_tier(path):
    add_user("bob", STRONG, AccessTier.VIEW, path=path)
    set_tier("bob", AccessTier.EDIT, path=path)
    assert load_roster(path).find("bob").tier is AccessTier.EDIT


# --- authenticate -----------------------------------------------------


def test_authenticate_accepts_correct_credentials(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert authenticate("alice", STRONG, path=path).name == "alice"


def test_authenticate_rejects_wrong_password(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert authenticate("alice", OTHER, path=path) is None


def test_authenticate_rejects_unknown_user(path):
    assert authenticate("nobody", STRONG, path=path) is None


def test_authenticate_never_matches_an_agent(path):
    add_agent("builder", AccessTier.EDIT, path=path)
    assert authenticate("builder", STRONG, path=path) is None


# --- enable / disable -------------------------------------------------


def test_enable_requires_a_working_admin_login(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    assert load_roster(path).enabled is True


def test_enable_rejects_a_wrong_password(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    with pytest.raises(RosterError, match="credentials"):
        enable_auth("alice", OTHER, path=path)
    assert load_roster(path).enabled is False


def test_enable_rejects_a_non_admin(path):
    add_user("bob", STRONG, AccessTier.VIEW, path=path)
    with pytest.raises(RosterError, match="admin"):
        enable_auth("bob", STRONG, path=path)
    assert load_roster(path).enabled is False


def test_enable_with_no_admin_at_all_raises(path):
    with pytest.raises(RosterError):
        enable_auth("alice", STRONG, path=path)


def test_disable_requires_a_working_admin_login(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    disable_auth("alice", STRONG, path=path)
    assert load_roster(path).enabled is False


def test_disable_rejects_a_wrong_password(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    with pytest.raises(RosterError):
        disable_auth("alice", OTHER, path=path)
    assert load_roster(path).enabled is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/auth/test_operations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.auth.operations'`

- [ ] **Step 3: Write the implementation**

Create `packages/haywire-studio/src/haywire_studio/auth/operations.py`:

```python
"""The rules for changing the roster (ADR 0027).

``roster.py`` is the document — read it, write it, look things up. This module
is the *rules*: last-admin protection, name collisions, the password policy
gate, and the credential check that guards enable/disable.

They live apart so the CLI (slice 2) and the roster UI (slice 5) call the same
functions and cannot drift into two different sets of rules.
"""

from __future__ import annotations

import secrets

from pathlib import Path

from haywire.core.access import AccessTier

from haywire_studio.auth.passwords import dummy_verify, hash_password, password_problem, verify_password
from haywire_studio.auth.roster import (
    KIND_AGENT,
    KIND_USER,
    Principal,
    Roster,
    RosterError,
    load_roster,
    save_roster,
)

TOKEN_BYTES = 32


def _require_password_ok(password: str, username: str) -> None:
    problem = password_problem(password, username=username)
    if problem is not None:
        raise RosterError(problem)


def _require_absent(roster: Roster, name: str) -> None:
    if not name:
        raise RosterError("A principal needs a name.")
    if roster.find(name) is not None:
        raise RosterError(f"A principal named {name!r} already exists.")


def _require_present(roster: Roster, name: str) -> Principal:
    principal = roster.find(name)
    if principal is None:
        raise RosterError(f"No principal named {name!r}.")
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
        raise RosterError(
            f"{principal.name!r} is the last admin and authentication is enabled — "
            "removing or demoting them would lock everyone out. Add another admin first, "
            "or run 'haywire auth disable'."
        )


def add_user(name: str, password: str, tier: AccessTier, *, path: Path | None = None) -> Principal:
    """Create a password principal."""
    roster = load_roster(path)
    _require_absent(roster, name)
    _require_password_ok(password, name)
    principal = Principal(name=name, kind=KIND_USER, tier=tier, password_hash=hash_password(password))
    roster.principals.append(principal)
    save_roster(roster, path)
    return principal


def add_agent(
    name: str, tier: AccessTier, *, workspace: str = "", path: Path | None = None
) -> Principal:
    """Create a token principal and mint its bearer token."""
    roster = load_roster(path)
    _require_absent(roster, name)
    principal = Principal(
        name=name,
        kind=KIND_AGENT,
        tier=tier,
        token=secrets.token_urlsafe(TOKEN_BYTES),
        workspace=workspace,
    )
    roster.principals.append(principal)
    save_roster(roster, path)
    return principal


def remove_principal(name: str, *, path: Path | None = None) -> None:
    roster = load_roster(path)
    principal = _require_present(roster, name)
    _require_not_last_admin(roster, principal)
    roster.principals = [p for p in roster.principals if p.name != name]
    save_roster(roster, path)


def set_password(name: str, password: str, *, path: Path | None = None) -> None:
    roster = load_roster(path)
    principal = _require_present(roster, name)
    if not principal.is_user:
        raise RosterError(f"{name!r} is an agent — agents authenticate with a token, not a password.")
    _require_password_ok(password, name)
    principal.password_hash = hash_password(password)
    save_roster(roster, path)


def set_tier(name: str, tier: AccessTier, *, path: Path | None = None) -> None:
    roster = load_roster(path)
    principal = _require_present(roster, name)
    if tier is not AccessTier.ADMIN:
        _require_not_last_admin(roster, principal)
    principal.tier = tier
    save_roster(roster, path)


def authenticate(username: str, password: str, *, path: Path | None = None) -> Principal | None:
    """Verify user credentials. Returns the principal, or ``None``.

    Always spends one scrypt hash even when the username is unknown, so a
    missing account and a wrong password take the same time — response timing
    cannot be used to enumerate the roster.
    """
    roster = load_roster(path)
    principal = roster.find(username)
    if principal is None or not principal.is_user or not principal.password_hash:
        dummy_verify()
        return None
    if not verify_password(password, principal.password_hash):
        return None
    return principal


def _require_admin_credentials(username: str, password: str, path: Path | None) -> None:
    roster = load_roster(path)
    if not roster.admins():
        raise RosterError(
            "No admin principal exists yet. Create one first:\n"
            "  haywire user add <name> --tier admin"
        )
    principal = authenticate(username, password, path=path)
    if principal is None:
        raise RosterError("Those credentials were not accepted.")
    if principal.tier is not AccessTier.ADMIN:
        raise RosterError(f"{username!r} is not an admin.")


def enable_auth(username: str, password: str, *, path: Path | None = None) -> None:
    """Turn authentication on, but only for someone who can prove they can get back in.

    Anyone who can run this can also edit the JSON by hand, so the credential
    check is not a barrier against an attacker. It is a **proof of
    recoverability**: it makes the realistic failure unreachable — turning on
    authentication with a roster whose passwords nobody remembers, on a machine
    whose UI is now the only way to fix it.
    """
    _require_admin_credentials(username, password, path)
    roster = load_roster(path)
    roster.enabled = True
    save_roster(roster, path)


def disable_auth(username: str, password: str, *, path: Path | None = None) -> None:
    """Turn authentication off. Requires the same proof as enabling it."""
    _require_admin_credentials(username, password, path)
    roster = load_roster(path)
    roster.enabled = False
    save_roster(roster, path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/auth/test_operations.py -v`
Expected: PASS, 26 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/auth/operations.py tests/auth/test_operations.py
git commit -m "feat(auth): roster mutation rules with last-admin protection and enable-requires-login"
```

---

### Task 4: The tier resolver

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/auth/live.py`
- Test: `tests/auth/test_live.py`

**Interfaces:**
- Consumes: Task 2, Slice 1's `set_access_resolver`.
- Produces: `RosterCache(path: Path | None = None)` with `.roster() -> Roster` (mtime-cached) and `.invalidate() -> None`; `install_resolver(cache: RosterCache) -> None`.

**Why cached:** the gate and every `can_*()` call reads live authority. Re-parsing JSON on each is wasteful; an `os.stat` is not. Revocation still lands immediately because the mtime changes the instant the roster is saved.

- [ ] **Step 1: Write the failing test**

Create `tests/auth/test_live.py`:

```python
"""Live tier resolution — mtime-cached roster reads behind the core resolver hook."""

import pytest

from haywire.core.access import AccessTier, access_resolver, resolve_tier, set_access_resolver
from haywire_studio.auth.live import RosterCache, install_resolver
from haywire_studio.auth.operations import add_agent, add_user, set_tier
from haywire_studio.auth.roster import Roster, save_roster

STRONG = "Correct-Horse9"


@pytest.fixture(autouse=True)
def _restore_resolver():
    previous = access_resolver()
    yield
    set_access_resolver(previous)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "auth.json"


def test_cache_returns_the_roster(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert RosterCache(path).roster().find("alice") is not None


def test_cache_reparses_after_mtime_changes(path):
    add_user("alice", STRONG, AccessTier.VIEW, path=path)
    cache = RosterCache(path)
    assert cache.roster().find("alice").tier is AccessTier.VIEW

    set_tier("alice", AccessTier.ADMIN, path=path)
    assert cache.roster().find("alice").tier is AccessTier.ADMIN


def test_cache_does_not_reparse_when_unchanged(path, monkeypatch):
    add_user("alice", STRONG, AccessTier.VIEW, path=path)
    cache = RosterCache(path)
    cache.roster()

    import haywire_studio.auth.live as live

    def _boom(_p):
        raise AssertionError("should not re-parse an unchanged roster")

    monkeypatch.setattr(live, "load_roster", _boom)
    assert cache.roster().find("alice") is not None


def test_missing_file_resolves_to_an_empty_roster(path):
    assert RosterCache(path).roster().principals == []


def test_resolver_answers_the_principals_tier(path):
    add_user("alice", STRONG, AccessTier.EDIT, path=path)
    install_resolver(RosterCache(path))
    assert resolve_tier("alice") is AccessTier.EDIT


def test_resolver_denies_an_unknown_principal_to_view(path):
    save_roster(Roster(enabled=True), path)
    install_resolver(RosterCache(path))
    assert resolve_tier("ghost") is AccessTier.VIEW


def test_resolver_denies_none_principal_to_view_when_auth_is_on(path):
    save_roster(Roster(enabled=True), path)
    install_resolver(RosterCache(path))
    assert resolve_tier(None) is AccessTier.VIEW


def test_resolver_answers_admin_when_auth_is_disabled(path):
    add_user("alice", STRONG, AccessTier.VIEW, path=path)  # roster.enabled stays False
    install_resolver(RosterCache(path))
    assert resolve_tier("alice") is AccessTier.ADMIN
    assert resolve_tier(None) is AccessTier.ADMIN


def test_demotion_is_visible_to_the_resolver_without_reinstalling(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    add_user("root", STRONG + "z", AccessTier.ADMIN, path=path)
    install_resolver(RosterCache(path))
    from haywire_studio.auth.operations import enable_auth

    enable_auth("alice", STRONG, path=path)
    assert resolve_tier("alice") is AccessTier.ADMIN

    set_tier("alice", AccessTier.VIEW, path=path)
    assert resolve_tier("alice") is AccessTier.VIEW


def test_agents_resolve_like_users(path):
    add_agent("builder", AccessTier.EDIT, path=path)
    save_roster_enabled = RosterCache(path).roster()
    save_roster_enabled.enabled = True
    save_roster(save_roster_enabled, path)
    install_resolver(RosterCache(path))
    assert resolve_tier("builder") is AccessTier.EDIT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/auth/test_live.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.auth.live'`

- [ ] **Step 3: Write the implementation**

Create `packages/haywire-studio/src/haywire_studio/auth/live.py`:

```python
"""Live roster reads behind core's resolver hook (ADR 0027).

The cookie carries identity; it never carries authority. So every
``ctx.can_edit()`` and every gate check asks the roster *now* rather than
trusting a tier stamped at login. That is what makes "remove a principal" an
actual revocation instead of a request — but it would be wasteful to re-parse
JSON on every call, so reads are cached against the file's mtime.

An ``os.stat`` per call is free; revocation still lands immediately because
saving the roster changes the mtime.
"""

from __future__ import annotations

import logging
from pathlib import Path

from haywire.core.access import AccessTier, set_access_resolver

from haywire_studio.auth.roster import Roster, RosterError, load_roster, roster_path

logger = logging.getLogger(__name__)


class RosterCache:
    """Reads the roster, re-parsing only when the file's mtime/size changes.

    A read error keeps the last good roster (and logs) rather than degrading to
    an empty one: an empty roster means "authentication disabled", so treating a
    transient disk error as empty would open the door.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or roster_path()
        self._stamp: tuple[float, int] | None = None
        self._roster: Roster = Roster()

    @property
    def path(self) -> Path:
        return self._path

    def roster(self) -> Roster:
        stamp = self._current_stamp()
        if stamp != self._stamp:
            try:
                self._roster = load_roster(self._path)
                self._stamp = stamp
            except RosterError:
                logger.warning("Roster at %s could not be read; keeping the last good copy", self._path)
        return self._roster

    def invalidate(self) -> None:
        """Force a re-parse on the next :meth:`roster` call.

        Used after this process itself writes the roster, so a write and a read
        inside the same mtime granularity cannot serve stale data.
        """
        self._stamp = None

    def _current_stamp(self) -> tuple[float, int] | None:
        try:
            info = self._path.stat()
        except OSError:
            return None
        return (info.st_mtime, info.st_size)


def install_resolver(cache: RosterCache) -> None:
    """Point core's ``resolve_tier`` at ``cache``.

    When the roster is disabled every principal resolves to ADMIN, which is what
    keeps an auth-off install behaving exactly as it did before. When enabled, an
    unknown principal resolves to VIEW rather than raising, so a stale cookie
    degrades to the least privilege instead of erroring inside a render.
    """

    def _resolve(name: str | None) -> AccessTier:
        roster = cache.roster()
        if not roster.enabled:
            return AccessTier.ADMIN
        if name is None:
            return AccessTier.VIEW
        principal = roster.find(name)
        return principal.tier if principal is not None else AccessTier.VIEW

    set_access_resolver(_resolve)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/auth/test_live.py -v`
Expected: PASS, 10 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/auth/live.py tests/auth/test_live.py
git commit -m "feat(auth): mtime-cached roster reads behind the core resolver hook"
```

---

### Task 5: `haywire user` and `haywire auth` subcommands

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/cli/user.py`
- Create: `packages/haywire-studio/src/haywire_studio/cli/authcmd.py`
- Modify: `packages/haywire-studio/src/haywire_studio/cli/__init__.py`
- Test: `tests/test_user_cli.py`, `tests/test_auth_cli.py`

**Interfaces:**
- Consumes: Task 3.
- Produces: two `register(subparsers)` modules following the house pattern; handlers return an `int` exit code and never call `sys.exit`.

**Module named `authcmd.py`, not `auth.py`:** `haywire_studio.auth` is already the package created in Task 1, and a sibling `cli/auth.py` would read as the same thing to anyone skimming imports.

- [ ] **Step 1: Write the failing test for `haywire user`**

Create `tests/test_user_cli.py`:

```python
"""haywire user — add/remove/list/passwd against an explicit roster path."""

import argparse

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.operations import add_user
from haywire_studio.auth.roster import load_roster
from haywire_studio.cli import user as user_cli

STRONG = "Correct-Horse9"


def _run(argv, monkeypatch, path, answers=None):
    """Parse argv through the real parser and run the handler."""
    if answers is not None:
        queue = list(answers)
        monkeypatch.setattr(user_cli, "_prompt_password", lambda *a, **k: queue.pop(0))
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    user_cli.register(subparsers)
    args = parser.parse_args(argv)
    args.roster = str(path)
    return args.handler(args)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "auth.json"


def test_add_user_creates_the_principal(monkeypatch, path, capsys):
    code = _run(["user", "add", "alice", "--tier", "admin"], monkeypatch, path, answers=[STRONG])
    assert code == 0
    assert load_roster(path).find("alice").tier is AccessTier.ADMIN


def test_add_user_defaults_to_view_tier(monkeypatch, path):
    _run(["user", "add", "bob"], monkeypatch, path, answers=[STRONG])
    assert load_roster(path).find("bob").tier is AccessTier.VIEW


def test_add_user_rejects_weak_password_with_exit_1(monkeypatch, path, capsys):
    code = _run(["user", "add", "alice"], monkeypatch, path, answers=["weak"])
    assert code == 1
    assert load_roster(path).find("alice") is None
    assert "12" in capsys.readouterr().out


def test_add_agent_prints_the_token(monkeypatch, path, capsys):
    code = _run(["user", "add", "builder", "--agent", "--tier", "edit"], monkeypatch, path)
    assert code == 0
    agent = load_roster(path).find("builder")
    assert agent.is_agent
    assert agent.token in capsys.readouterr().out


def test_remove_user(monkeypatch, path):
    add_user("bob", STRONG, AccessTier.VIEW, path=path)
    assert _run(["user", "remove", "bob"], monkeypatch, path) == 0
    assert load_roster(path).find("bob") is None


def test_remove_unknown_user_exits_1(monkeypatch, path):
    assert _run(["user", "remove", "ghost"], monkeypatch, path) == 1


def test_list_shows_names_and_tiers(monkeypatch, path, capsys):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert _run(["user", "list"], monkeypatch, path) == 0
    out = capsys.readouterr().out
    assert "alice" in out and "admin" in out


def test_list_never_prints_a_password_hash(monkeypatch, path, capsys):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    _run(["user", "list"], monkeypatch, path)
    assert "scrypt$" not in capsys.readouterr().out


def test_passwd_changes_the_password(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    new = "Battery-Staple7"
    assert _run(["user", "passwd", "alice"], monkeypatch, path, answers=[new]) == 0

    from haywire_studio.auth.operations import authenticate

    assert authenticate("alice", new, path=path) is not None


def test_tier_change(monkeypatch, path):
    add_user("bob", STRONG, AccessTier.VIEW, path=path)
    assert _run(["user", "tier", "bob", "edit"], monkeypatch, path) == 0
    assert load_roster(path).find("bob").tier is AccessTier.EDIT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_user_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'user' from 'haywire_studio.cli'`

- [ ] **Step 3: Write `cli/user.py`**

```python
"""``haywire user`` — manage principals in the global roster.

Runs against a stopped studio. A running studio caches the roster against its
mtime, so changes made here are picked up within a request; but enabling or
disabling authentication needs a restart, which is why that lives in
``haywire auth`` rather than here.
"""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from haywire.core.access import AccessTier

from haywire_studio.auth.operations import (
    add_agent,
    add_user,
    remove_principal,
    set_password,
    set_tier,
)
from haywire_studio.auth.passwords import POLICY_HELP
from haywire_studio.auth.roster import RosterError, load_roster

_TIERS = [tier.value for tier in AccessTier]


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("user", help="Manage studio principals (users and agents)")
    parser.add_argument(
        "--roster",
        default=None,
        help="Roster file to operate on (default: ~/.haywire/auth.json). Mainly for testing.",
    )
    actions = parser.add_subparsers(dest="user_command", required=True)

    add = actions.add_parser("add", help="Add a user or agent principal")
    add.add_argument("name")
    add.add_argument("--tier", choices=_TIERS, default=AccessTier.VIEW.value)
    add.add_argument("--agent", action="store_true", help="Create a token principal instead of a password one")
    add.add_argument("--workspace", default="", help="Scope an agent token to one project path")
    add.set_defaults(handler=_add)

    remove = actions.add_parser("remove", help="Remove a principal")
    remove.add_argument("name")
    remove.set_defaults(handler=_remove)

    listing = actions.add_parser("list", help="List principals")
    listing.set_defaults(handler=_list)

    passwd = actions.add_parser("passwd", help="Set a user's password")
    passwd.add_argument("name")
    passwd.set_defaults(handler=_passwd)

    tier = actions.add_parser("tier", help="Change a principal's access tier")
    tier.add_argument("name")
    tier.add_argument("tier", choices=_TIERS)
    tier.set_defaults(handler=_tier)


def _roster_path(args: argparse.Namespace) -> Path | None:
    raw = getattr(args, "roster", None)
    return Path(raw) if raw else None


def _prompt_password(name: str) -> str:
    """Prompt twice and require a match. Patched in tests."""
    print(f"Password policy: {POLICY_HELP}")
    first = getpass.getpass(f"New password for {name}: ")
    second = getpass.getpass("Repeat: ")
    if first != second:
        raise RosterError("The two passwords did not match.")
    return first


def _add(args: argparse.Namespace) -> int:
    path = _roster_path(args)
    tier = AccessTier(args.tier)
    try:
        if args.agent:
            agent = add_agent(args.name, tier, workspace=args.workspace, path=path)
            print(f"Created agent principal {agent.name!r} ({tier.value}).")
            print(f"  Token: {agent.token}")
            print("  Give this to the agent — it is stored in the roster and can be re-read at any time.")
        else:
            add_user(args.name, _prompt_password(args.name), tier, path=path)
            print(f"Created user principal {args.name!r} ({tier.value}).")
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


def _remove(args: argparse.Namespace) -> int:
    try:
        remove_principal(args.name, path=_roster_path(args))
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Removed {args.name!r}.")
    return 0


def _list(args: argparse.Namespace) -> int:
    try:
        roster = load_roster(_roster_path(args))
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1

    state = "enabled" if roster.enabled else "disabled"
    print(f"Authentication is {state}. {len(roster.principals)} principal(s):")
    for principal in roster.principals:
        scope = f"  workspace={principal.workspace}" if principal.workspace else ""
        print(f"  {principal.name:<24} {principal.kind:<6} {principal.tier.value:<6}{scope}")
    return 0


def _passwd(args: argparse.Namespace) -> int:
    try:
        set_password(args.name, _prompt_password(args.name), path=_roster_path(args))
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Password updated for {args.name!r}.")
    return 0


def _tier(args: argparse.Namespace) -> int:
    try:
        set_tier(args.name, AccessTier(args.tier), path=_roster_path(args))
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"{args.name!r} is now {args.tier}.")
    return 0
```

- [ ] **Step 4: Run the user CLI test**

Run: `uv run pytest tests/test_user_cli.py -v`
Expected: PASS, 10 tests.

- [ ] **Step 5: Write the failing test for `haywire auth`**

Create `tests/test_auth_cli.py`:

```python
"""haywire auth — enable/disable/status, each gated on a working admin login."""

import argparse

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.operations import add_user, enable_auth
from haywire_studio.auth.roster import load_roster
from haywire_studio.cli import authcmd

STRONG = "Correct-Horse9"


def _run(argv, monkeypatch, path, username=None, password=None):
    if username is not None:
        monkeypatch.setattr(authcmd, "_prompt_username", lambda: username)
    if password is not None:
        monkeypatch.setattr(authcmd, "_prompt_password", lambda: password)
    monkeypatch.setattr(authcmd, "_studio_is_running", lambda: False)
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    authcmd.register(subparsers)
    args = parser.parse_args(argv)
    args.roster = str(path)
    return args.handler(args)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "auth.json"


def test_enable_with_valid_admin_credentials(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 0
    assert load_roster(path).enabled is True


def test_enable_with_wrong_password_exits_1_and_does_not_enable(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert _run(["auth", "enable"], monkeypatch, path, "alice", "Wrong-Horse9!") == 1
    assert load_roster(path).enabled is False


def test_enable_with_no_admin_exits_1(monkeypatch, path, capsys):
    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 1
    assert "haywire user add" in capsys.readouterr().out


def test_disable_requires_credentials(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    assert _run(["auth", "disable"], monkeypatch, path, "alice", STRONG) == 0
    assert load_roster(path).enabled is False


def test_status_reports_disabled(monkeypatch, path, capsys):
    assert _run(["auth", "status"], monkeypatch, path) == 0
    assert "disabled" in capsys.readouterr().out


def test_status_reports_enabled_and_admin_count(monkeypatch, path, capsys):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    assert _run(["auth", "status"], monkeypatch, path) == 0
    out = capsys.readouterr().out
    assert "enabled" in out and "1 admin" in out


def test_enable_refuses_while_a_studio_is_running(monkeypatch, path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    monkeypatch.setattr(authcmd, "_prompt_username", lambda: "alice")
    monkeypatch.setattr(authcmd, "_prompt_password", lambda: STRONG)
    monkeypatch.setattr(authcmd, "_studio_is_running", lambda: True)

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    authcmd.register(subparsers)
    args = parser.parse_args(["auth", "enable"])
    args.roster = str(path)

    assert args.handler(args) == 1
    assert load_roster(path).enabled is False
```

- [ ] **Step 6: Run it to verify it fails**

Run: `uv run pytest tests/test_auth_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'authcmd'`

- [ ] **Step 7: Write `cli/authcmd.py`**

```python
"""``haywire auth`` — turn studio authentication on and off.

Both directions demand a working admin login. Anyone who can run this command
can also edit ``~/.haywire/auth.json`` by hand, so the check is not a barrier
against an attacker — it is a proof of recoverability. It makes the realistic
failure unreachable: enabling authentication with a roster whose passwords
nobody remembers.

Refuses to run while a studio is live in this workspace: the flag is read once
at startup, so flipping it under a running process produces a studio whose
behaviour no longer matches its own config file.
"""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from haywire_studio.auth.operations import disable_auth, enable_auth
from haywire_studio.auth.roster import RosterError, load_roster


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("auth", help="Enable or disable studio authentication")
    parser.add_argument(
        "--roster",
        default=None,
        help="Roster file to operate on (default: ~/.haywire/auth.json). Mainly for testing.",
    )
    actions = parser.add_subparsers(dest="auth_command", required=True)

    enable = actions.add_parser("enable", help="Turn authentication on (requires an admin login)")
    enable.set_defaults(handler=_enable)

    disable = actions.add_parser("disable", help="Turn authentication off (requires an admin login)")
    disable.set_defaults(handler=_disable)

    status = actions.add_parser("status", help="Show whether authentication is on")
    status.set_defaults(handler=_status)


def _roster_path(args: argparse.Namespace) -> Path | None:
    raw = getattr(args, "roster", None)
    return Path(raw) if raw else None


def _prompt_username() -> str:
    return input("Admin username: ").strip()


def _prompt_password() -> str:
    return getpass.getpass("Password: ")


def _studio_is_running() -> bool:
    """True when this workspace has a live studio process.

    Best-effort, via the sidecar the studio writes when it mounts Farmhand. It
    cannot see a studio running for a *different* workspace against the same
    global roster — that case is handled by the roster's atomic writes, which
    make a concurrent write last-one-wins rather than corrupting.
    """
    from haywire_studio.farmhand.identity import identity_status, read_identity

    ident = read_identity(Path.cwd())
    return ident is not None and identity_status(ident) == "alive"


def _guard_running_studio() -> bool:
    if _studio_is_running():
        print(
            "ERROR: a studio is running in this workspace.\n"
            "  Authentication is read once at startup, so it must be changed with the studio stopped.\n"
            "  Quit the studio and run this again."
        )
        return True
    return False


def _enable(args: argparse.Namespace) -> int:
    if _guard_running_studio():
        return 1
    try:
        enable_auth(_prompt_username(), _prompt_password(), path=_roster_path(args))
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1
    print("Authentication enabled. Start the studio and sign in at /login.")
    return 0


def _disable(args: argparse.Namespace) -> int:
    if _guard_running_studio():
        return 1
    try:
        disable_auth(_prompt_username(), _prompt_password(), path=_roster_path(args))
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1
    print("Authentication disabled. Everyone who can reach the studio is now a full operator.")
    return 0


def _status(args: argparse.Namespace) -> int:
    try:
        roster = load_roster(_roster_path(args))
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1
    state = "enabled" if roster.enabled else "disabled"
    admins = len(roster.admins())
    print(
        f"Authentication is {state} — {len(roster.principals)} principal(s), "
        f"{admins} admin{'' if admins == 1 else 's'}."
    )
    return 0
```

- [ ] **Step 7b: Import an existing Farmhand token on enable**

Without this, switching authentication on takes every already-configured agent
offline: the gate matches the **roster's** tokens, and a `farmhand_token` file
predating the roster is not in it. The agent would silently stop working at the
exact moment the operator changed something else.

Add to `tests/test_auth_cli.py`:

```python
def test_enable_imports_an_existing_farmhand_token(monkeypatch, path, tmp_path, capsys):
    from haywire_studio.auth.roster import load_roster

    workspace = tmp_path / "proj"
    (workspace / ".haywire").mkdir(parents=True)
    (workspace / ".haywire" / "farmhand_token").write_text("legacy-token-value")

    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    monkeypatch.chdir(workspace)
    monkeypatch.setattr(authcmd, "_confirm", lambda prompt: True)

    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 0

    imported = load_roster(path).find_by_token("legacy-token-value")
    assert imported is not None
    assert imported.is_agent
    assert imported.tier is AccessTier.EDIT
    assert imported.workspace == str(workspace.resolve())


def test_enable_skips_the_import_when_declined(monkeypatch, path, tmp_path):
    from haywire_studio.auth.roster import load_roster

    workspace = tmp_path / "proj"
    (workspace / ".haywire").mkdir(parents=True)
    (workspace / ".haywire" / "farmhand_token").write_text("legacy-token-value")

    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    monkeypatch.chdir(workspace)
    monkeypatch.setattr(authcmd, "_confirm", lambda prompt: False)

    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 0
    assert load_roster(path).find_by_token("legacy-token-value") is None


def test_enable_without_a_farmhand_token_asks_nothing(monkeypatch, path, tmp_path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    monkeypatch.chdir(tmp_path)

    def _should_not_be_called(prompt):
        raise AssertionError("no token to import — must not prompt")

    monkeypatch.setattr(authcmd, "_confirm", _should_not_be_called)
    assert _run(["auth", "enable"], monkeypatch, path, "alice", STRONG) == 0
```

Then add to `cli/authcmd.py`:

```python
def _confirm(prompt: str) -> bool:
    """Yes/no prompt. Patched in tests."""
    return input(f"{prompt} [y/N] ").strip().lower() in {"y", "yes"}


def _offer_token_import(roster_path_arg: Path | None) -> None:
    """Offer to bring this workspace's existing Farmhand token into the roster.

    With authentication off, the token lives in ``<workspace>/.haywire/farmhand_token``
    and the gate is not involved. Once on, the roster is authoritative — so an
    agent configured before the flip would stop working with no obvious cause.
    Imported at EDIT and scoped to this workspace, matching the blast radius the
    token already had.
    """
    from haywire_studio.auth.roster import KIND_AGENT, load_roster

    workspace = Path.cwd().resolve()
    token_file = workspace / ".haywire" / "farmhand_token"
    if not token_file.exists():
        return

    token = token_file.read_text(encoding="utf-8").strip()
    if not token:
        return

    roster = load_roster(roster_path_arg)
    if roster.find_by_token(token) is not None:
        return

    print(f"\nThis workspace has a Farmhand token at {token_file}.")
    print("Agents using it will stop working once authentication is on unless it")
    print("becomes a roster principal.")
    if not _confirm("Import it as an 'edit' agent principal scoped to this workspace?"):
        print("Skipped. Create one later with: haywire user add <name> --agent --tier edit")
        return

    name = f"farmhand-{workspace.name}"
    suffix = 2
    while roster.find(name) is not None:
        name = f"farmhand-{workspace.name}-{suffix}"
        suffix += 1

    roster.principals.append(
        Principal(
            name=name,
            kind=KIND_AGENT,
            tier=AccessTier.EDIT,
            token=token,
            workspace=str(workspace),
        )
    )
    save_roster(roster, roster_path_arg)
    print(f"Imported as agent principal {name!r} (edit, scoped to {workspace}).")
```

with these imports added to `cli/authcmd.py`:

```python
from haywire.core.access import AccessTier

from haywire_studio.auth.roster import Principal, save_roster
```

and call it from `_enable`, **before** the flag is written — so a failure to import never leaves authentication half-enabled:

```python
def _enable(args: argparse.Namespace) -> int:
    if _guard_running_studio():
        return 1
    roster_path_arg = _roster_path(args)
    try:
        username, password = _prompt_username(), _prompt_password()
        _offer_token_import(roster_path_arg)
        enable_auth(username, password, path=roster_path_arg)
    except RosterError as exc:
        print(f"ERROR: {exc}")
        return 1
    print("Authentication enabled. Start the studio and sign in at /login.")
    return 0
```

- [ ] **Step 8: Register both subcommands**

In `packages/haywire-studio/src/haywire_studio/cli/__init__.py`, change the import and the tuple:

```python
from haywire_studio.cli import authcmd, deps, docs, init, rename, share, user, verify
```

```python
SUBCOMMANDS: Sequence[_SubcommandModule] = (init, share, rename, deps, docs, verify, user, authcmd)
```

- [ ] **Step 9: Run both CLI tests**

Run: `uv run pytest tests/test_user_cli.py tests/test_auth_cli.py -v`
Expected: PASS, 20 tests.

- [ ] **Step 10: Verify the real CLI wires up**

```bash
uv run haywire --help
uv run haywire user --help
uv run haywire auth status
```

Expected: `user` and `auth` appear in the subcommand list; `auth status` prints `Authentication is disabled — 0 principal(s), 0 admins.`

- [ ] **Step 11: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/cli/ tests/test_user_cli.py tests/test_auth_cli.py
git commit -m "feat(auth): haywire user and haywire auth CLI subcommands"
```

---

### Task 6: Quality gate

- [ ] **Step 1: Lint and format**

```bash
uv run ruff check .
uv run ruff format --check .
```

- [ ] **Step 2: Type check**

```bash
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

- [ ] **Step 3: Pre-commit test gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/slice2.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/slice2.log
grep -E "passed|failed" /tmp/slice2.log | tail -1
```

Expected: `exit=0`.

- [ ] **Step 4: Confirm no test wrote to the real `~/.haywire/auth.json`**

```bash
ls -la ~/.haywire/auth.json 2>&1
```

Expected: `No such file or directory` (unless you created one by hand). Every test passes an explicit `path=`. If this file appeared, a test is leaking to the real home directory — find it and fix it before committing.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A && git commit -m "chore(auth): lint/type fixes for slice 2"
```

---

### Task 7 (final): Record delivery and drift

- [ ] **Step 1: Fill in the Drift Log below** — one line per deviation from this plan (what it said, what was built, why), or the words "No drift." explicitly.

- [ ] **Step 2: Record the public surface Slice 3 consumes** in the Delivered section: exact signatures for `load_roster`, `Roster`, `Principal`, `authenticate`, `RosterCache`, `install_resolver`.

- [ ] **Step 3: Flip the front matter** `status: planned` → `status: implemented`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-08-15-auth-2-roster-cli.md
git commit -m "docs(plan): slice 2 complete — roster and CLI"
```

---

## Delivered

*(Filled in by the final task.)*

## Drift Log

*(Filled in by the final task. One line per deviation, or the words "No drift.")*
