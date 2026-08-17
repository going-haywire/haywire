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
