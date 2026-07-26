"""Token file lifecycle and bearer middleware (no server needed)."""

import asyncio

import pytest

from haywire_studio.farmhand.auth import BearerTokenMiddleware, connection_command, ensure_token

pytestmark = pytest.mark.unit


def test_token_created_stable_and_gitignored(tmp_path):
    token = ensure_token(tmp_path)
    assert len(token) >= 32
    token_file = tmp_path / ".haywire" / "farmhand_token"
    assert token_file.exists()
    assert ensure_token(tmp_path) == token  # stable across calls
    gitignore = (tmp_path / ".haywire" / ".gitignore").read_text()
    assert "farmhand_token" in gitignore


def test_token_rotates_when_file_deleted(tmp_path):
    first = ensure_token(tmp_path)
    (tmp_path / ".haywire" / "farmhand_token").unlink()
    assert ensure_token(tmp_path) != first


def test_connection_command_contains_endpoint_and_header():
    line = connection_command(8082, "sekrit")
    assert "claude mcp add --transport http farmhand http://127.0.0.1:8082/mcp" in line
    assert "Authorization: Bearer sekrit" in line


def test_connection_command_omits_header_when_token_is_none():
    line = connection_command(8082, None)
    assert "claude mcp add --transport http farmhand http://127.0.0.1:8082/mcp" in line
    assert "Authorization" not in line


def _run_middleware(headers: list[tuple[bytes, bytes]]) -> int:
    """Drive the ASGI middleware with a fake downstream app; return the status sent."""
    sent: dict = {}

    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def send(message):
        if message["type"] == "http.response.start":
            sent["status"] = message["status"]

    async def receive():
        return {"type": "http.request"}

    middleware = BearerTokenMiddleware(downstream, token="sekrit")
    scope = {"type": "http", "headers": headers, "path": "/mcp"}
    asyncio.run(middleware(scope, receive, send))
    return sent["status"]


def test_missing_token_is_401():
    assert _run_middleware([]) == 401


def test_wrong_token_is_401():
    assert _run_middleware([(b"authorization", b"Bearer wrong")]) == 401


def test_correct_token_passes_through():
    assert _run_middleware([(b"authorization", b"Bearer sekrit")]) == 200
