"""graph_editor_* tools over the real MCP server; includes the one-call-one-undo-fence contract."""

import pytest

from tests.farmhand.conftest import call_tool_json

pytestmark = pytest.mark.integration

NODE_KEY = "example:node:MathOP"  # a registered node with FLOAT data inlets
CALLBACK_NODE_KEY = "testing:node:EdgeLinkTestNode"  # has callback_outlet + callback_inlet


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


def test_query_detail_adds_port_setup_fields(farmhand_call):
    """detail=true enriches each port with its setup; default stays 3-field."""
    bid = _new_graph(farmhand_call)
    try:
        node_id = call_tool_json(
            _call(farmhand_call, "graph_editor_add_node", {"binding_id": bid, "registry_key": NODE_KEY})
        )["node_id"]

        # Default call: only the three base fields, no detail keys leaked.
        plain = call_tool_json(_call(farmhand_call, "graph_editor_query_graph", {"binding_id": bid}))
        plain_node = next(n for n in plain["nodes"] if n["node_id"] == node_id)
        for port in plain_node["ports"]:
            assert set(port) == {"id", "direction", "flow_type"}

        # detail=true: the tier-1/2 setup fields are present and typed sensibly.
        detailed = call_tool_json(
            _call(farmhand_call, "graph_editor_query_graph", {"binding_id": bid, "detail": True})
        )
        node = next(n for n in detailed["nodes"] if n["node_id"] == node_id)
        detail_keys = {
            "data_type",
            "allow_multiple_links",
            "is_linked",
            "link_count",
            "use_mode",
            "promoted",
            "has_widget",
            "is_linked_lazy",
        }
        inlet = next(p for p in node["ports"] if p["direction"] == "inlet")
        assert detail_keys <= set(inlet)
        # A freshly added node has no edges: nothing linked anywhere.
        assert inlet["is_linked"] is False
        assert inlet["link_count"] == 0
        assert inlet["promoted"] is False
        # A concrete data type resolves to a registry key (not None) on data ports.
        data_port = next(p for p in node["ports"] if p["flow_type"] == "data")
        assert isinstance(data_port["data_type"], str) and ":" in data_port["data_type"]
    finally:
        _close(farmhand_call, bid)


def test_query_labels_callback_ports_and_edges(farmhand_call):
    """Callback ports carry flow_type='callback'; the edge between them is self-labeled."""
    bid = _new_graph(farmhand_call)
    try:
        src = call_tool_json(
            _call(
                farmhand_call,
                "graph_editor_add_node",
                {"binding_id": bid, "registry_key": CALLBACK_NODE_KEY},
            )
        )["node_id"]
        sink = call_tool_json(
            _call(
                farmhand_call,
                "graph_editor_add_node",
                {"binding_id": bid, "registry_key": CALLBACK_NODE_KEY},
            )
        )["node_id"]
        _call(
            farmhand_call,
            "graph_editor_connect",
            {
                "binding_id": bid,
                "source_node_id": src,
                "outlet": "callback_outlet",
                "sink_node_id": sink,
                "inlet": "callback_inlet",
            },
        )

        graph = call_tool_json(_call(farmhand_call, "graph_editor_query_graph", {"binding_id": bid}))

        # The edge is self-labeled — no port join needed to classify it.
        cb_edges = [e for e in graph["edges"] if e["flow_type"] == "callback"]
        assert len(cb_edges) == 1
        assert cb_edges[0]["outlet"] == "callback_outlet"
        assert cb_edges[0]["inlet"] == "callback_inlet"

        # And the ports themselves report flow_type='callback'.
        src_node = next(n for n in graph["nodes"] if n["node_id"] == src)
        outlet = next(p for p in src_node["ports"] if p["id"] == "callback_outlet")
        assert outlet["flow_type"] == "callback"
    finally:
        _close(farmhand_call, bid)


