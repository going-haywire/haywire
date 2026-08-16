"""The certificate material on disk — key, cert, and reading them back."""

import ipaddress
import stat

import pytest
from cryptography import x509

from haywire_studio.network.certs import (
    CertError,
    cert_expiry,
    cert_names,
    fingerprint,
    generate_key,
    key_matches_cert,
    load_cert,
    load_key,
    paths,
    sign_cert,
    write_cert,
    write_key,
)
from haywire_studio.network.names import LocalNames

pytestmark = pytest.mark.unit


@pytest.fixture
def names():
    return LocalNames(dns=("localhost", "box.local"), ip=("127.0.0.1", "10.0.0.5"))


def test_every_requested_name_lands_in_the_san_extension(names):
    """A CN-only certificate is rejected by every current browser."""
    cert = sign_cert(generate_key(), names)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert set(san.get_values_for_type(x509.DNSName)) == {"localhost", "box.local"}
    assert set(san.get_values_for_type(x509.IPAddress)) == {
        ipaddress.ip_address("127.0.0.1"),
        ipaddress.ip_address("10.0.0.5"),
    }


def test_not_valid_before_is_backdated(names):
    """Clock skew between the studio and a phone on the same LAN otherwise
    yields ERR_CERT_NOT_YET_VALID, which looks like a broken command."""
    import datetime

    cert = sign_cert(generate_key(), names)
    now = datetime.datetime.now(datetime.timezone.utc)
    assert cert.not_valid_before_utc < now - datetime.timedelta(minutes=30)


def test_validity_defaults_to_ten_years(names):
    """Generated once, trusted once — an annual expiry is pure friction."""
    cert = sign_cert(generate_key(), names)
    span = cert.not_valid_after_utc - cert.not_valid_before_utc
    assert span.days > 3600


def test_certificate_is_self_signed_and_a_ca(names):
    """It must be importable into a trust store as its own root."""
    cert = sign_cert(generate_key(), names)
    assert cert.subject == cert.issuer
    basic = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    assert basic.ca is True


def test_key_file_is_private_and_cert_is_public(tmp_path, names):
    key = generate_key()
    write_key(key, tmp_path)
    write_cert(sign_cert(key, names), tmp_path)
    key_path, cert_path = paths(tmp_path)
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(cert_path.stat().st_mode) == 0o644


def test_names_round_trip_through_disk(tmp_path, names):
    key = generate_key()
    write_key(key, tmp_path)
    write_cert(sign_cert(key, names), tmp_path)
    recovered = cert_names(load_cert(tmp_path))
    assert set(recovered.dns) == set(names.dns)
    assert set(recovered.ip) == set(names.ip)


def test_key_round_trips_through_disk(tmp_path, names):
    """update reuses the key, so it must survive a write/read cycle intact."""
    key = generate_key()
    write_key(key, tmp_path)
    reloaded = load_key(tmp_path)
    cert = sign_cert(reloaded, names)
    assert key_matches_cert(key, cert)


def test_key_matches_cert_detects_a_mismatch(names):
    cert = sign_cert(generate_key(), names)
    assert key_matches_cert(generate_key(), cert) is False


def test_zone_suffix_never_reaches_a_san():
    """A '%' in a SAN is invalid; certs.py must reject rather than emit it."""
    with pytest.raises(CertError):
        sign_cert(generate_key(), LocalNames(dns=(), ip=("fe80::1%en0",)))


def test_signing_with_no_names_is_refused():
    """A certificate covering nothing is never what the caller meant."""
    with pytest.raises(CertError):
        sign_cert(generate_key(), LocalNames.empty())


def test_load_cert_on_missing_file_raises_cert_error(tmp_path):
    with pytest.raises(CertError):
        load_cert(tmp_path)


def test_load_cert_on_corrupt_file_raises_cert_error(tmp_path):
    _, cert_path = paths(tmp_path)
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_text("not a certificate", encoding="utf-8")
    with pytest.raises(CertError):
        load_cert(tmp_path)


def test_fingerprint_is_colon_separated_hex(tmp_path, names):
    cert = sign_cert(generate_key(), names)
    value = fingerprint(cert)
    assert value.count(":") == 31
    assert value.upper() == value


def test_cert_expiry_is_timezone_aware(names):
    assert cert_expiry(sign_cert(generate_key(), names)).tzinfo is not None


def test_writes_are_atomic_leaving_no_temp_files(tmp_path, names):
    key = generate_key()
    write_key(key, tmp_path)
    write_cert(sign_cert(key, names), tmp_path)
    key_path, _ = paths(tmp_path)
    assert not list(key_path.parent.glob(".*.tmp"))


def test_rewriting_replaces_rather_than_appends(tmp_path, names):
    """update() re-signs into the same path; a stale cert must not linger."""
    key = generate_key()
    write_cert(sign_cert(key, names), tmp_path)
    wider = names.extend(["10.0.0.9"])
    write_cert(sign_cert(key, wider), tmp_path)
    assert "10.0.0.9" in cert_names(load_cert(tmp_path)).ip
