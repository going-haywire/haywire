"""Unit tests for node_data-carrying creation and the paste action."""

from typing import Any, cast

import pytest

from haywire.core.graph.base import BaseGraph

pytestmark = pytest.mark.unit


def test_create_node_wrapper_passes_node_data_to_build(monkeypatch):
    captured = {}
    g = BaseGraph(graph_id="test_graph", name="Test Graph")

    class _FakeWrapper:
        def __init__(self, *a, **k):
            self._node_id = k.get("node_id", "node_x")

        def build(self, node_info=None):
            captured["node_info"] = node_info

    # create_node_wrapper does a local `from ..node.node_wrapper import NodeWrapper`,
    # so the name resolves from the source module at call time.
    from haywire.core.node import node_wrapper as node_wrapper_module

    monkeypatch.setattr(node_wrapper_module, "NodeWrapper", _FakeWrapper)
    monkeypatch.setattr(g, "add_node_wrapper", lambda w: w)

    g.create_node_wrapper("some.key", position=(0, 0), node_data={"hello": "world"})
    assert captured["node_info"] == {"hello": "world"}


def test_add_node_action_forwards_node_data():
    from haywire.core.undo.actions.graph_actions import AddNodeAction

    seen = {}

    class _G:
        def create_node_wrapper(self, registry_key, position, node_data=None, node_id=None):
            seen["node_data"] = node_data
            return object()

    action = AddNodeAction(graph=cast(Any, _G)(), registry_key="k", position=(0, 0), node_data={"a": 1})
    action._execute_impl()
    assert seen["node_data"] == {"a": 1}


def test_add_node_action_default_node_data_is_none():
    from haywire.core.undo.actions.graph_actions import AddNodeAction

    seen = {}

    class _G:
        def create_node_wrapper(self, registry_key, position, node_data=None, node_id=None):
            seen["node_data"] = node_data
            return object()

    action = AddNodeAction(graph=cast(Any, _G)(), registry_key="k", position=(0, 0))
    action._execute_impl()
    assert seen["node_data"] is None


def test_add_node_action_redo_reuses_wrapper_without_recreating():
    """A second _execute_impl() (redo) must re-add the existing wrapper via
    add_node_wrapper, not recreate it through create_node_wrapper."""
    from haywire.core.undo.actions.graph_actions import AddNodeAction

    calls = {"create": 0, "add": 0}
    sentinel = object()

    class _G:
        def create_node_wrapper(self, registry_key, position, node_data=None, node_id=None):
            calls["create"] += 1
            return sentinel

        def add_node_wrapper(self, wrapper):
            calls["add"] += 1
            assert wrapper is sentinel  # redo re-adds the SAME built wrapper
            return wrapper

    action = AddNodeAction(graph=cast(Any, _G)(), registry_key="k", position=(0, 0), node_data={"a": 1})
    action._execute_impl()  # first execution -> create
    action._execute_impl()  # redo -> add, NOT create
    assert calls["create"] == 1
    assert calls["add"] == 1
    assert action.wrapper is sentinel


def _payload(nodes, edges):
    return {
        "haywire_clipboard": True,
        "format_version": 1,
        "source": {"session_id": "s", "timestamp": 1.0},
        "bounding_box": {"min_x": 0.0, "min_y": 0.0, "max_x": 0.0, "max_y": 0.0},
        "nodes": nodes,
        "edges": edges,
    }


def test_paste_builds_child_actions_with_new_ids_and_remapped_edges(monkeypatch):
    from haywire.core.undo.actions.graph_actions import PasteClipboardAction, AddNodeAction, AddEdgeAction

    payload = _payload(
        nodes={
            "n1": {"node_id": "n1", "registry_key": "k", "position": [100.0, 100.0], "node_data": {"v": 1}},
            "n2": {"node_id": "n2", "registry_key": "k", "position": [200.0, 100.0], "node_data": {"v": 2}},
        },
        edges={
            "e": {
                "source_node_id": "n1",
                "outlet_port_id": "o",
                "sink_node_id": "n2",
                "inlet_port_id": "i",
                "edge_type": "data",
                "chain_adapter_keys": [],
                "is_lazy": False,
            },
        },
    )

    ids = iter(["new_a", "new_b"])

    class _G:
        # No node_factory needed — paste does not pre-validate registry_keys.
        def generate_unique_node_id(self, prefix="node"):
            return next(ids)

    action = PasteClipboardAction(graph=cast(Any, _G)(), payload=payload, paste_x=0.0, paste_y=0.0)

    node_actions = [a for a in action.actions if isinstance(a, AddNodeAction)]
    edge_actions = [a for a in action.actions if isinstance(a, AddEdgeAction)]
    assert {a.registry_key for a in node_actions} == {"k"}
    # node_data carries the original "v" plus the overwritten paste position in
    # props' "values" block (the nested shape from_dict restores from), so
    # build()'s _initialize_from_dict restore lands the paste point.
    assert {cast(dict, a.node_data)["v"] for a in node_actions} == {1, 2}
    assert all(
        "posX" in cast(dict, a.node_data)["props"]["values"]
        and "posY" in cast(dict, a.node_data)["props"]["values"]
        for a in node_actions
    )
    assert len(edge_actions) == 1
    ea = edge_actions[0]
    assert ea.source_node_id == "new_a"
    assert ea.sink_node_id == "new_b"
    assert {a.position for a in node_actions} == {(100.0, 100.0), (200.0, 100.0)}


