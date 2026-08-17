"""The rules for changing the network and Farmhand blocks (ADR 0028).

:mod:`document` is the document — read it, write it, validate it. This module
is the *verbs*: what "expose" means, what it demands first, and what it leaves
alone. They live apart for the reason ``auth/operations.py`` already does — the
CLI and any future UI call the same functions and cannot drift into two sets of
rules.

**Exposure is a verb, not a boolean.** ``expose_to_network`` used to be one bit
in a settings panel, but safe exposure is three or four coordinated decisions
and a checkbox cannot express a precondition. Every refusal here names the one
command that fixes it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from haywire_studio.security.document import (
    NetworkPolicy,
    SecurityDocument,
    load_document,
    save_document,
)
from haywire_studio.security.errors import SecurityError


def expose(
    ranges: Sequence[str],
    *,
    public_hostname: str | None = None,
    trusted_proxies: Iterable[str] | None = None,
    path: Path | None = None,
) -> SecurityDocument:
    """Bind beyond loopback, admitting *ranges*.

    Refuses unless authentication is on, TLS is configured and at least one
    range is given — those three checks live in
    :func:`~haywire_studio.security.document.validate`, so this function does
    not restate them; it assembles the document it wants and lets the write
    path reject it. That is deliberate: a second copy of the preconditions here
    is a second copy that can disagree with the one the studio boots against.

    ``public_hostname`` and ``trusted_proxies`` are left untouched when not
    given, so re-running ``expose`` to change subnets does not silently drop a
    reverse-proxy configuration.
    """
    doc = load_document(path)
    doc.network = NetworkPolicy(
        exposed=True,
        allowed_ranges=_clean(ranges),
        public_hostname=(
            doc.network.public_hostname if public_hostname is None else public_hostname.strip()
        ),
        trusted_proxies=(
            doc.network.trusted_proxies if trusted_proxies is None else _clean(trusted_proxies)
        ),
        tls_certfile=doc.network.tls_certfile,
        tls_keyfile=doc.network.tls_keyfile,
    )
    save_document(doc, path)
    return doc


def seal(*, path: Path | None = None) -> SecurityDocument:
    """Bind to loopback again.

    **The allowlist is kept.** Sealing is usually temporary — a laptop leaving
    the venue — and discarding the ranges would make the return trip a
    re-typing exercise. Exposure is the bit that decides reachability; the
    ranges are inert while it is off.
    """
    doc = load_document(path)
    doc.network.exposed = False
    save_document(doc, path)
    return doc


def set_farmhand_enabled(enabled: bool, *, path: Path | None = None) -> SecurityDocument:
    """Serve, or stop serving, the MCP endpoint at ``/mcp``."""
    doc = load_document(path)
    doc.farmhand.enabled = enabled
    save_document(doc, path)
    return doc


def set_farmhand_loopback(restrict: bool, *, path: Path | None = None) -> SecurityDocument:
    """Turn the DNS-rebinding ``Host``/``Origin`` check on or off.

    Turning it **off** demands authentication, and that check lives here rather
    than in ``validate`` because it constrains a transition, not a state: a
    document with the check off and authentication off is not corrupt, it is
    simply what you get when someone disables authentication afterwards — and
    refusing to load that would be a lockout. Refusing to *enter* it is enough,
    and ``haywire security status`` reports the combination if it is reached
    another way.
    """
    doc = load_document(path)
    if not restrict and not doc.auth.enabled:
        raise SecurityError(
            "Farmhand cannot accept remote MCP clients while authentication is off — "
            "the DNS-rebinding check would be the only thing standing between a web page "
            "in your browser and this studio's tools.\n"
            "  Run 'haywire auth enable' first."
        )
    doc.farmhand.restrict_to_loopback = restrict
    save_document(doc, path)
    return doc


def write_tls_paths(certfile: str, keyfile: str, *, path: Path | None = None) -> SecurityDocument:
    """Point the studio at a certificate and key.

    Both are written together, always — exactly one of the pair is the
    half-configured state ``validate`` rejects, and it is not a state this
    function is permitted to create.
    """
    doc = load_document(path)
    doc.network.tls_certfile = certfile
    doc.network.tls_keyfile = keyfile
    save_document(doc, path)
    return doc


def _clean(entries: Iterable[str]) -> tuple[str, ...]:
    """Strip and drop blanks, preserving order. Validation happens on write."""
    return tuple(entry.strip() for entry in entries if entry.strip())
