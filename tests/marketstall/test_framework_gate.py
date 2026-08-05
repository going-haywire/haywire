"""Tests for the pre-emptive framework-requirement gate.

The gate is ADVISORY: it reads author-declared marketstall metadata, so every
way the check can fail to apply must pass rather than block. The resolver's
constraints file remains the real guard.
"""

from __future__ import annotations

import pytest

from haywire.core.marketstall import check_require
from haywire.core.marketstall.framework_gate import installed_core_version


@pytest.mark.unit
def test_conflict_names_both_sides():
    """The message must name the requirement AND what is running — a bare
    "needs a different version" is the complaint this gate exists to fix."""
    verdict = check_require("haywire-core~=0.0.37", installed="0.0.36")

    assert verdict.ok is False
    assert "~=0.0.37" in verdict.message
    assert "0.0.36" in verdict.message
    assert "Check for updates" in verdict.message


@pytest.mark.unit
@pytest.mark.parametrize(
    ("declared", "installed"),
    [
        ("haywire-core>=0.0.31", "0.0.36"),  # satisfied
        ("haywire-core~=0.0.36", "0.0.36"),  # exact compatible release
        ("haywire-core>=0.0.31,<1.0.0", "0.0.36"),  # bounded range
    ],
)
def test_satisfied_requirements_pass(declared, installed):
    assert check_require(declared, installed=installed).ok is True


@pytest.mark.unit
@pytest.mark.parametrize(
    ("declared", "installed", "why"),
    [
        ("", "0.0.36", "undeclared — the field is absent from the entry"),
        ("   ", "0.0.36", "blank is undeclared"),
        ("haywire-core", "0.0.36", "declared with no floor constrains nothing"),
        ("numpy>=2.0", "0.0.36", "a token for another package is metadata we cannot act on"),
        ("haywire-core@@bad", "0.0.36", "unparseable specifier is our metadata bug"),
        ("haywire-core>=0.0.37", "not-a-version", "unparseable installed version"),
        ("haywire-core>=0.0.37", "", "haywire-core not installed"),
    ],
)
def test_unprovable_cases_never_block(declared, installed, why):
    """A gap in metadata is not evidence about the user's environment.

    Blocking on one would turn an advisory nicety into a wall in front of an
    install that may well succeed.
    """
    assert check_require(declared, installed=installed).ok is True, why


@pytest.mark.unit
def test_prerelease_framework_satisfies_a_floor():
    """A user running a prerelease strictly newer than the floor is satisfied.

    packaging excludes prereleases by default, which would block 0.0.38rc1
    against ">=0.0.37" — a strictly newer framework reported as too old.
    """
    assert check_require("haywire-core>=0.0.37", installed="0.0.38rc1").ok is True


@pytest.mark.unit
def test_installed_core_version_reads_real_metadata():
    """The helper resolves against the running env, or "" when absent."""
    value = installed_core_version()

    assert isinstance(value, str)
    # haywire-core is installed in this test env, so it must report something.
    assert value