def test_paste_builds_actions_for_unknown_registry_keys_too():
    """Unknown types are NOT rejected — they paste as placeholders (like load_from_dict)."""
    from haywire.core.undo.actions.graph_actions import PasteClipboardAction, AddNodeAction

    payload = _payload(
        nodes={
            "n1": {"node_id": "n1", "registry_key": "totally.unknown", "position": [0, 0], "node_data": {}}
        },
        edges={},
    )

    class _G:
        def generate_unique_node_id(self, prefix="node"):
            return "new_x"

    action = PasteClipboardAction(graph=cast(Any, _G)(), payload=payload, paste_x=0.0, paste_y=0.0)
    node_actions = [a for a in action.actions if isinstance(a, AddNodeAction)]
    assert [a.registry_key for a in node_actions] == ["totally.unknown"]


def test_paste_offsets_positions_to_paste_point():
    from haywire.core.undo.actions.graph_actions import PasteClipboardAction, AddNodeAction

    payload = _payload(
        nodes={"n1": {"node_id": "n1", "registry_key": "k", "position": [100.0, 200.0], "node_data": {}}},
        edges={},
    )
    # bbox.min is (0,0) from _payload; override to make the offset non-trivial:
    payload["bounding_box"] = {"min_x": 100.0, "min_y": 200.0, "max_x": 100.0, "max_y": 200.0}

    class _G:
        def generate_unique_node_id(self, prefix="node"):
            return "new_x"

    # paste at (500, 600): offset = (500-100, 600-200) = (400, 400)
    # node at (100,200) -> (100+400, 200+400) = (500, 600)
    action = PasteClipboardAction(graph=cast(Any, _G)(), payload=payload, paste_x=500.0, paste_y=600.0)
    node_actions = [a for a in action.actions if isinstance(a, AddNodeAction)]
    assert len(node_actions) == 1
    assert node_actions[0].position == (500.0, 600.0)


def test_editor_paste_clipboard_adds_action_and_returns_new_ids():
    from haywire.core.graph.editor import Editor
    from haywire.core.undo.actions import graph_actions

    added = {}

    class _HM:
        def add_action(self, action):
            added["action"] = action

    payload = _payload(
        nodes={"n1": {"node_id": "n1", "registry_key": "k", "position": [0, 0], "node_data": {}}},
        edges={},
    )

    ed = Editor.__new__(Editor)  # bypass __init__ wiring
    ed.graph = type(
        "G",
        (),
        {
            "generate_unique_node_id": lambda self, prefix="node": "new_x",
        },
    )()
    ed.history_manager = cast(Any, _HM())

    result = ed.paste_clipboard(payload, 10.0, 20.0)
    # Returns (new_node_ids, new_edge_ids) so callers can auto-select the paste.
    assert result == (["new_x"], [])
    assert isinstance(added["action"], graph_actions.PasteClipboardAction)


def test_add_node_action_forwards_node_id():
    """The pre-minted node_id must reach create_node_wrapper on first exec."""
    from haywire.core.undo.actions.graph_actions import AddNodeAction

    seen = {}

    class _G:
        def create_node_wrapper(self, registry_key, position, node_data=None, node_id=None):
            seen["node_id"] = node_id
            return object()

    action = AddNodeAction(graph=cast(Any, _G)(), registry_key="k", position=(0, 0), node_id="pre_minted_1")
    action._execute_impl()
    assert seen["node_id"] == "pre_minted_1"


