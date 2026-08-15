"""NetworkSettings field validation: the shared _valid_cidr_list helper used by
allowed_remote_ranges and trusted_proxies."""

import pytest

from haywire_studio.network.settings import NetworkSettings, _valid_cidr_list

pytestmark = pytest.mark.unit


# -- _valid_cidr_list -------------------------------------------------------


def test_valid_cidr_list_accepts_empty_string():
    assert _valid_cidr_list("") is True


def test_valid_cidr_list_accepts_single_cidr():
    assert _valid_cidr_list("192.168.1.0/24") is True


def test_valid_cidr_list_accepts_multiple_comma_separated_entries():
    assert _valid_cidr_list("192.168.1.0/24, 10.0.0.0/8") is True


def test_valid_cidr_list_accepts_bare_ip_via_strict_false():
    # ip_network(..., strict=False) accepts a bare host address (treated as a /32 or /128).
    assert _valid_cidr_list("192.168.1.5") is True


def test_valid_cidr_list_accepts_ipv6_cidr():
    assert _valid_cidr_list("2001:db8::/32") is True


def test_valid_cidr_list_rejects_malformed_entry():
    assert _valid_cidr_list("not-a-cidr") is False


def test_valid_cidr_list_rejects_one_bad_entry_among_good_ones():
    assert _valid_cidr_list("192.168.1.0/24, garbage") is False


def test_valid_cidr_list_rejects_out_of_range_octet():
    assert _valid_cidr_list("999.1.1.1/24") is False


# -- NetworkSettings field wiring -------------------------------------------


def test_allowed_remote_ranges_default_is_empty_string():
    assert NetworkSettings.__dict__["allowed_remote_ranges"]._default == ""


def test_trusted_proxies_default_is_empty_string():
    assert NetworkSettings.__dict__["trusted_proxies"]._default == ""


def test_allowed_remote_ranges_rejects_malformed_write():
    settings = NetworkSettings()
    original = settings.allowed_remote_ranges
    settings.allowed_remote_ranges = "not-a-cidr"
    # Rejected writes are dropped silently by the descriptor (see
    # .insights/project_settings_bags_include_props.md) — value stays unchanged.
    assert settings.allowed_remote_ranges == original


def test_allowed_remote_ranges_accepts_valid_write():
    settings = NetworkSettings()
    settings.allowed_remote_ranges = "10.0.0.0/8"
    assert settings.allowed_remote_ranges == "10.0.0.0/8"
    settings.allowed_remote_ranges = ""  # reset


def test_trusted_proxies_rejects_malformed_write():
    settings = NetworkSettings()
    original = settings.trusted_proxies
    settings.trusted_proxies = "not-a-cidr"
    assert settings.trusted_proxies == original


def test_trusted_proxies_accepts_valid_write():
    settings = NetworkSettings()
    settings.trusted_proxies = "172.16.0.0/12"
    assert settings.trusted_proxies == "172.16.0.0/12"
    settings.trusted_proxies = ""  # reset


def test_allowed_remote_ranges_and_trusted_proxies_share_validator_function():
    # Same helper wired to both fields — not two independent copies.
    assert (
        NetworkSettings.__dict__["allowed_remote_ranges"]._validator
        is NetworkSettings.__dict__["trusted_proxies"]._validator
        is _valid_cidr_list
    )


def test_no_enabled_when_metadata_on_advanced_fields():
    # The plan explicitly forbids enabled_when metadata (dead config on this
    # render path) — guard against it creeping back in.
    for name in ("public_hostname", "trusted_proxies", "allowed_remote_ranges"):
        metadata = NetworkSettings.__dict__[name]._metadata
        assert "enabled_when" not in metadata


def test_advanced_fields_are_in_advanced_category():
    assert NetworkSettings.__dict__["public_hostname"]._category == "advanced"
    assert NetworkSettings.__dict__["trusted_proxies"]._category == "advanced"


def test_network_category_fields():
    assert NetworkSettings.__dict__["port"]._category == "network"
    assert NetworkSettings.__dict__["expose_to_network"]._category == "network"
    assert NetworkSettings.__dict__["allowed_remote_ranges"]._category == "network"


def test_field_declaration_order_advanced_last_and_contiguous():
    names = list(NetworkSettings._property_settings().keys())
    assert names == [
        "port",
        "expose_to_network",
        "allowed_remote_ranges",
        "public_hostname",
        "trusted_proxies",
        "ssl_certfile",
        "ssl_keyfile",
    ]


def test_restrict_to_loopback_removed_from_network_settings():
    assert "restrict_to_loopback" not in NetworkSettings.__dict__


def test_expose_to_network_default_is_false():
    assert NetworkSettings.__dict__["expose_to_network"]._default is False


def test_tls_settings_default_to_empty():
    settings = NetworkSettings()
    assert settings.ssl_certfile == ""
    assert settings.ssl_keyfile == ""
