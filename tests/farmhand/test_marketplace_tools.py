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
    result = call_tool_json(
        _call(farmhand_call, "haybale-marketplace_list_available", {"limit": 10, "offset": 0})
    )
    assert "total" in result
    assert "haybales" in result


def test_get_library_docs_for_installed_library(farmhand_call):
    # haybale-marketplace itself is installed in the barn; any doc file counts.
    result = _call(farmhand_call, "haybale-marketplace_get_library_docs", {"library": "haybale-testing"})
    if result.isError:
        # acceptable if the test lib ships no docs
        assert "[docs_not_found]" in result.content[0].text
    else:
        payload = call_tool_json(result)
        assert payload["source"] == "installed"
        assert payload["text"]


def test_get_library_docs_unknown_library_is_stable_error(farmhand_call):
    result = _call(farmhand_call, "haybale-marketplace_get_library_docs", {"library": "does_not_exist"})
    assert result.isError is True
    assert "[library_not_found]" in result.content[0].text
    # The error carries the command that resolves it, not just the failure.
    assert "help:" in result.content[0].text


@pytest.mark.unit
def test_doc_result_truncates_long_text_and_reports_the_real_size():
    from haybale_marketplace.farmhands.catalog_tools import _DOC_CHAR_CAP, _doc_result

    long_text = "x" * (_DOC_CHAR_CAP + 500)
    payload = _doc_result("lib: README.", long_text, full=False)
    assert len(payload["text"]) == _DOC_CHAR_CAP
    assert payload["total_chars"] == _DOC_CHAR_CAP + 500
    assert payload["truncated"] is True
    assert "full=true" in payload["help"]

    whole = _doc_result("lib: README.", long_text, full=True)
    assert whole["text"] == long_text
    assert "truncated" not in whole


@pytest.mark.unit
def test_doc_result_leaves_short_text_untouched():
    from haybale_marketplace.farmhands.catalog_tools import _doc_result

    payload = _doc_result("lib: README.", "short", full=False)
    assert payload["text"] == "short"
    assert payload["total_chars"] == 5
    # Nothing hidden -> no truncation markers to mislead the caller.
    assert "truncated" not in payload
    assert "help" not in payload
