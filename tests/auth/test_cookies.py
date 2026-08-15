"""HMAC-signed session cookie. The signature is the whole boundary — test it hard."""

import base64
import json
import stat

import pytest

from haywire_studio.auth.cookies import (
    load_or_create_secret,
    rotate_secret,
    sign_session,
    verify_session,
)

SECRET = b"0" * 32
OTHER = b"1" * 32


def test_round_trip():
    assert verify_session(sign_session("alice", secret=SECRET, days=30), secret=SECRET) == "alice"


def test_wrong_secret_rejects():
    assert verify_session(sign_session("alice", secret=SECRET, days=30), secret=OTHER) is None


def test_tampered_payload_rejects():
    token = sign_session("alice", secret=SECRET, days=30)
    payload_b64, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    payload["p"] = "root"
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    assert verify_session(f"{forged}.{signature}", secret=SECRET) is None


def test_expired_token_rejects():
    token = sign_session("alice", secret=SECRET, days=1, now=1000.0)
    assert verify_session(token, secret=SECRET, now=1000.0 + 2 * 86400) is None


def test_unexpired_token_accepts():
    token = sign_session("alice", secret=SECRET, days=30, now=1000.0)
    assert verify_session(token, secret=SECRET, now=1000.0 + 86400) == "alice"


def test_days_zero_never_expires():
    token = sign_session("alice", secret=SECRET, days=0, now=1000.0)
    assert verify_session(token, secret=SECRET, now=1000.0 + 10_000 * 86400) == "alice"


def test_expiry_cannot_be_extended_without_the_secret():
    """The expiry is inside the signed payload — re-signing is the only way to change it."""
    token = sign_session("alice", secret=SECRET, days=1, now=1000.0)
    payload_b64, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    payload["exp"] = 10**12
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    assert verify_session(f"{forged}.{signature}", secret=SECRET) is None


@pytest.mark.parametrize(
    "token",
    ["", ".", "a.b", "no-dot", "....", "!!!.???", "a.b.c"],
)
def test_malformed_tokens_reject_without_raising(token):
    assert verify_session(token, secret=SECRET) is None


def test_principal_with_a_dot_survives_the_round_trip():
    """Payload is base64url JSON, not delimiter-joined fields — separators in names are safe."""
    assert verify_session(sign_session("a.b|c", secret=SECRET, days=30), secret=SECRET) == "a.b|c"


# --- secret file ------------------------------------------------------


def test_secret_is_created_at_0600(tmp_path):
    path = tmp_path / "session_secret"
    secret = load_or_create_secret(path)
    assert len(secret) == 32
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_secret_is_stable_across_calls(tmp_path):
    path = tmp_path / "session_secret"
    assert load_or_create_secret(path) == load_or_create_secret(path)


def test_rotate_replaces_the_secret(tmp_path):
    path = tmp_path / "session_secret"
    first = load_or_create_secret(path)
    second = rotate_secret(path)
    assert first != second
    assert load_or_create_secret(path) == second


def test_rotating_invalidates_every_existing_cookie(tmp_path):
    path = tmp_path / "session_secret"
    secret = load_or_create_secret(path)
    token = sign_session("alice", secret=secret, days=30)
    assert verify_session(token, secret=rotate_secret(path)) is None
