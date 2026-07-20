"""Offline-testable marketplace tools over the real MCP server.

Network/destructive tools (refresh, dry_run, install, uninstall) run uv/urllib
and are exercised manually, not in CI. Only the offline catalog/docs rows are
covered here.
"""

import pytest

from tests.farmhand.conftest import call_tool_json

pytestmark = pytest.mark.integration


def _call(farmhand_call, tool: str, args: dict):
    async def scenario(session, init):
        return await session.call_tool(tool, args)

    return farmhand_call(scenario)


def test_list_available_returns_paginated_catalog(farmhand_call):
    result = call_tool_json(_call(farmhand_call, "marketplace_list_available", {"limit": 10, "offset": 0}))
    assert "total" in result and "haybales" in result  # may be empty in a test workspace


def test_get_library_docs_for_installed_library(farmhand_call):
    # haybale-marketplace itself is installed in the barn; any doc file counts.
    result = _call(farmhand_call, "marketplace_get_library_docs", {"library": "testing"})
    if result.isError:
        # acceptable if the test lib ships no docs
        assert "[docs_not_found]" in result.content[0].text
    else:
        payload = call_tool_json(result)
        assert payload["source"] == "installed"
        assert payload["text"]


def test_get_library_docs_unknown_library_is_stable_error(farmhand_call):
    result = _call(farmhand_call, "marketplace_get_library_docs", {"library": "does_not_exist"})
    assert result.isError is True
    assert "[library_not_found]" in result.content[0].text
