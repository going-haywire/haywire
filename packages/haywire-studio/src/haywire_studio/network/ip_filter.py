"""IP allowlist for the studio's ASGI app when exposed beyond loopback.

Pure-ASGI (not BaseHTTPMiddleware) because NiceGUI's UI runs over Socket.IO
at /_nicegui_ws/ — a BaseHTTPMiddleware subclass sees only
scope["type"] == "http" and would let every UI interaction (the websocket
upgrade and all subsequent frames) through unfiltered.
"""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network

logger = logging.getLogger(__name__)

_IPAddress = IPv4Address | IPv6Address
_IPNetwork = IPv4Network | IPv6Network


class IPAllowlistMiddleware:
    """Reject connections whose TCP peer is outside the allowed ranges.

    Pure-ASGI (not BaseHTTPMiddleware) because NiceGUI's UI runs over
    Socket.IO at /_nicegui_ws/ — a BaseHTTPMiddleware subclass sees only
    scope["type"] == "http" and would let every UI interaction through.
    """

    def __init__(
        self,
        app,
        allowed_ranges: Iterable[str],
        trusted_proxies: Iterable[str] = (),
    ):
        # Accept raw CIDR strings (same comma-separated-field format
        # NetworkSettings stores) and parse once here so every request is a
        # cheap membership check rather than a re-parse. Invalid entries
        # raise ValueError — the caller (2b) is responsible for surfacing
        # that to the user before this middleware is ever constructed.
        self.app = app
        self.allowed_ranges: list[_IPNetwork] = [
            ipaddress.ip_network(entry, strict=False) for entry in allowed_ranges
        ]
        self.trusted_proxies: list[_IPNetwork] = [
            ipaddress.ip_network(entry, strict=False) for entry in trusted_proxies
        ]

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return

        peer = scope.get("client")
        if peer is None:
            logger.warning(
                "Rejecting connection with no peer address; allowed_ranges=%s",
                self.allowed_ranges,
            )
            await self._reject(scope, send)
            return

        peer_host = peer[0]
        try:
            peer_ip = ipaddress.ip_address(peer_host)
        except ValueError:
            logger.warning(
                "Rejecting connection with unparseable peer address %r; allowed_ranges=%s",
                peer_host,
                self.allowed_ranges,
            )
            await self._reject(scope, send)
            return

        if peer_ip.is_loopback:
            logger.debug("Allowing loopback peer %s", peer_ip)
            await self.app(scope, receive, send)
            return

        resolved_ip = self._resolve_client(peer_ip, scope)

        if self._is_allowed(resolved_ip):
            logger.debug("Allowing peer %s (resolved %s)", peer_ip, resolved_ip)
            await self.app(scope, receive, send)
            return

        logger.warning(
            "Rejecting peer %s (resolved %s); allowed_ranges=%s",
            peer_ip,
            resolved_ip,
            self.allowed_ranges,
        )
        await self._reject(scope, send)

    def _is_allowed(self, ip: _IPAddress) -> bool:
        return any(ip in network for network in self.allowed_ranges)

    def _resolve_client(self, peer_ip: _IPAddress, scope) -> _IPAddress:
        """Resolve the effective client IP, honoring X-Forwarded-For only
        when the direct peer is itself a trusted proxy.

        Rightmost-untrusted algorithm: XFF entries are appended
        left-to-right as a request hops through proxies (leftmost = the
        first-hop client, which is attacker-controlled since anyone can
        set that header). Scanning from the right and skipping entries
        that are themselves trusted proxies finds the first hop we didn't
        put there ourselves — the most trustworthy signal available.
        """
        if not self.trusted_proxies:
            return peer_ip
        if not any(peer_ip in network for network in self.trusted_proxies):
            return peer_ip

        xff = self._get_header(scope, b"x-forwarded-for")
        if xff is None:
            return peer_ip

        entries = [entry.strip() for entry in xff.split(",") if entry.strip()]
        for entry in reversed(entries):
            try:
                candidate = ipaddress.ip_address(entry)
            except ValueError:
                continue
            if not any(candidate in network for network in self.trusted_proxies):
                return candidate

        # Every entry in the chain (or the header itself) was trusted/unusable.
        return peer_ip

    @staticmethod
    def _get_header(scope, name: bytes) -> str | None:
        for key, value in scope.get("headers", []):
            if key == name:
                return value.decode("latin-1")
        return None

    async def _reject(self, scope, send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = b'{"error": "forbidden"}'
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})
