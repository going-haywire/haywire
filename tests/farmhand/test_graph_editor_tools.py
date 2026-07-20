"""graph_editor_* tools over the real MCP server; includes the one-call-one-undo-fence contract."""

import pytest

from tests.farmhand.conftest import call_tool_json

pytestmark = pytest.mark.integration

NODE_KEY = "example:node:MathOP"  # a registered node with FLOAT data inlets


@pytest.fixture(autouse=True)
def _restore_new_counter():
    """haystack_create_graph increments the persistent HaystackSettings.new_counter
    on the ambient registry; restore it so settings tests keep their default."""
    from haybale_haystack.settings.haystack_settings import HaystackSettings

    before = HaystackSettings().new_counter
    yield
    HaystackSettings().new_counter = before


def _call(farmhand_call, tool: str, args: dict):
    async def scenario(session, init):
        return await session.call_tool(tool, args)

    return farmhand_call(scenario)


def _new_graph(farmhand_call) -> str:
    return call_tool_json(_call(farmhand_call, "haystack_create_graph", {}))["binding_id"]


def _close(farmhand_call, bid) -> None:
    _call(farmhand_call, "haystack_close_graph", {"binding_id": bid})


def test_add_query_remove(farmhand_call):
    bid = _new_graph(farmhand_call)
    try:
        node_id = call_tool_json(
            _call(farmhand_call, "graph_editor_add_node", {"binding_id": bid, "registry_key": NODE_KEY})
        )["node_id"]
        query = call_tool_json(_call(farmhand_call, "graph_editor_query_graph", {"binding_id": bid}))
        assert any(n["node_id"] == node_id for n in query["nodes"])
        assert query["total"] == 1
        _call(farmhand_call, "graph_editor_remove_elements", {"binding_id": bid, "nodes": [node_id]})
        after = call_tool_json(_call(farmhand_call, "graph_editor_query_graph", {"binding_id": bid}))
        assert after["total"] == 0
    finally:
        _close(farmhand_call, bid)


def test_one_tool_call_is_one_undo_gesture(farmhand_call):
    bid = _new_graph(farmhand_call)
    try:
        _call(farmhand_call, "graph_editor_add_node", {"binding_id": bid, "registry_key": NODE_KEY})
        _call(farmhand_call, "graph_editor_add_node", {"binding_id": bid, "registry_key": NODE_KEY})
        assert (
            call_tool_json(_call(farmhand_call, "graph_editor_query_graph", {"binding_id": bid}))["total"]
            == 2
        )
        undo = call_tool_json(_call(farmhand_call, "graph_editor_undo", {"binding_id": bid}))
        assert undo["performed"] is True
        # exactly ONE call reverted, not both:
        assert (
            call_tool_json(_call(farmhand_call, "graph_editor_query_graph", {"binding_id": bid}))["total"]
            == 1
        )
    finally:
        _close(farmhand_call, bid)


def test_set_property_and_undo(farmhand_call):
    bid = _new_graph(farmhand_call)
    try:
        node_id = call_tool_json(
            _call(farmhand_call, "graph_editor_add_node", {"binding_id": bid, "registry_key": NODE_KEY})
        )["node_id"]
        node = next(
            n
            for n in call_tool_json(_call(farmhand_call, "graph_editor_query_graph", {"binding_id": bid}))[
                "nodes"
            ]
            if n["node_id"] == node_id
        )
        inlet = next(p["id"] for p in node["ports"] if p["direction"] == "inlet")
        _call(
            farmhand_call,
            "graph_editor_set_property",
            {"binding_id": bid, "node_id": node_id, "name": inlet, "value": 7.0},
        )
        undo = call_tool_json(_call(farmhand_call, "graph_editor_undo", {"binding_id": bid}))
        assert undo["performed"] is True
    finally:
        _close(farmhand_call, bid)


def test_connect_failure_is_stable_error(farmhand_call):
    bid = _new_graph(farmhand_call)
    try:
        result = _call(
            farmhand_call,
            "graph_editor_connect",
            {
                "binding_id": bid,
                "source_node_id": "ghost",
                "outlet": "out",
                "sink_node_id": "ghost2",
                "inlet": "in",
            },
        )
        assert result.isError is True
        # Ghost endpoints are caught by the up-front node check.
        assert "[node_not_found]" in result.content[0].text
    finally:
        _close(farmhand_call, bid)


def test_connect_bad_pin_is_connect_failed(farmhand_call):
    bid = _new_graph(farmhand_call)
    try:
        a = call_tool_json(
            _call(farmhand_call, "graph_editor_add_node", {"binding_id": bid, "registry_key": NODE_KEY})
        )["node_id"]
        b = call_tool_json(
            _call(farmhand_call, "graph_editor_add_node", {"binding_id": bid, "registry_key": NODE_KEY})
        )["node_id"]
        result = _call(
            farmhand_call,
            "graph_editor_connect",
            {
                "binding_id": bid,
                "source_node_id": a,
                "outlet": "no_such_outlet",
                "sink_node_id": b,
                "inlet": "no_such_inlet",
            },
        )
        assert result.isError is True
        assert "[connect_failed]" in result.content[0].text
    finally:
        _close(farmhand_call, bid)


def test_unknown_graph_is_stable_error(farmhand_call):
    result = _call(farmhand_call, "graph_editor_query_graph", {"binding_id": "__nope__"})
    assert result.isError is True
    assert "[graph_not_found]" in result.content[0].text