def test_paste_node_actions_carry_pre_minted_ids():
    """Each child AddNodeAction must carry the id its remapped edges point at."""
    from haywire.core.undo.actions.graph_actions import PasteClipboardAction, AddNodeAction

    payload = _payload(
        nodes={
            "n1": {"node_id": "n1", "registry_key": "k", "position": [0, 0], "node_data": {}},
            "n2": {"node_id": "n2", "registry_key": "k", "position": [10, 0], "node_data": {}},
        },
        edges={},
    )
    ids = iter(["mint_a", "mint_b"])

    class _G:
        def generate_unique_node_id(self, prefix="node"):
            return next(ids)

    action = PasteClipboardAction(graph=cast(Any, _G)(), payload=payload, paste_x=0.0, paste_y=0.0)
    node_actions = [a for a in action.actions if isinstance(a, AddNodeAction)]
    assert {a.node_id for a in node_actions} == {"mint_a", "mint_b"}


def test_paste_execution_edge_connects_created_nodes():
    """EXECUTION-level test: run the composite against a recording fake graph
    whose create_edge_wrapper raises KeyError if an endpoint id was never
    registered by create_node_wrapper. The created node must adopt the
    pre-minted id so the edge connects.
    """
    from haywire.core.undo.actions.graph_actions import PasteClipboardAction

    payload = _payload(
        nodes={
            "n1": {"node_id": "n1", "registry_key": "k", "position": [0, 0], "node_data": {}},
            "n2": {"node_id": "n2", "registry_key": "k", "position": [10, 0], "node_data": {}},
        },
        edges={
            "e": {
                "source_node_id": "n1",
                "outlet_port_id": "o",
                "sink_node_id": "n2",
                "inlet_port_id": "i",
                "edge_type": "data",
                "chain_adapter_keys": [],
                "is_lazy": False,
            },
        },
    )

    class _RecordingGraph:
        """Mimics the real graph: create_node_wrapper registers a node under the
        id it actually uses; create_edge_wrapper does node_wrappers[id] and
        raises KeyError on a miss (exactly the real bug)."""

        def __init__(self):
            self.node_wrappers = {}
            self.edges = []
            self._counter = 0

        def generate_unique_node_id(self, prefix="node"):
            self._counter += 1
            return f"minted_{self._counter}"

        def create_node_wrapper(self, registry_key, position, node_data=None, node_id=None):
            # The real base.py mints its OWN id when node_id is None.
            if node_id is None:
                node_id = self.generate_unique_node_id(registry_key)
            wrapper = type("W", (), {"node_id": node_id})()
            self.node_wrappers[node_id] = wrapper
            return wrapper

        def create_edge_wrapper(self, source_node_id, outlet_port_id, sink_node_id, inlet_port_id):
            # Real graph indexes node_wrappers by id -> KeyError if absent.
            _ = self.node_wrappers[source_node_id]
            _ = self.node_wrappers[sink_node_id]
            edge = type("E", (), {"source": source_node_id, "sink": sink_node_id, "edge_id": "edge_0"})()
            self.edges.append(edge)
            return edge

        def add_node_wrapper(self, wrapper):
            self.node_wrappers[wrapper.node_id] = wrapper
            return wrapper

        def remove_node_wrapper(self, wrapper):
            self.node_wrappers.pop(wrapper.node_id, None)
            return wrapper

        def add_edge_wrapper(self, wrapper):
            self.edges.append(wrapper)
            return wrapper

        def remove_edge_wrapper(self, edge_id):
            self.edges = [e for e in self.edges if getattr(e, "edge_id", None) != edge_id]
            return None

    graph = _RecordingGraph()
    action = PasteClipboardAction(graph=cast(Any, graph), payload=payload, paste_x=0.0, paste_y=0.0)

    # EXECUTE the composite (this is what unit tests never did).
    action._execute_impl()

    # Two new nodes created, ids differ from originals (n1/n2).
    assert len(graph.node_wrappers) == 2
    assert "n1" not in graph.node_wrappers
    assert "n2" not in graph.node_wrappers

    # Exactly one edge, connecting the two CREATED node ids (remap agreed).
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.source in graph.node_wrappers
    assert edge.sink in graph.node_wrappers
    assert edge.source != edge.sink

    # Undo removes everything (single composite).
    action._undo_impl()
    assert len(graph.node_wrappers) == 0
    assert len(graph.edges) == 0


def test_editor_paste_clipboard_returns_none_on_error():
    """The except branch: an unexpected failure routing the action yields None."""
    from haywire.core.graph.editor import Editor

    payload = _payload(
        nodes={"n1": {"node_id": "n1", "registry_key": "k", "position": [0, 0], "node_data": {}}},
        edges={},
    )

    class _HM:
        def add_action(self, action):
            raise RuntimeError("boom")

    ed = Editor.__new__(Editor)
    ed.graph = type("G", (), {"generate_unique_node_id": lambda self, prefix="node": "new_x"})()
    ed.history_manager = cast(Any, _HM())

    assert ed.paste_clipboard(payload, 0.0, 0.0) is None


