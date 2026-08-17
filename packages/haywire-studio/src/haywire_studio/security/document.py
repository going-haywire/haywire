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

    if doc.auth.enabled and not doc.auth.user_admins():
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
    if auth.enabled and not auth.user_admins():
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
