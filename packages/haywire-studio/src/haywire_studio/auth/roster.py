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