def test_query_edge_detail_reports_health_and_adapter_chain(farmhand_call):
    """detail=true enriches edges with health + the built adapter chain.

    Connecting TEST_BOOL -> TEST_FLOAT forces a two-hop coercion, so the edge's
    adapter_chain is the ordered list of the adapters the framework inserted.
    """
    bid = _new_graph(farmhand_call)
    try:
        a = call_tool_json(
            _call(
                farmhand_call,
                "graph_editor_add_node",
                {"binding_id": bid, "registry_key": CALLBACK_NODE_KEY},
            )
        )["node_id"]
        b = call_tool_json(
            _call(
                farmhand_call,
                "graph_editor_add_node",
                {"binding_id": bid, "registry_key": CALLBACK_NODE_KEY},
            )
        )["node_id"]
        # bool_outlet (TEST_BOOL) -> float_inlet (TEST_FLOAT): needs BoolToInt + IntToFloat.
        _call(
            farmhand_call,
            "graph_editor_connect",
            {
                "binding_id": bid,
                "source_node_id": a,
                "outlet": "bool_outlet",
                "sink_node_id": b,
                "inlet": "float_inlet",
            },
        )

        # Default edges: no detail keys.
        plain = call_tool_json(_call(farmhand_call, "graph_editor_query_graph", {"binding_id": bid}))
        assert set(plain["edges"][0]) == {
            "edge_id",
            "source_node",
            "outlet",
            "sink_node",
            "inlet",
            "flow_type",
        }

        detailed = call_tool_json(
            _call(farmhand_call, "graph_editor_query_graph", {"binding_id": bid, "detail": True})
        )
        edge = detailed["edges"][0]
        assert edge["is_functional"] is True
        assert edge["is_linked"] is True
        assert edge["error"] is None
        assert edge["has_adapters"] is True
        assert edge["adapter_chain"] == [
            "testing:adapter:BoolToIntAdapter",
            "testing:adapter:IntToFloatAdapter",
        ]
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


# ---------------------------------------------------------------------------
# graph_editor_inspect_node
# ---------------------------------------------------------------------------

SETTINGS_NODE_KEY = "testing:node:SettingsNode"  # exercises every setting() flavour


def _inspect(farmhand_call, bid, node_id, get):
    return call_tool_json(
        _call(
            farmhand_call,
            "graph_editor_inspect_node",
            {"binding_id": bid, "node_id": node_id, "get": get},
        )
    )


def _add(farmhand_call, bid, key=SETTINGS_NODE_KEY) -> str:
    return call_tool_json(
        _call(farmhand_call, "graph_editor_add_node", {"binding_id": bid, "registry_key": key})
    )["node_id"]


def test_inspect_summary_only_returns_no_sections(farmhand_call):
    """get=['summary'] is the cheap survey: a summary, and no row payload at all."""
    bid = _new_graph(farmhand_call)
    try:
        node_id = _add(farmhand_call, bid)
        result = _inspect(farmhand_call, bid, node_id, ["summary"])
        assert "summary" in result
        assert SETTINGS_NODE_KEY in result["summary"]
        # None of the row sections leak into a summary-only call.
        for section in ("ports", "settings", "props", "state"):
            assert section not in result
    finally:
        _close(farmhand_call, bid)


def test_inspect_summary_always_present(farmhand_call):
    """The canon requires a summary on every result — even when not named in get."""
    bid = _new_graph(farmhand_call)
    try:
        node_id = _add(farmhand_call, bid)
        result = _inspect(farmhand_call, bid, node_id, ["ports"])
        assert result["summary"]
        assert "ports" in result
    finally:
        _close(farmhand_call, bid)


def test_inspect_settings_excludes_props(farmhand_call):
    """props IS a settings bag, so it must be filtered out of the settings section."""
    bid = _new_graph(farmhand_call)
    try:
        node_id = _add(farmhand_call, bid)
        result = _inspect(farmhand_call, bid, node_id, ["settings", "props"])
        assert {r["accessor"] for r in result["settings"]} == {"example"}
        assert {r["accessor"] for r in result["props"]} == {"props"}
    finally:
        _close(farmhand_call, bid)


def test_inspect_setting_row_carries_value_opinion_and_constraints(farmhand_call):
    """A settings row is directly actionable: value + is_set + default + constraints."""
    bid = _new_graph(farmhand_call)
    try:
        node_id = _add(farmhand_call, bid)
        rows = {r["name"]: r for r in _inspect(farmhand_call, bid, node_id, ["settings"])["settings"]}

        num = rows["example_int"]
        assert num["kind"] == "setting"
        assert num["accessor"] == "example"  # the promote_setting handle
        assert num["type"] == "INT"
        assert num["value"] == 3
        assert num["is_set"] is False  # inheriting, not overridden
        assert num["default"] == 3
        assert num["min"] == 0 and num["max"] == 100

        # CHOICES exposes its valid set — the agent cannot guess these.
        assert rows["example_choices"]["options"] == ["fast", "balanced", "quality"]

        # Vec types are list subclasses: native JSON, no lossy str() fallback.
        assert rows["example_vec3f"]["value"] == [1.0, 2.0, 3.0]

        # watch() seeds ui_state=DISABLED; shadow() does not.
        assert rows["intensity_ro"]["ui_state"] == "disabled"
        assert "ui_state" not in rows["intensity"]
        assert rows["intensity"]["mirrors"]
    finally:
        _close(farmhand_call, bid)


