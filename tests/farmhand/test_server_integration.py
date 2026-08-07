"""Served-app integration: capabilities, round-trip, errors, list_changed, affinity, offload, auth."""

import asyncio
import json
import time
import urllib.error
import urllib.request

import pytest

from tests.farmhand.conftest import call_tool_json

pytestmark = pytest.mark.integration


def test_initialize_advertises_list_changed(farmhand_call):
    async def scenario(session, init):
        return init

    init = farmhand_call(scenario)
    assert init.capabilities.tools.listChanged is True


def test_tool_round_trip_structured_json(farmhand_call):
    async def scenario(session, init):
        return await session.call_tool("testing_echo", {"text": "hi"})

    result = farmhand_call(scenario)
    payload = call_tool_json(result)
    assert payload["echo"] == "hi"
    assert "summary" in payload


def test_tool_result_carries_structured_content_alongside_text(farmhand_call):
    """Both halves of the MCP result are populated: text for text-only clients,
    structuredContent so a structure-aware one skips the string parse."""

    async def scenario(session, init):
        return await session.call_tool("testing_echo", {"text": "hi"})

    result = farmhand_call(scenario)
    assert result.structuredContent is not None
    assert result.structuredContent["echo"] == "hi"
    # The two halves must not disagree.
    assert result.structuredContent == call_tool_json(result)


def test_error_contract_stable_code_no_traceback(farmhand_call):
    async def scenario(session, init):
        return await session.call_tool("testing_fail", {})

    result = farmhand_call(scenario)
    assert result.isError is True
    text = result.content[0].text
    assert "[testing_failure]" in text
    assert "tool=fail" in text
    assert "Traceback" not in text


def test_mutating_tool_runs_on_event_loop(farmhand_call):
    async def scenario(session, init):
        return await session.call_tool("testing_affinity", {})

    payload = call_tool_json(farmhand_call(scenario))
    assert payload["on_event_loop"] is True


def test_blocking_tool_does_not_stall_concurrent_request(farmhand_call):
    async def scenario(session, init):
        started = time.monotonic()

        async def timed_echo():
            await session.call_tool("testing_echo", {"text": "quick"})
            return time.monotonic() - started

        block = asyncio.create_task(session.call_tool("testing_block", {"seconds": 1.5}))
        echo_elapsed = await timed_echo()
        await block
        return echo_elapsed

    assert farmhand_call(scenario) < 1.0  # echo finished while block still sleeping


def test_disable_enable_shrinks_and_grows_tool_list(farmhand_server, farmhand_call):
    from haywire.core.library.registry import LibraryRegistry

    registry = farmhand_server.service.injector.get(LibraryRegistry)

    async def scenario(session, init):
        names = {t.name for t in (await session.list_tools()).tools}
        assert "testing_echo" in names
        registry.disable_library("testing")
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                names = {t.name for t in (await session.list_tools()).tools}
                if "testing_echo" not in names:
                    break
                await asyncio.sleep(0.1)
            assert "testing_echo" not in names
        finally:
            registry.enable_library("testing")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            names = {t.name for t in (await session.list_tools()).tools}
            if "testing_echo" in names:
                return True
            await asyncio.sleep(0.1)
        return False

    assert farmhand_call(scenario) is True


def _post(url: str, headers: dict) -> int:
    # POST /mcp 307-redirects to /mcp/ (Starlette Mount) BEFORE the ASGI sub-app's
    # bearer/security layer runs; the real MCP client follows that redirect
    # transparently. urllib does not re-issue POST on a 307, so probe the resolved
    # path directly — that is where auth and origin checks actually execute.
    if not url.endswith("/"):
        url = url + "/"
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def _assert_auth_required():
    from haywire_studio.farmhand.settings import FarmhandSettings

    assert FarmhandSettings().require_auth is True, (
        "these tests assert 401 on missing/wrong token, which only holds when "
        "FarmhandSettings.require_auth is True — check the schema default and "
        "that nothing upstream flipped it"
    )


def test_missing_token_is_401(farmhand_server):
    _assert_auth_required()
    assert _post(farmhand_server.base_url, {}) == 401


def test_wrong_token_is_401(farmhand_server):
    _assert_auth_required()
    assert _post(farmhand_server.base_url, {"Authorization": "Bearer wrong"}) == 401


def test_disallowed_origin_rejected(farmhand_server):
    status = _post(
        farmhand_server.base_url,
        {"Authorization": f"Bearer {farmhand_server.token}", "Origin": "http://evil.example"},
    )
    assert status in (400, 403, 421)


def test_token_file_created_gitignored_on_first_start(farmhand_server):
    """ensure_token ran during server mount against the session workspace."""
    from pathlib import Path

    from haywire_studio.farmhand.auth import TOKEN_FILENAME

    workspace = Path(farmhand_server.host._workspace_root)
    assert (workspace / ".haywire" / TOKEN_FILENAME).exists()
    assert TOKEN_FILENAME in (workspace / ".haywire" / ".gitignore").read_text()
