import pytest

pytestmark = pytest.mark.integration


def _two_node_graph_dict(graph):
    """Serialize a graph with two Display nodes and one edge between them."""
    a = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0))
    b = graph.create_node_wrapper("testing:node:SettingsNode", position=(100, 0))
    return graph.to_dict(), a.node_id, b.node_id


def test_poisoned_node_skips_only_itself(graph_with_library_system, library_system):
    graph = graph_with_library_system
    data, a_id, b_id = _two_node_graph_dict(graph)
    # Poison node A: a non-iterable "position" makes `tuple(wrapper_data.get(...))`
    # raise TypeError inside the loop body (registry_key mismatches are swallowed
    # internally by NodeWrapper and don't propagate out of the loop).
    data["nodes"][a_id]["position"] = 12345
    # Force the poisoned node to be iterated first, so this test fails today
    # (pre-fix) when the try/except wraps the whole loop.
    data["nodes"] = {a_id: data["nodes"][a_id], b_id: data["nodes"][b_id]}

    graph.clear()
    graph.load_from_dict(data)

    assert b_id in graph.node_wrappers, "healthy node must survive a poisoned sibling"
    assert a_id not in graph.node_wrappers


def test_poisoned_edge_skips_only_itself(graph_with_library_system, library_system):
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    graph = graph_with_library_system
    a = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0))
    b = graph.create_node_wrapper("testing:node:SettingsNode", position=(100, 0))
    promote_setting(a.node, "example", "example_float", direction=PortType.OUTLET)
    promote_setting(b.node, "example", "example_float", direction=PortType.INLET)
    promote_setting(a.node, "example", "example_string", direction=PortType.OUTLET)
    promote_setting(b.node, "example", "example_string", direction=PortType.INLET)
    float_pid = type(a.node.example).__dict__["example_float"].storage_key
    string_pid = type(a.node.example).__dict__["example_string"].storage_key
    edge1 = graph.create_edge_wrapper(a.node_id, float_pid, b.node_id, float_pid)
    edge2 = graph.create_edge_wrapper(a.node_id, string_pid, b.node_id, string_pid)
    assert edge1 is not None
    assert edge2 is not None

    data = graph.to_dict()
    assert len(data["edges"]) == 2
    # Poison the first edge with an edge_type value FlowType can't parse — this
    # raises ValueError directly in the loop body (source/sink node id mismatches
    # are swallowed internally by EdgeWrapper's own guarded build/formal
    # validation and don't propagate out of the loop).
    first_edge_id = edge1.edge_id
    second_edge_id = edge2.edge_id
    data["edges"][first_edge_id]["edge_type"] = "not-a-real-flow-type"
    # Force the poisoned edge to be iterated first, so this test fails today
    # (pre-fix) when the try/except wraps the whole loop.
    data["edges"] = {
        first_edge_id: data["edges"][first_edge_id],
        second_edge_id: data["edges"][second_edge_id],
    }

    graph.clear()
    graph.load_from_dict(data)

    assert a.node_id in graph.node_wrappers
    assert b.node_id in graph.node_wrappers
    # The poisoned edge is gone; the healthy sibling edge after it still loads.
    assert first_edge_id not in graph.edge_wrappers
    assert second_edge_id in graph.edge_wrappers, "healthy edge must survive a poisoned sibling"
