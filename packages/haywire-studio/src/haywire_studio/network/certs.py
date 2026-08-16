"""The certificate material — the two files on disk and the crypto that makes them.

This is the ``roster.py`` of the TLS feature: it owns the files and knows
nothing about settings, the CLI, or printing. The rules that compose these
pieces live in :mod:`haywire_studio.network.tls_operations`.

The private key is written with the same discipline as the roster and the
session secret — temp file, ``chmod`` **before** the rename, then an atomic
replace — so the key is never briefly world-readable and a crash mid-write
cannot leave a truncated key beside a valid certificate.

Self-signed by design (D3). The certificate is marked ``CA=True`` and signs
itself, which is what allows a user to import it into an OS trust store as its
own root and make the browser warning disappear.
"""

from __future__ import annotations

import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from haywire_studio.network.names import LocalNames

CERT_DIRNAME = "certs"
CERT_FILENAME = "studio.crt"
KEY_FILENAME = "studio.key"

# RSA 2048 over EC: maximum compatibility with whatever is on a mixed LAN
# (older phones, embedded browsers), and the performance difference is
# irrelevant at studio traffic volumes.
_KEY_SIZE = 2048

# Ten years. The certificate is generated once and trusted once per machine;
# a shorter life would reintroduce the re-trust chore with no security benefit
# for a self-signed LAN certificate (D5).
_VALIDITY_YEARS = 10

# Clock skew between the studio machine and a phone on the same LAN otherwise
# produces NET::ERR_CERT_NOT_YET_VALID, which reads as a broken command.
_BACKDATE = datetime.timedelta(hours=1)


class CertError(Exception):
    """A certificate could not be created, read, or trusted as valid."""


def default_dir() -> Path:
    """``~/.haywire/certs`` — global tier, beside the roster and the session
    secret, because TLS is a property of the machine's network identity (D1)."""
    return Path.home() / ".haywire" / CERT_DIRNAME


def paths(directory: Path | None = None) -> tuple[Path, Path]:
    """``(key_path, cert_path)`` for *directory*, defaulting to the global tier."""
    base = directory or default_dir()
    return base / KEY_FILENAME, base / CERT_FILENAME


def generate_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=_KEY_SIZE)


def sign_cert(
    key: rsa.RSAPrivateKey,
    names: LocalNames,
    *,
    years: int = _VALIDITY_YEARS,
    now: datetime.datetime | None = None,
) -> x509.Certificate:
    """Self-sign a certificate covering every name in *names*.

    Every name goes into the SAN extension. Modern browsers ignore the Common
    Name entirely, so a certificate whose SAN list omits the address the user
    typed is rejected no matter what the CN says.
    """
    entries = _san_entries(names)
    if not entries:
        raise CertError("A certificate needs at least one name or address to cover.")

    moment = now or datetime.datetime.now(datetime.timezone.utc)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, _common_name(names)),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Haywire Studio"),
        ]
    )

    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)  # self-signed: subject is its own issuer
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(moment - _BACKDATE)
        .not_valid_after(moment + datetime.timedelta(days=365 * years))
        .add_extension(x509.SubjectAlternativeName(entries), critical=False)
        # CA=True so the certificate can be imported into a trust store as its
        # own root — that is what 'haywire ssl trust' relies on.
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )


def write_key(key: rsa.RSAPrivateKey, directory: Path | None = None) -> Path:
    """Write the private key ``0600``, atomically.

    Unencrypted on disk, matching the roster's agent tokens: a passphrase the
    studio would have to store beside the key protects nothing, and one the
    user must type defeats unattended startup on a kiosk machine.
    """
    key_path, _ = paths(directory)
    payload = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _atomic_write(key_path, payload, mode=0o600)
    return key_path


def write_cert(cert: x509.Certificate, directory: Path | None = None) -> Path:
    """Write the certificate ``0644``. Public material — only the key is secret."""
    _, cert_path = paths(directory)
    _atomic_write(cert_path, cert.public_bytes(serialization.Encoding.PEM), mode=0o644)
    return cert_path


