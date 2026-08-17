"""How an agent connects to the Farmhand mount.

**There is no separate MCP credential.** `/mcp` is mounted inside the studio's
own ASGI app, so ``AuthGateMiddleware`` (ADR 0027) already demands a roster
bearer token on every request when authentication is on. When it is off, the
security document's invariants guarantee the studio is loopback-only — so the
matrix is closed: no configuration exists in which `/mcp` is reachable from
another machine without a token.

The workspace token file this module used to mint (`<ws>/.haywire/farmhand_token`)
is gone with ADR 0028. It was a second credential with a second lifetime,
guarding an endpoint the bind address already guarded, and its existence made
"is /mcp protected?" a question with two answers.
"""

from __future__ import annotations


def connection_command(port: int, token: str | None, *, tls: bool = False) -> str:
    """The ``claude mcp add`` line for this studio.

    *token* is a roster agent's token, or ``None`` when authentication is off
    and no header is needed. The scheme follows actual TLS, because a client
    told ``http://`` against an HTTPS studio fails in a way that looks like the
    server is down.
    """
    scheme = "https" if tls else "http"
    base = f"claude mcp add --transport http farmhand {scheme}://127.0.0.1:{port}/mcp"
    if token is None:
        return base
    return f'{base} --header "Authorization: Bearer {token}"'
