"""The ``require`` token: derivation, and the three states it distinguishes.

Both producers — the CI feed generator and the share wizard — go through
``haywire_core_requirement``, so this covers the derivation once for both.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from haywire.core.marketstall.requirement import haywire_core_requirement, requirement_specifier

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.generate_marketstall import _ENTRY_FIELD_ORDER  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("deps", "expected"),
    [
        (["haywire-core~=0.0.37"], "haywire-core~=0.0.37"),
        (["haywire-core>=0.0.31"], "haywire-core>=0.0.31"),
        (["haywire-core>=0.0.31,<1.0.0"], "haywire-core>=0.0.31,<1.0.0"),
        (["toml", "haywire-core~=0.0.37", "packaging"], "haywire-core~=0.0.37"),
        # Declared with no floor is NOT the same as undeclared — see below.
        (["haywire-core"], "haywire-core"),
        (["haywire-studio~=0.0.37", "toml"], None),
        ([], None),
    ],
)
def test_requirement_is_read_off_the_core_floor(deps, expected):
    assert haywire_core_requirement(deps) == expected


def test_undeclared_and_floorless_are_distinct():
    """The whole reason the token carries the package name.

    A bare specifier field collapses both to "", losing the difference between
    "nobody answered" and "the author deliberately declared no floor" — and the
    wizard's no-pin option produces the latter.
    """
    assert haywire_core_requirement([]) is None
    assert haywire_core_requirement(["haywire-core"]) == "haywire-core"


def test_haybale_core_is_not_mistaken_for_haywire_core():
    """Name matching must be exact — haybale-core is a different package."""
    assert haywire_core_requirement(["haybale-core~=0.0.37"]) is None


def test_environment_marker_is_stripped():
    assert (
        haywire_core_requirement(['haywire-core>=0.0.31; python_version >= "3.12"'])
        == "haywire-core>=0.0.31"
    )


def test_internal_whitespace_is_normalized():
    """The emitted token must not vary with how the author spaced their entry."""
    assert haywire_core_requirement(["haywire-core >= 0.0.31"]) == "haywire-core>=0.0.31"


@pytest.mark.parametrize(
    ("token", "expected"),
    [("haywire-core>=0.0.31", ">=0.0.31"), ("haywire-core", ""), ("", "")],
)
def test_requirement_specifier_splits_the_token(token, expected):
    assert requirement_specifier(token) == expected


def test_field_order_carries_require():
    """emit_stall_toml() skips any key absent from _ENTRY_FIELD_ORDER, so a
    field missing here is silently dropped from the published feed."""
    assert "require" in _ENTRY_FIELD_ORDER
