"""The authentication gate (ADR 0027).

**Pure-ASGI, not BaseHTTPMiddleware.** NiceGUI's entire UI runs over Socket.IO
at ``/_nicegui_ws/``; a ``BaseHTTPMiddleware`` subclass only ever sees
``scope["type"] == "http"``, so it would gate the login page and let every
subsequent websocket frame — the whole application — through unfiltered. This
mirrors ``network/ip_filter.py``, which is pure-ASGI for exactly the same
reason. If you are about to "simplify" this into a Starlette middleware class:
don't. See ADR 0026.

**One gate, two credentials.** ``/mcp`` is mounted *inside* this same ASGI app,
so a root-level wrapper covers it whether or not that was intended. Rather than
carving it out — which would make the boundary's correctness depend on
``FarmhandSettings.require_auth`` staying True — the gate accepts a valid
session cookie *or* a valid agent bearer token. ``BearerTokenMiddleware`` stays
mounted underneath as defence in depth.

**A websocket is one scope.** ASGI calls the app once per connection; the whole
connection lifetime then happens inside that call. So this check runs at the
handshake and never again for that socket. That makes it free, and it means the
gate cannot revoke a socket it has already admitted — revocation reaches live
sessions by push, from ``eviction.py``.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from haywire_studio.auth.cookies import COOKIE_NAME, verify_session
from haywire_studio.auth.live import RosterCache

logger = logging.getLogger(__name__)

#: Reachable without any credential. Exactly two routes, both plain HTTP.
#: Adding anything here widens the unauthenticated surface — in particular,
#: never add ``/_nicegui_ws/`` or any ``/_nicegui/`` asset path.
EXEMPT_PATHS = frozenset({"/login"})

#: Where the resolved principal name is stashed for downstream consumers —
#: the NiceGUI page handler (which binds it onto SessionContext) and the
#: Farmhand handlers (which filter the tool list by its tier).
PRINCIPAL_SCOPE_KEY = "haywire_principal"

_LAST_SEEN: dict[str, float] = {}


def last_seen() -> dict[str, float]:
    """principal name → monotonic timestamp of their most recent admitted request.

    Drives agent presence in the TopBar. For a browser principal an open socket
    is the better liveness signal; for an agent this is the only one, because
    MCP traffic is request-shaped and its ``ping`` is an optional protocol
    message.
    """
    return _LAST_SEEN


def record_seen(name: str) -> None:
    _LAST_SEEN[name] = time.monotonic()


class AuthGateMiddleware:
    """Admit a valid cookie or a valid bearer token; reject everything else."""

    def __init__(
        self,
        app,
        *,
        cache: RosterCache,
        secret: bytes,
        workspace_root: str = "",
    ) -> None:
        self.app = app
        self._cache = cache
        self._secret = secret
        self._workspace_root = str(Path(workspace_root).resolve()) if workspace_root else ""

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return

        roster = self._cache.roster()
        if not roster.enabled:
            await self.app(scope, receive, send)
            return

        if scope.get("path", "") in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        principal = self._resolve_principal(scope, roster)
        if principal is None:
            await self._reject(scope, send)
            return

        scope[PRINCIPAL_SCOPE_KEY] = principal
        record_seen(principal)
        await self.app(scope, receive, send)

    # -- credential resolution ------------------------------------------

    def _resolve_principal(self, scope, roster) -> str | None:
        token = self._bearer_token(scope)
        if token:
            agent = roster.find_by_token(token)
            if agent is not None and self._workspace_allows(agent):
                return agent.name
            logger.warning("Rejecting unknown or out-of-scope bearer token from %s", scope.get("client"))

        raw = self._cookie(scope, COOKIE_NAME)
        if not raw:
            # A bad bearer token with no cookie to fall back to is a hard
            # reject — an explicit-but-wrong credential must not be treated
            # as "no credential offered".
            return None

        name = verify_session(raw, secret=self._secret)
        if name is None:
            return None

        # The cookie proves identity. The roster is authority: a principal
        # removed since the cookie was issued is refused here, which is what
        # makes "remove" an actual revocation.
        if roster.find(name) is None:
            logger.warning("Rejecting cookie for unknown principal %r", name)
            return None
        return name

    def _workspace_allows(self, agent) -> bool:
        """An agent with no ``workspace`` works anywhere; a scoped one only at home."""
        if not agent.workspace or not self._workspace_root:
            return not agent.workspace
        return str(Path(agent.workspace).resolve()) == self._workspace_root

    @staticmethod
    def _header(scope, name: bytes) -> str:
        for key, value in scope.get("headers", []):
            if key == name:
                return value.decode("latin-1")
        return ""

    @staticmethod
    def _cookie_header(scope) -> str:
        """Join every ``cookie`` header line, not just the first.

        HTTP/2 explicitly permits the Cookie field to arrive split across
        multiple header lines (RFC 9113 §8.2.3), and some proxies do the
        same; a single-header read would silently drop the session cookie
        whenever a second ``cookie`` header happens to precede it.
        """
        parts = [value.decode("latin-1") for key, value in scope.get("headers", []) if key == b"cookie"]
        return "; ".join(parts)

    def _bearer_token(self, scope) -> str:
        auth = self._header(scope, b"authorization")
        prefix = "Bearer "
        return auth[len(prefix) :].strip() if auth.startswith(prefix) else ""

    def _cookie(self, scope, name: str) -> str:
        raw = self._cookie_header(scope)
        for part in raw.split(";"):
            key, _, value = part.strip().partition("=")
            if key == name:
                return value
        return ""

    # -- rejection ------------------------------------------------------

    async def _reject(self, scope, send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return

        # A browser navigating to a page should land on the login form; anything
        # else (fetch, curl, an MCP client) gets a machine-readable 401 rather
        # than an HTML redirect it cannot follow usefully.
        accept = self._header(scope, b"accept")
        if scope.get("method") == "GET" and "text/html" in accept:
            await send(
                {
                    "type": "http.response.start",
                    "status": 303,
                    "headers": [(b"location", b"/login"), (b"content-length", b"0")],
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return

        body = json.dumps({"error": "unauthorized"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
