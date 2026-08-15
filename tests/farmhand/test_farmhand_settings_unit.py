"""FarmhandSettings field wiring, including restrict_to_loopback (moved here
from NetworkSettings — see .superpowers/sdd/task-1-brief.md 1b)."""

import pytest

from haywire_studio.farmhand.settings import FarmhandSettings

pytestmark = pytest.mark.unit


def test_restrict_to_loopback_descriptor_default_is_true():
    assert FarmhandSettings.__dict__["restrict_to_loopback"]._default is True


def test_restrict_to_loopback_is_in_farmhand_category():
    # Stays out of "advanced" so it renders alongside require_auth — the pair
    # guards the same mount and is incomplete alone.
    assert FarmhandSettings.__dict__["restrict_to_loopback"]._category == "farmhand"


def test_restrict_to_loopback_description_mentions_dns_rebinding():
    description = FarmhandSettings.__dict__["restrict_to_loopback"]._description
    assert "DNS-rebinding" in description or "DNS rebinding" in description.lower()


def test_restrict_to_loopback_description_disclaims_forged_header_defence():
    description = FarmhandSettings.__dict__["restrict_to_loopback"]._description.lower()
    assert "forged" in description


def test_field_declaration_order():
    names = list(FarmhandSettings._property_settings().keys())
    assert names == ["enabled", "require_auth", "restrict_to_loopback"]