def test_inspect_port_row_reports_value_and_link_state(farmhand_call):
    bid = _new_graph(farmhand_call)
    try:
        node_id = _add(farmhand_call, bid, NODE_KEY)
        ports = _inspect(farmhand_call, bid, node_id, ["ports"])["ports"]
        inlet = next(p for p in ports if p["direction"] == "inlet")
        assert inlet["kind"] == "port"
        assert inlet["is_linked"] is False
        assert inlet["promoted"] is False
        assert ":" in inlet["data_type"]
        # value or value_omitted — exactly one is present.
        assert ("value" in inlet) != ("value_omitted" in inlet)
    finally:
        _close(farmhand_call, bid)


def test_inspect_state_reports_stage_booleans(farmhand_call):
    """state carries per-stage lifecycle flags — the post-hot-reload diagnostic."""
    bid = _new_graph(farmhand_call)
    try:
        node_id = _add(farmhand_call, bid)
        state = _inspect(farmhand_call, bid, node_id, ["state"])["state"]
        for key in (
            "is_valid",
            "is_registered",
            "is_imported",
            "is_instantiated",
            "is_initialized",
            "is_structural",
            "has_test_passed",
        ):
            assert isinstance(state[key], bool), key
        assert state["errors"] == []
        assert isinstance(state["warnings"], list)
    finally:
        _close(farmhand_call, bid)


def test_inspect_round_trips_into_set_property(farmhand_call):
    """The contract that motivates the tool: a row's 'name' is what set_property takes."""
    bid = _new_graph(farmhand_call)
    try:
        node_id = _add(farmhand_call, bid)
        rows = {r["name"]: r for r in _inspect(farmhand_call, bid, node_id, ["settings"])["settings"]}
        assert rows["example_int"]["value"] == 3

        _call(
            farmhand_call,
            "graph_editor_set_property",
            {"binding_id": bid, "node_id": node_id, "name": "example_int", "value": 42},
        )
        after = {r["name"]: r for r in _inspect(farmhand_call, bid, node_id, ["settings"])["settings"]}
        assert after["example_int"]["value"] == 42
        assert after["example_int"]["is_set"] is True  # now overridden
        assert after["example_int"]["default"] == 3  # what a reset would restore
    finally:
        _close(farmhand_call, bid)


def test_set_property_reports_silent_validator_rejection(farmhand_call):
    """even_int's validator drops odd writes silently; the tool must not report success."""
    bid = _new_graph(farmhand_call)
    try:
        node_id = _add(farmhand_call, bid)
        result = _call(
            farmhand_call,
            "graph_editor_set_property",
            {"binding_id": bid, "node_id": node_id, "name": "even_int", "value": 7},
        )
        assert result.isError is True
        assert "[set_rejected]" in result.content[0].text
        # And the value really is unchanged.
        rows = {r["name"]: r for r in _inspect(farmhand_call, bid, node_id, ["settings"])["settings"]}
        assert rows["even_int"]["value"] == 4
    finally:
        _close(farmhand_call, bid)


def test_set_property_accepts_valid_value(farmhand_call):
    """The verification must not flag a legitimate write."""
    bid = _new_graph(farmhand_call)
    try:
        node_id = _add(farmhand_call, bid)
        result = call_tool_json(
            _call(
                farmhand_call,
                "graph_editor_set_property",
                {"binding_id": bid, "node_id": node_id, "name": "even_int", "value": 8},
            )
        )
        assert "8" in result["summary"]
    finally:
        _close(farmhand_call, bid)


def test_inspect_rejects_empty_and_unknown_sections(farmhand_call):
    """get= is forced at two layers: the schema rejects [], the tool rejects bad names.

    minItems/enum in input_schema_override are enforced by the MCP host BEFORE
    run() executes, so an empty or misspelled section never reaches the tool
    body — the in-body guards remain as defence for non-MCP callers.
    """
    bid = _new_graph(farmhand_call)
    try:
        node_id = _add(farmhand_call, bid)
        empty = _call(
            farmhand_call,
            "graph_editor_inspect_node",
            {"binding_id": bid, "node_id": node_id, "get": []},
        )
        assert empty.isError is True
        assert "non-empty" in empty.content[0].text

        bad = _call(
            farmhand_call,
            "graph_editor_inspect_node",
            {"binding_id": bid, "node_id": node_id, "get": ["bogus"]},
        )
        assert bad.isError is True
        # Either layer may catch it; both name the offending value.
        assert "bogus" in bad.content[0].text
    finally:
        _close(farmhand_call, bid)


def test_inspect_unknown_node_is_stable_error(farmhand_call):
    bid = _new_graph(farmhand_call)
    try:
        result = _call(
            farmhand_call,
            "graph_editor_inspect_node",
            {"binding_id": bid, "node_id": "ghost", "get": ["summary"]},
        )
        assert result.isError is True
        assert "[node_not_found]" in result.content[0].text
    finally:
        _close(farmhand_call, bid)