def load_key(directory: Path | None = None) -> rsa.RSAPrivateKey:
    """Read the private key so ``update`` can re-sign without minting a new one."""
    key_path, _ = paths(directory)
    try:
        loaded = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    except FileNotFoundError as exc:
        raise CertError(f"No private key at {key_path}.") from exc
    except (ValueError, TypeError) as exc:
        raise CertError(f"The private key at {key_path} could not be read: {exc}") from exc
    if not isinstance(loaded, rsa.RSAPrivateKey):
        raise CertError(f"The key at {key_path} is not an RSA private key.")
    return loaded


def load_cert(directory: Path | None = None) -> x509.Certificate:
    _, cert_path = paths(directory)
    try:
        return x509.load_pem_x509_certificate(cert_path.read_bytes())
    except FileNotFoundError as exc:
        raise CertError(f"No certificate at {cert_path}.") from exc
    except ValueError as exc:
        raise CertError(f"The certificate at {cert_path} could not be read: {exc}") from exc


def cert_names(cert: x509.Certificate) -> LocalNames:
    """Read the SAN extension back out — the covered-names list for ``status``
    and the starting point for ``update`` (D4: amend, never rebuild)."""
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return LocalNames.empty()
    return LocalNames(
        dns=tuple(san.get_values_for_type(x509.DNSName)),
        ip=tuple(str(entry) for entry in san.get_values_for_type(x509.IPAddress)),
    )


def cert_expiry(cert: x509.Certificate) -> datetime.datetime:
    return cert.not_valid_after_utc


def key_matches_cert(key: rsa.RSAPrivateKey, cert: x509.Certificate) -> bool:
    """Whether *key* is the one *cert* was signed with.

    A drifted pair makes uvicorn fail at startup with a message naming neither
    file, so both ``status`` and ``update`` check this and say which two files
    disagree.

    A certificate carrying a non-RSA public key cannot have been signed by our
    RSA key, so it is a mismatch rather than an error — this module only ever
    generates RSA, but the file on disk may have been replaced by anything.
    """
    public = cert.public_key()
    if not isinstance(public, rsa.RSAPublicKey):
        return False
    return key.public_key().public_numbers() == public.public_numbers()


def fingerprint(cert: x509.Certificate) -> str:
    """SHA-256, colon-separated uppercase hex — the format every OS trust tool
    displays, so a user can compare the two by eye."""
    raw = cert.fingerprint(hashes.SHA256())
    return ":".join(f"{byte:02X}" for byte in raw)


def _san_entries(names: LocalNames) -> list[x509.GeneralName]:
    """Build SAN entries, rejecting anything that cannot legally be one."""
    entries: list[x509.GeneralName] = [x509.DNSName(name) for name in names.dns]
    for raw in names.ip:
        if "%" in raw:
            # A zone-suffixed link-local address is invalid in a SAN. names.py
            # filters these; reaching here means a caller bypassed it.
            raise CertError(f"{raw!r} carries a zone suffix and cannot be a certificate name.")
        try:
            entries.append(x509.IPAddress(ipaddress.ip_address(raw)))
        except ValueError as exc:
            raise CertError(f"{raw!r} is not a valid IP address.") from exc
    return entries


def _common_name(names: LocalNames) -> str:
    """A CN for display only — browsers read the SAN list, not this."""
    if names.dns:
        return names.dns[0]
    return names.ip[0] if names.ip else "haywire-studio"


def _atomic_write(path: Path, payload: bytes, *, mode: int) -> None:
    """Write via a temp file, chmod, then replace.

    ``chmod`` happens **before** the rename so the key is never visible with
    default permissions, even briefly — the same ordering the roster uses.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(payload)
    tmp.chmod(mode)
    tmp.replace(path)
