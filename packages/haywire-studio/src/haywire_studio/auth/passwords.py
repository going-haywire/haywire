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
