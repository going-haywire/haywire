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
