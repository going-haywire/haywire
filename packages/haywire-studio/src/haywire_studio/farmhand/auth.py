"""Static bearer-token auth for the Farmhand mount.

Token lives gitignored at <workspace>/.haywire/farmhand_token; delete the
file to rotate. Layered with NetworkSettings.expose_to_network (loopback
bind by default) and the SDK's TransportSecuritySettings, gated by
FarmhandSettings.restrict_to_loopback (host task) per spec §4.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

TOKEN_FILENAME = "farmhand_token"


def ensure_token(workspace_root: Path) -> str:
    haywire_dir = Path(workspace_root) / ".haywire"
    haywire_dir.mkdir(parents=True, exist_ok=True)

    gitignore = haywire_dir / ".gitignore"
    if not gitignore.exists() or TOKEN_FILENAME not in gitignore.read_text(encoding="utf-8"):
        with gitignore.open("a", encoding="utf-8") as fh:
            fh.write(f"{TOKEN_FILENAME}\n")

    token_file = haywire_dir / TOKEN_FILENAME
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(32)
    token_file.write_text(token, encoding="utf-8")
    token_file.chmod(0o600)
    return token


def connection_command(port: int, token: str | None) -> str:
    base = f"claude mcp add --transport http farmhand http://127.0.0.1:{port}/mcp"
    if token is None:
        return base
    return f'{base} --header "Authorization: Bearer {token}"'


class BearerTokenMiddleware:
    """Pure-ASGI bearer check wrapping the Farmhand mount only."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        auth = ""
        for key, value in scope.get("headers", []):
            if key == b"authorization":
                auth = value.decode("latin-1")
                break
        if auth != f"Bearer {self.token}":
            body = json.dumps({"error": "unauthorized"}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)
