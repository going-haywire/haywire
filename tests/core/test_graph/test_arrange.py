"""Node arrange: the node sets a scope covers, and the layout ``arrange_layout`` computes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from haywire.core.graph.arrange import (
    ArrangeGaps,
    ArrangeScope,
    arrange_layout,
    arranged_nodes,
    connected_nodes,
)
from haywire.core.graph.editor import Editor

from tests.conftest import make_node

DOWN, UP, FLOW, ALL = ArrangeScope.DOWNSTREAM, ArrangeScope.UPSTREAM, ArrangeScope.FLOW, ArrangeScope.ALL


def _graph(edges, nodes=(), direction="l2r", sizes=None, locked=(), positions=None):
    """A stand-in graph: ``edges`` as ``"a>b"`` strings; nodes default to 100x50 at the origin."""
    sizes = sizes or {}
    positions = positions or {}
    ids = list(dict.fromkeys([*nodes, *(n for e in edges for n in e.split(">"))]))
    wrappers = {}
    for n in ids:
        w, h = sizes.get(n, (100, 50))
        x, y = positions.get(n, (0.0, 0.0))
        props = SimpleNamespace(posX=x, posY=y, width=w, height=h, locked=n in locked)
        wrappers[n] = SimpleNamespace(node=SimpleNamespace(props=props))
    edge_wrappers = {
        f"e{i}": SimpleNamespace(source_node_id=e.split(">")[0], sink_node_id=e.split(">")[1])
        for i, e in enumerate(edges)
    }
    return SimpleNamespace(
        node_wrappers=wrappers,
        edge_wrappers=edge_wrappers,
        props=SimpleNamespace(layout_direction=direction),
    )


def _rect(graph, positions, n):
    props = graph.node_wrappers[n].node.props
    x, y = (positions[n]["x"], positions[n]["y"]) if n in positions else (props.posX, props.posY)
    return x, y, x + props.width, y + props.height


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _no_overlaps(graph, positions, ids):
    rects = [_rect(graph, positions, n) for n in ids]
    return not any(_overlap(rects[i], rects[j]) for i in range(len(rects)) for j in range(i + 1, len(rects)))


def _x(graph, positions, n) -> float:
    return _rect(graph, positions, n)[0]


# ---------------------------------------------------------------------------
# connected_nodes
# ---------------------------------------------------------------------------


def test_downstream_and_upstream_follow_edges_from_the_start_node():
    graph = _graph(["a>b", "b>c", "d>b"])
    assert connected_nodes(graph, "b", DOWN) == {"b", "c"}
    assert connected_nodes(graph, "b", UP) == {"a", "b", "d"}


def test_flow_follows_edges_either_way():
    graph = _graph(["a>b", "d>b", "b>c", "x>y"])
    assert connected_nodes(graph, "a", FLOW) == {"a", "b", "c", "d"}


def test_all_is_every_node():
    graph = _graph(["a>b"], nodes=["z"])
    assert connected_nodes(graph, None, ALL) == {"a", "b", "z"}


def test_a_cycle_is_walked_once():
    graph = _graph(["a>b", "b>c", "c>a"])
    assert connected_nodes(graph, "a", DOWN) == {"a", "b", "c"}


def test_an_isolated_node_is_its_own_set_and_an_unknown_one_is_empty():
    graph = _graph(["a>b"], nodes=["z"])
    assert connected_nodes(graph, "z", FLOW) == {"z"}
    assert connected_nodes(graph, "nope", DOWN) == set()


def test_a_plain_string_names_a_scope():
    graph = _graph(["a>b"])
    assert connected_nodes(graph, "a", "downstream") == {"a", "b"}


# ---------------------------------------------------------------------------
# arrange_layout — layering
# ---------------------------------------------------------------------------


def test_the_start_node_does_not_move_and_the_rest_lie_downstream_of_it():
    graph = _graph(["a>b", "b>c"], positions={"a": (500.0, 300.0)})
    positions = arrange_layout(graph, DOWN, "a")
    assert set(positions) == {"b", "c"}
    assert positions["b"] == {"x": 500.0 + 100 + ArrangeGaps.rank, "y": 300.0}
    assert _x(graph, positions, "c") > _x(graph, positions, "b")


def test_upstream_places_everything_before_the_start_node():
    graph = _graph(["a>b", "b>c"], positions={"c": (500.0, 300.0)})
    positions = arrange_layout(graph, UP, "c")
    assert set(positions) == {"a", "b"}
    assert _x(graph, positions, "a") < _x(graph, positions, "b") < 500.0


def test_every_edge_points_forward_in_a_flow():
    graph = _graph(["a>b", "b>c", "a>c", "d>c", "c>e"])
    positions = arrange_layout(graph, FLOW, "a")
    for source, sink in (("a", "b"), ("b", "c"), ("a", "c"), ("d", "c"), ("c", "e")):
        assert _x(graph, positions, source) < _x(graph, positions, sink)


def test_a_node_feeding_a_late_consumer_sits_just_before_it():
    # d feeds only c, which is two layers in; it lands next to c, not in the first layer.
    graph = _graph(["a>b", "b>c", "d>c"])
    positions = arrange_layout(graph, FLOW, "a")
    assert _x(graph, positions, "d") == _x(graph, positions, "b")


def test_a_cycle_terminates_and_keeps_the_start_node_first():
    graph = _graph(["a>b", "b>c", "c>a"])
    positions = arrange_layout(graph, DOWN, "a")
    assert 0.0 < _x(graph, positions, "b") < _x(graph, positions, "c")


def test_a_layer_is_ordered_to_avoid_a_crossing():
    # a feeds d, b feeds c; graph order puts c above d, which would cross.
    graph = _graph(["a>d", "b>c"], nodes=["a", "b", "c", "d"])
    positions = arrange_layout(graph, ALL)
    a_above_b = _rect(graph, positions, "a")[1] < _rect(graph, positions, "b")[1]
    d_above_c = _rect(graph, positions, "d")[1] < _rect(graph, positions, "c")[1]
    assert a_above_b == d_above_c


def test_nodes_in_one_layer_stack_without_overlap():
    graph = _graph(["a>b", "a>c", "a>d"], sizes={"c": (300, 120)})
    positions = arrange_layout(graph, DOWN, "a")
    assert _no_overlaps(graph, positions, ["a", "b", "c", "d"])
    rects = sorted(_rect(graph, positions, n)[1:4:2] for n in "bcd")
    assert rects[1][0] - rects[0][1] == ArrangeGaps.cross


def test_a_layer_advances_by_its_widest_card():
    graph = _graph(["a>b", "a>c", "b>d"], sizes={"c": (400, 50)})
    positions = arrange_layout(graph, DOWN, "a")
    assert _x(graph, positions, "d") == _x(graph, positions, "b") + 400 + ArrangeGaps.rank


# ---------------------------------------------------------------------------
# arrange_layout — direction, locked, ALL, determinism
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("direction", "axis", "sign"),
    [("l2r", 0, 1), ("r2l", 0, -1), ("t2b", 1, 1), ("b2t", 1, -1)],
)
def test_downstream_lies_along_the_graph_layout_direction(direction, axis, sign):
    graph = _graph(["a>b", "b>c"], direction=direction, sizes={"a": (100, 50), "b": (120, 70)})
    positions = arrange_layout(graph, DOWN, "a")
    a, b, c = (_rect(graph, positions, n) for n in "abc")
    assert _no_overlaps(graph, positions, ["a", "b", "c"])
    assert sign * (b[axis] - a[axis]) > 0
    assert sign * (c[axis] - b[axis]) > 0


def test_a_locked_node_is_laid_out_around_but_never_moves():
    graph = _graph(["a>b", "b>c"], locked=["b"])
    positions = arrange_layout(graph, DOWN, "a")
    assert set(positions) == {"c"}


def test_all_bands_separate_parts_and_keeps_their_centre():
    graph = _graph(
        ["a>b", "c>d"],
        positions={"a": (0.0, 0.0), "b": (40.0, 400.0), "c": (900.0, 10.0), "d": (20.0, 90.0)},
    )
    before = [(n.node.props.posX, n.node.props.posY) for n in graph.node_wrappers.values()]
    positions = arrange_layout(graph, ALL)
    assert set(positions) == {"a", "b", "c", "d"}
    assert _no_overlaps(graph, positions, ["a", "b", "c", "d"])
    centre = sum(p["x"] for p in positions.values()) / 4, sum(p["y"] for p in positions.values()) / 4
    assert centre == pytest.approx((sum(x for x, _ in before) / 4, sum(y for _, y in before) / 4))


def test_all_with_only_locked_nodes_moves_nothing():
    graph = _graph(["a>b"], locked=["a", "b"])
    assert arrange_layout(graph, ALL) == {}


def test_an_unknown_start_node_moves_nothing():
    assert arrange_layout(_graph(["a>b"]), DOWN, "nope") == {}


def test_the_layout_is_the_same_on_every_call():
    graph = _graph(["a>b", "a>c", "b>d", "c>d", "e>c", "d>a", "f>g"])
    assert arrange_layout(graph, ALL) == arrange_layout(graph, ALL)
    assert arrange_layout(graph, FLOW, "e") == arrange_layout(graph, FLOW, "e")


# ---------------------------------------------------------------------------
# On a real graph, through the editor
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_an_arrange_is_one_undo_step(graph_with_library_system, library_system):
    from haybale_testing.nodes.testbed.swinglet_probe import SwingletVisualProbeNode

    graph = graph_with_library_system
    key = SwingletVisualProbeNode.class_identity.registry_key
    editor = Editor(graph, library_system.get_node_factory())
    nodes = [make_node(graph, key) for _ in range(3)]
    assert all(isinstance(w.node, SwingletVisualProbeNode) for w in nodes)
    a, b, c = (w.node_id for w in nodes)
    assert editor.create_edge(a, "note", b, "note")
    assert editor.create_edge(b, "note", c, "note")
    before = {w.node_id: (w.node.props.posX, w.node.props.posY) for w in nodes}

    positions = arrange_layout(graph, DOWN, a)
    assert set(positions) == {b, c}
    assert editor.move_nodes_to(positions)
    assert graph.node_wrappers[b].node.props.posX == positions[b]["x"]

    assert editor.undo()
    assert {w.node_id: (w.node.props.posX, w.node.props.posY) for w in nodes} == before


def test_gaps_set_the_space_between_cards():
    graph = _graph(["a>b", "a>c"])
    positions = arrange_layout(graph, DOWN, "a", gaps=ArrangeGaps(rank=300, cross=10))
    assert _x(graph, positions, "b") == 100 + 300
    tops = sorted(_rect(graph, positions, n)[1] for n in "bc")
    assert tops[1] - tops[0] == 50 + 10


def test_gaps_read_the_user_settings(test_injector):
    from haywire.core.graph.arrange_settings import ArrangeSettings

    settings = ArrangeSettings()
    before = settings.rank_gap
    settings.rank_gap = 250
    try:
        assert ArrangeGaps.from_settings().rank == 250
    finally:
        settings.rank_gap = before


def test_several_start_nodes_arrange_every_flow_they_touch_in_place():
    graph = _graph(
        ["a>b", "c>d", "x>y"],
        positions={"a": (0.0, 0.0), "b": (40.0, 400.0), "c": (900.0, 10.0), "d": (20.0, 90.0)},
    )
    positions = arrange_layout(graph, FLOW, ["a", "d"])
    assert set(positions) == {"a", "b", "c", "d"}  # no anchor: all move; x, y untouched
    assert _no_overlaps(graph, positions, ["a", "b", "c", "d"])
    centre = sum(p["x"] for p in positions.values()) / 4, sum(p["y"] for p in positions.values()) / 4
    assert centre == pytest.approx(((0 + 40 + 900 + 20) / 4, (0 + 400 + 10 + 90) / 4))


def test_two_start_nodes_in_one_flow_arrange_it_once():
    graph = _graph(["a>b", "b>c"])
    assert arranged_nodes(graph, FLOW, ["a", "c"]) == {"a", "b", "c"}
    assert set(arrange_layout(graph, FLOW, ["a", "c"])) == {"a", "b", "c"}


def test_one_start_node_in_a_list_is_the_anchor():
    graph = _graph(["a>b"])
    assert arrange_layout(graph, DOWN, ["a"]) == arrange_layout(graph, DOWN, "a")


def test_directed_scopes_refuse_several_start_nodes():
    graph = _graph(["a>b", "c>d"])
    with pytest.raises(ValueError, match="one start node"):
        arrange_layout(graph, DOWN, ["a", "c"])
