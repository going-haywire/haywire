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
    assert "12" in message
    assert "20" in message
