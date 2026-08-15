"""The signed session cookie (ADR 0027).

This signature is the single artifact standing between an anonymous HTTP
request and full access to the studio, so the rules below are not style
preferences:

* **The whole payload is signed, expiry included.** Validation reads the expiry
  out of the *signed* payload — never from the cookie's ``Max-Age``, which the
  client controls and can simply omit.
* **``hmac.compare_digest``**, never ``==``.
* **base64url JSON, not delimiter-joined fields.** ``alice|admin`` splits
  ambiguously the moment a principal name contains the separator.
* **The cookie carries identity, never authority.** No tier in the payload — the
  tier is read live from the roster, which is what makes removing a principal an
  actual revocation rather than a request (ADR 0027).

Rotating the secret invalidates every issued cookie at once. That is the
"log everyone out" lever.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

COOKIE_NAME = "haywire_session"
SECRET_FILENAME = "session_secret"
SECRET_BYTES = 32


def secret_path() -> Path:
    """``~/.haywire/session_secret`` — beside the roster, same 0600 discipline."""
    return Path.home() / ".haywire" / SECRET_FILENAME


def load_or_create_secret(path: Path | None = None) -> bytes:
    """Read the signing secret, generating it on first use."""
    target = path or secret_path()
    if target.exists():
        data = target.read_bytes()
        if len(data) >= SECRET_BYTES:
            return data
    return rotate_secret(target)


def rotate_secret(path: Path | None = None) -> bytes:
    """Generate and persist a fresh secret, invalidating every issued cookie."""
    target = path or secret_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_bytes(SECRET_BYTES)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_bytes(secret)
    tmp.chmod(0o600)
    tmp.replace(target)
    return secret


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def sign_session(principal: str, *, secret: bytes, days: int, now: float | None = None) -> str:
    """Build ``<base64url-payload>.<base64url-signature>``.

    ``days=0`` means never expires — the kiosk case, where a show machine that
    reboots at 6am must not land on a login screen with nobody around.
    """
    issued = int(now if now is not None else time.time())
    payload = {"p": principal, "iat": issued, "exp": 0 if days == 0 else issued + days * 86400}
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64encode(signature)}"


def verify_session(token: str, *, secret: bytes, now: float | None = None) -> str | None:
    """Return the principal name, or ``None`` for any failure.

    Never raises: a malformed cookie is a rejection, not a 500 inside middleware
    that runs before every request in the process.
    """
    try:
        payload_b64, signature_b64 = token.split(".")
    except ValueError:
        return None

    try:
        expected = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64decode(signature_b64), expected):
            return None
        payload = json.loads(_b64decode(payload_b64))
    except Exception:
        return None

    principal = payload.get("p")
    expires = payload.get("exp")
    if not isinstance(principal, str) or not principal or not isinstance(expires, int):
        return None

    if expires != 0 and (now if now is not None else time.time()) >= expires:
        return None

    return principal
