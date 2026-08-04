"""The CI feed generator's requires_haywire derivation.

In-repo packages never run the share wizard, so nobody authors a
requires_haywire for them. CI derives it from the haywire-core floor in
pyproject.toml — the same value the wizard writes to its first carrier.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.generate_marketstall import _ENTRY_FIELD_ORDER, _haywire_core_specifier  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("deps", "expected"),
    [
        (["haywire-core~=0.0.37"], "~=0.0.37"),
        (["haywire-core>=0.0.31"], ">=0.0.31"),
        (["haywire-core>=0.0.31,<1.0.0"], ">=0.0.31,<1.0.0"),
        (["toml", "haywire-core~=0.0.37", "packaging"], "~=0.0.37"),
        (["haywire-core"], ""),  # present but unpinned -> nothing to declare
        (["haywire-studio~=0.0.37", "toml"], ""),  # core absent
        ([], ""),
    ],
)
def test_specifier_is_read_off_the_core_floor(deps, expected):
    assert _haywire_core_specifier(deps) == expected


def test_haybale_core_is_not_mistaken_for_haywire_core():
    """Name matching must be exact — haybale-core is a different package."""
    assert _haywire_core_specifier(["haybale-core~=0.0.37"]) == ""


def test_environment_marker_is_stripped():
    assert _haywire_core_specifier(['haywire-core>=0.0.31; python_version >= "3.12"']) == ">=0.0.31"


def test_field_order_carries_requires_haywire():
    """emit_stall_toml() skips any key absent from _ENTRY_FIELD_ORDER, so a
    field missing here is silently dropped from the published feed."""
    assert "requires_haywire" in _ENTRY_FIELD_ORDER
