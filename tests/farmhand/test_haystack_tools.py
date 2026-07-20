"""haystack_* tools over the real MCP server.

Driven through the served app rather than by direct instantiation: the server
harness sets the ambient workspace_root BEFORE the library system initializes,
so HaystackState.on_enable resolves its deps (node factory, graph registry) —
the ordering a direct-call test can't reproduce because library_system enables
its AppStates once at session scope.
"""

import pytest

from tests.farmhand.conftest import call_tool_json

pytestmark = pytest.mark.integration


def _call(farmhand_call, tool: str, args: dict):
    async def scenario(session, init):
        return await session.call_tool(tool, args)

    return farmhand_call(scenario)


def _created_then_closed(farmhand_call):
    created = call_tool_json(_call(farmhand_call, "haystack_create_graph", {}))
    return created["binding_id"]


def test_create_list_close_round_trip(farmhand_call):
    bid = _created_then_closed(farmhand_call)
    try:
        listing = call_tool_json(_call(farmhand_call, "haystack_list_graphs", {}))
        assert any(row["binding_id"] == bid for row in listing["open"])
    finally:
        _call(farmhand_call, "haystack_close_graph", {"binding_id": bid})


def test_compile_start_stop_empty_graph(farmhand_call):
    bid = _created_then_closed(farmhand_call)
    try:
        compiled = call_tool_json(_call(farmhand_call, "haystack_compile_graph", {"binding_id": bid}))
        assert "compile" in compiled
        _call(farmhand_call, "haystack_start_graph", {"binding_id": bid})
        _call(farmhand_call, "haystack_stop_graph", {"binding_id": bid})
    finally:
        _call(farmhand_call, "haystack_close_graph", {"binding_id": bid})


def test_save_and_reopen(farmhand_call):
    bid = _created_then_closed(farmhand_call)
    try:
        result = call_tool_json(
            _call(
                farmhand_call,
                "haystack_save_graph",
                {"binding_id": bid, "save_as": "graphs/farmhand_t12.haywire"},
            )
        )
        assert result["path"] and result["unsaved"] is False
    finally:
        # bid changed to the saved path after save-as; close whatever is open.
        listing = call_tool_json(_call(farmhand_call, "haystack_list_graphs", {}))
        for row in listing["open"]:
            _call(farmhand_call, "haystack_close_graph", {"binding_id": row["binding_id"]})


def test_unknown_binding_id_is_stable_error(farmhand_call):
    result = _call(farmhand_call, "haystack_compile_graph", {"binding_id": "__nope__"})
    assert result.isError is True
    assert "[graph_not_found]" in result.content[0].text
