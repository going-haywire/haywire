"""The Farmhand connection command. There is no separate MCP token any more."""

from __future__ import annotations

from haywire_studio.farmhand.auth import connection_command


def test_connection_command_contains_endpoint_and_header():
    line = connection_command(8124, "sekrit")
    assert "http://127.0.0.1:8124/mcp" in line
    assert "Authorization: Bearer sekrit" in line


def test_connection_command_omits_header_when_token_is_none():
    line = connection_command(8124, None)
    assert "Authorization" not in line
    assert "http://127.0.0.1:8124/mcp" in line


def test_connection_command_uses_https_under_tls():
    line = connection_command(8124, None, tls=True)
    assert "https://127.0.0.1:8124/mcp" in line