@pytest.mark.integration
class TestPasteExecutionIntegration:
    """Execute a paste-with-edge against a REAL graph with real nodes/edges,
    end-to-end, and confirm the pasted edge connects the two newly-created
    nodes (no KeyError)."""

    def _two_connected_nodes(self, graph):
        # TestAddFloatNode has only FLOAT ports — serializes cleanly (the
        # CALLBACK port on EdgeLinkTestNode trips an unrelated to_dict quirk).
        from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

        key = TestAddFloatNode.class_identity.registry_key
        node_a = graph.create_node_wrapper(key, position=(100, 100))
        node_b = graph.create_node_wrapper(key, position=(300, 100))
        edge = graph.create_edge_wrapper(node_a.node_id, "result", node_b.node_id, "value_a")
        assert edge.state.is_valid()
        return node_a, node_b, edge

    def test_paste_with_edge_connects_new_nodes(self, graph_with_library_system, library_system):
        from haywire.core.graph.clipboard import build_clipboard_payload
        from haywire.core.undo.actions.graph_actions import PasteClipboardAction

        graph = graph_with_library_system
        node_a, node_b, edge = self._two_connected_nodes(graph)
        original_ids = {node_a.node_id, node_b.node_id}

        payload = build_clipboard_payload(
            graph,
            node_ids=[node_a.node_id, node_b.node_id],
            edge_ids=[edge.edge_id],
            session_id="test-session",
        )
        assert len(payload["nodes"]) == 2
        assert len(payload["edges"]) == 1  # both-endpoints edge retained

        action = PasteClipboardAction(graph=cast(Any, graph), payload=payload, paste_x=500.0, paste_y=500.0)
        # EXECUTE the paste against the real graph.
        action._execute_impl()

        # Two NEW nodes exist with ids distinct from the originals.
        all_node_ids = set(graph.node_wrappers.keys())
        new_node_ids = all_node_ids - original_ids
        assert len(new_node_ids) == 2

        # An edge connects the two NEW nodes — remap + creation agreed.
        pasted_edges = [
            e
            for e in graph.edge_wrappers.values()
            if e.edge.source_node_id in new_node_ids and e.edge.sink_node_id in new_node_ids
        ]
        assert len(pasted_edges) == 1
        assert pasted_edges[0].state.is_valid()

        # Undo removes the pasted nodes + edge (single composite), leaving
        # only the originals.
        action._undo_impl()
        assert set(graph.node_wrappers.keys()) == original_ids

    def test_paste_node_lands_at_offset_position_not_original(
        self, graph_with_library_system, library_system
    ):
        """The pasted node's FINAL position (after build()'s
        _initialize_from_dict restores props.posX/posY) must be the paste
        point, NOT the original position.

        AddNodeAction(position=) is applied early via set_position, but
        _initialize_from_dict() then restores the serialized posX/posY. Unless
        PasteClipboardAction overwrites those props, the pasted node lands on
        top of its source. Single-node selection => bbox.min == the node's own
        pos => offset lands the node AT the paste point.
        """
        from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
        from haywire.core.graph.clipboard import build_clipboard_payload
        from haywire.core.undo.actions.graph_actions import PasteClipboardAction

        graph = graph_with_library_system
        key = TestAddFloatNode.class_identity.registry_key

        # Real node at a KNOWN position.
        orig_x, orig_y = 500.0, 600.0
        node = graph.create_node_wrapper(key, position=(orig_x, orig_y))
        node.node.props.set_position((orig_x, orig_y))
        assert node.node.props.posX == orig_x
        assert node.node.props.posY == orig_y
        original_ids = set(graph.node_wrappers.keys())

        payload = build_clipboard_payload(
            graph,
            node_ids=[node.node_id],
            edge_ids=[],
            session_id="test-session",
        )
        assert len(payload["nodes"]) == 1

        # Paste at a DIFFERENT point; single-node bbox.min == node pos, so the
        # offset lands the node exactly at the paste point.
        paste_x, paste_y = 1234.0, 4321.0
        action = PasteClipboardAction(
            graph=cast(Any, graph), payload=payload, paste_x=paste_x, paste_y=paste_y
        )
        action._execute_impl()

        new_node_ids = set(graph.node_wrappers.keys()) - original_ids
        assert len(new_node_ids) == 1
        pasted = graph.node_wrappers[next(iter(new_node_ids))]

        # FINAL position (post build()/from_dict restore) is the paste point...
        assert pasted.node.props.posX == paste_x
        assert pasted.node.props.posY == paste_y
        # ...and NOT the original.
        assert (pasted.node.props.posX, pasted.node.props.posY) != (orig_x, orig_y)

        action._undo_impl()
        assert set(graph.node_wrappers.keys()) == original_ids
