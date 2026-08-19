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
        return await session.call_tool("haybale-testing_echo", {"text": "hi"})

    result = farmhand_call(scenario)
    payload = call_tool_json(result)
    assert payload["echo"] == "hi"
    assert "summary" in payload


def test_tool_result_carries_structured_content_alongside_text(farmhand_call):
    """Both halves of the MCP result are populated: text for text-only clients,
    structuredContent so a structure-aware one skips the string parse."""

    async def scenario(session, init):
        return await session.call_tool("haybale-testing_echo", {"text": "hi"})

    result = farmhand_call(scenario)
    assert result.structuredContent is not None
    assert result.structuredContent["echo"] == "hi"
    # The two halves must not disagree.
    assert result.structuredContent == call_tool_json(result)


def test_error_contract_stable_code_no_traceback(farmhand_call):
    async def scenario(session, init):
        return await session.call_tool("haybale-testing_fail", {})

    result = farmhand_call(scenario)
    assert result.isError is True
    text = result.content[0].text
    assert "[testing_failure]" in text
    assert "tool=fail" in text
    assert "Traceback" not in text


def test_mutating_tool_runs_on_event_loop(farmhand_call):
    async def scenario(session, init):
        return await session.call_tool("haybale-testing_affinity", {})

    payload = call_tool_json(farmhand_call(scenario))
    assert payload["on_event_loop"] is True


def test_blocking_tool_does_not_stall_concurrent_request(farmhand_call):
    async def scenario(session, init):
        started = time.monotonic()

        async def timed_echo():
            await session.call_tool("haybale-testing_echo", {"text": "quick"})
            return time.monotonic() - started

        block = asyncio.create_task(session.call_tool("haybale-testing_block", {"seconds": 1.5}))
        echo_elapsed = await timed_echo()
        await block
        return echo_elapsed

    assert farmhand_call(scenario) < 1.0  # echo finished while block still sleeping


def test_disable_enable_shrinks_and_grows_tool_list(farmhand_server, farmhand_call):
    from haywire.core.library.registry import LibraryRegistry

    registry = farmhand_server.service.injector.get(LibraryRegistry)

    async def scenario(session, init):
        names = {t.name for t in (await session.list_tools()).tools}
        assert "haybale-testing_echo" in names
        registry.disable_library("haybale-testing")
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                names = {t.name for t in (await session.list_tools()).tools}
                if "haybale-testing_echo" not in names:
                    break
                await asyncio.sleep(0.1)
            assert "haybale-testing_echo" not in names
        finally:
            registry.enable_library("haybale-testing")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            names = {t.name for t in (await session.list_tools()).tools}
            if "haybale-testing_echo" in names:
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


def test_disallowed_origin_rejected(farmhand_server):
    status = _post(
        farmhand_server.base_url,
        {"Origin": "http://evil.example"},
    )
    assert status in (400, 403, 421)


def test_mount_writes_no_token_file(farmhand_server):
    """ADR 0028: /mcp carries no credential of its own."""
    from pathlib import Path

    workspace = Path(farmhand_server.host._workspace_root)
    assert not (workspace / ".haywire" / "farmhand_token").exists()


# ---------------------------------------------------------------------------
# Activity tracking (the presence row's "what is that agent doing?" source)
# ---------------------------------------------------------------------------


def test_successful_tool_call_is_recorded_as_finished_activity(farmhand_call):
    """The host records every call, not just mutating ones — echo is read-only."""
    from haywire_studio.farmhand.activity import activity_tracker

    activity_tracker().clear()

    async def scenario(session, init):
        return await session.call_tool("haybale-testing_echo", {"text": "hi"})

    farmhand_call(scenario)

    recent = activity_tracker().recent()
    assert [r.tool for r in recent] == ["haybale-testing_echo"]
    assert recent[0].ok is True
    assert recent[0].running is False
    # Auth is off in this harness, so the principal is None — the same value a
    # browser session's context.principal carries, resolving to ADMIN.
    assert recent[0].principal is None


def test_failing_tool_call_is_recorded_with_its_error(farmhand_call):
    from haywire_studio.farmhand.activity import activity_tracker

    activity_tracker().clear()

    async def scenario(session, init):
        return await session.call_tool("haybale-testing_fail", {})

    farmhand_call(scenario)

    recent = activity_tracker().recent()
    assert [r.tool for r in recent] == ["haybale-testing_fail"]
    assert recent[0].ok is False
    assert "[testing_failure]" in (recent[0].error or "")


def test_no_call_is_left_pinned_as_running(farmhand_call):
    """Both outcomes must clear the in-flight set, or the chip lies forever."""
    from haywire_studio.farmhand.activity import activity_tracker

    activity_tracker().clear()

    async def scenario(session, init):
        await session.call_tool("haybale-testing_echo", {"text": "hi"})
        return await session.call_tool("haybale-testing_fail", {})

    farmhand_call(scenario)

    assert activity_tracker().current(None) is None
    assert len(activity_tracker().recent()) == 2


def test_a_real_call_records_its_arguments_and_result(farmhand_call):
    """End-to-end through host.py's real call_tool wrapper, not a direct tracker call."""
    import json

    from haywire_studio.farmhand.activity import activity_tracker

    activity_tracker().clear()

    async def scenario(session, init):
        return await session.call_tool("haybale-testing_echo", {"text": "roundtrip"})

    farmhand_call(scenario)

    record = activity_tracker().recent()[0]
    assert json.loads(record.arguments) == {"text": "roundtrip"}
    assert record.result is not None
    assert json.loads(record.result)["echo"] == "roundtrip"
