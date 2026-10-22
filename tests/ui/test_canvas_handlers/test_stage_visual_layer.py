"""Tests for a stage canvas: ``VisualLayerHandlers`` and ``InteractionHandlers`` on ``STAGE``.

A stage canvas mounts only on-stage nodes, at their stage rect translated by the stage origin,
and draws only on-stage edges between mounted nodes.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from haybale_graph_editor.editors.graph_canvas.handlers.interaction import InteractionHandlers
from haybale_graph_editor.editors.graph_canvas.handlers import visual_layer as vl_module
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haywire.core.graph.types import ChangeReason, ValidationResult
from haywire.core.node.layout import PATCH, STAGE
from haywire.ui.components.graph.event_definitions import SyncAllEdgesEvent, UserDragUpdateEvent

from tests.conftest import edit_route

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on the asyncio backend."""
    return "asyncio"


def _wrapper(node_id: str, *, on_stage: bool, patch_xy=(5.0, 6.0), stage_xy=(0.0, 0.0)):
    props = SimpleNamespace(on_stage=on_stage, posX=patch_xy[0], posY=patch_xy[1])
    props.stage_x, props.stage_y = stage_xy
    props.get_position = lambda channel=PATCH: (getattr(props, channel.x), getattr(props, channel.y))
    w = MagicMock()
    w.node_id = node_id
    w.node.node_id = node_id
    w.node.props = props
    w.state.has_warning.return_value = False
    return w


def _edge(edge_id: str, src: str, dst: str, *, on_stage: bool = True):
    return SimpleNamespace(
        edge_id=edge_id,
        source_node_id=src,
        sink_node_id=dst,
        outlet_port_id="o",
        inlet_port_id="i",
        on_stage=on_stage,
    )


@pytest.fixture(autouse=True)
def _plain_edge_payloads(monkeypatch):
    monkeypatch.setattr(vl_module, "edge_visual_state", lambda e: ("state", e.edge_id))
    monkeypatch.setattr(vl_module, "edge_sync_payload", lambda e, s: {"id": e.edge_id})


@pytest.fixture
def graph():
    g = MagicMock()
    g.node_wrappers = {
        "a": _wrapper("a", on_stage=True),
        "b": _wrapper("b", on_stage=True, stage_xy=(10.0, 20.0)),
        "c": _wrapper("c", on_stage=False),
    }
    g.edge_wrappers = {
        "ab": _edge("ab", "a", "b"),
        "ac": _edge("ac", "a", "c"),
        "ab_patch": _edge("ab_patch", "a", "b", on_stage=False),
    }
    g.get_node_wrapper.side_effect = lambda nid: g.node_wrappers.get(nid)
    g.get_edge_wrapper.side_effect = lambda eid: g.edge_wrappers.get(eid)
    g.canvas_extent.return_value = (1000, 900)
    g.library_compatibility_findings = []
    return g


def _layer(graph, channel=STAGE):
    canvas_vue = MagicMock()
    h = VisualLayerHandlers(
        graph=graph,
        route=edit_route(MagicMock()),
        skin_factory=MagicMock(),
        canvas_vue=canvas_vue,
        channel=channel,
    )
    h.mounted_at = {}  # type: ignore[attr-defined]

    def _add(node, position):
        h.mounted_at[node.node_id] = position  # type: ignore[attr-defined]
        h.node_panels[node.node_id] = MagicMock()
        return True

    h.add_node_visual = MagicMock(side_effect=_add)  # type: ignore[method-assign]
    return h


def _edge_ids(h):
    """Edge ids sent in SyncAllEdgesEvents so far."""
    ids: list[str] = []
    for call in h.canvas_vue.emit_sync_event.call_args_list:
        (event,), _ = call
        if isinstance(event, SyncAllEdgesEvent):
            ids.extend(p["id"] for p in event.edges)
    return ids


def test_only_on_stage_nodes_mount_in_sync_with_graph(graph):
    h = _layer(graph)
    h.sync_with_graph()
    assert set(h.node_panels) == {"a", "b"}


@pytest.mark.anyio
async def test_only_on_stage_nodes_mount_in_chunked_sync(graph):
    h = _layer(graph)
    progress = []
    await h.sync_with_graph_chunked(on_progress=lambda i, n: progress.append((i, n)))
    assert set(h.node_panels) == {"a", "b"}
    assert progress == [(1, 2), (2, 2)]


def test_only_on_stage_edges_between_mounted_nodes_register(graph):
    h = _layer(graph)
    h.sync_with_graph()
    assert set(h.edge_states) == {"ab"}
    assert _edge_ids(h) == ["ab"]


def test_resync_edges_sends_only_eligible_edges(graph):
    h = _layer(graph)
    h.resync_edges()
    assert _edge_ids(h) == ["ab"]


def test_add_edge_visual_refuses_an_ineligible_edge(graph):
    h = _layer(graph)
    assert h.add_edge_visual(graph.edge_wrappers["ac"]) is False
    assert h.add_edge_visual(graph.edge_wrappers["ab_patch"]) is False
    assert h.edge_states == {}
    h.canvas_vue.emit_sync_event.assert_not_called()
    assert h.add_edge_visual(graph.edge_wrappers["ab"]) is True


def test_on_validated_registers_only_eligible_edges(graph):
    h = _layer(graph)
    h.on_validated(
        ValidationResult(
            nodes={},
            edges={e: ChangeReason.EDGE_ADDED for e in graph.edge_wrappers},
            validation_time_ms=0.0,
        )
    )
    assert _edge_ids(h) == ["ab"]


def test_counts_follow_the_filter(graph):
    assert _layer(graph).included_node_count() == 2
    assert _layer(graph).included_edge_count() == 1
    assert _layer(graph, PATCH).included_node_count() == 3
    assert _layer(graph, PATCH).included_edge_count() == 3


@pytest.mark.anyio
async def test_chunked_sync_waits_for_the_included_edge_count(graph):
    h = _layer(graph)
    waited = []

    async def _wait(n):
        waited.append(n)

    h._await_client_drawn = _wait  # type: ignore[method-assign]
    await h.sync_with_graph_chunked()
    assert waited == [1]


def _stage_changed(*ids):
    return ValidationResult(
        nodes={i: ChangeReason.NODE_STAGE_CHANGED for i in ids}, edges={}, validation_time_ms=0.0
    )


def test_stage_change_mounts_and_unmounts(graph):
    h = _layer(graph)
    h.sync_with_graph()
    h.canvas_vue.emit_sync_event.reset_mock()

    graph.node_wrappers["c"].node.props.on_stage = True
    graph.edge_wrappers["ac"].on_stage = True
    h.on_validated(_stage_changed("c"))
    assert "c" in h.node_panels
    assert "ac" in h.edge_states
    assert "ac" in _edge_ids(h)

    graph.node_wrappers["c"].node.props.on_stage = False
    h.on_validated(_stage_changed("c"))
    assert "c" not in h.node_panels
    assert "ac" not in h.edge_states
    assert "ab" in h.edge_states  # untouched


def test_stage_change_mounts_only_the_eligible_edges(graph):
    h = _layer(graph)
    h.sync_with_graph()
    graph.edge_wrappers["ac"].on_stage = False
    graph.node_wrappers["c"].node.props.on_stage = True
    h.on_validated(_stage_changed("c"))
    # ac is a data edge (not on stage), so it stays undrawn though both ends are mounted.
    assert "c" in h.node_panels
    assert "ac" not in h.edge_states


def test_a_stage_change_during_a_chunked_load_mounts_the_node_but_sends_no_edges(graph):
    """The chunked load sends every edge once its nodes are mounted; an earlier one has no pins yet."""
    h = _layer(graph)
    h.sync_with_graph()
    h.mounting = True
    graph.node_wrappers["c"].node.props.on_stage = True
    graph.edge_wrappers["ac"].on_stage = True

    h.on_validated(_stage_changed("c"))

    assert "c" in h.node_panels
    assert "ac" not in h.edge_states


def test_a_patch_canvas_ignores_the_stage_reason(graph):
    h = _layer(graph, PATCH)
    h.on_validated(_stage_changed("c"))
    h.add_node_visual.assert_not_called()
    assert h.node_panels == {}


def test_positions_are_translated_by_the_origin(graph):
    h = _layer(graph)
    h.sync_with_graph()
    assert h.mounted_at == {"a": (200.0, 200.0), "b": (210.0, 220.0)}

    resent = []
    h.update_node_position = lambda nid, pos: resent.append((nid, pos))  # type: ignore[method-assign]
    graph.node_wrappers["a"].node.props.stage_x = 60.0
    graph.node_wrappers["a"].node.props.stage_y = 100.0
    h.resync_positions(["a"])
    assert resent == [("a", (260.0, 300.0))]

    resent.clear()
    h.on_validated(ValidationResult(nodes={"a": ChangeReason.NODE_MOVED}, edges={}, validation_time_ms=0.0))
    assert resent == [("a", (260.0, 300.0))]


def test_a_drag_update_is_translated_back_into_stage_coordinates():
    editor = MagicMock()
    handlers = InteractionHandlers(edit_route(editor), channel=STAGE)
    handlers.process_drag_update(UserDragUpdateEvent(positions={"a": {"x": 260.0, "y": 300.0}}))
    editor.move_nodes_to.assert_called_once_with({"a": {"x": 60.0, "y": 100.0}}, STAGE)


def test_a_patch_drag_update_is_untouched():
    editor = MagicMock()
    handlers = InteractionHandlers(edit_route(editor))
    handlers.process_drag_update(UserDragUpdateEvent(positions={"a": {"x": 260.0, "y": 300.0}}))
    editor.move_nodes_to.assert_called_once_with({"a": {"x": 260.0, "y": 300.0}}, PATCH)


def test_each_canvas_applies_only_its_own_extent(graph):
    stage, patch_layer = _layer(graph), _layer(graph, PATCH)
    result = ValidationResult(nodes={}, edges={}, canvas_sizes={"stage": (700, 600)}, validation_time_ms=0.0)
    with (
        patch.object(stage, "_apply_canvas_resize") as s,
        patch.object(patch_layer, "_apply_canvas_resize") as p,
    ):
        stage.on_validated(result)
        patch_layer.on_validated(result)
    s.assert_called_once_with(700, 600)
    p.assert_not_called()


_REFUSED = "This connection would not show on the stage. Make it in the patch view."


def _with_ports(graph, ports: dict[str, dict[str, bool]]) -> None:
    """Give the mocked nodes real-looking ports: ``{node_id: {port_id: on_stage}}``."""
    for node_id, by_id in ports.items():
        graph.node_wrappers[node_id].node.ports = {
            pid: SimpleNamespace(on_stage=on) for pid, on in by_id.items()
        }


def _create(h, editor, src="a", outlet="o", dst="b", inlet="i"):
    from haywire.ui.components.graph.event_definitions import EdgeCreatedEvent

    with patch.object(vl_module.ui, "notify") as notify:
        h.process_edge_creation(
            EdgeCreatedEvent(sourceNodeId=src, outletPinId=outlet, sinkNodeId=dst, inletPinId=inlet)
        )
    return notify


def _gated_layer(graph, channel):
    h = _layer(graph, channel)
    editor = MagicMock()
    editor.create_edge.return_value = True
    h.route = edit_route(editor)
    return h, editor


def test_a_data_edge_is_refused_on_a_stage_canvas(graph):
    _with_ports(graph, {"a": {"o": False}, "b": {"i": False}})

    stage, stage_editor = _gated_layer(graph, STAGE)
    notify = _create(stage, stage_editor)
    stage_editor.create_edge.assert_not_called()
    notify.assert_called_once_with(_REFUSED, type="warning")

    patch_layer, patch_editor = _gated_layer(graph, PATCH)
    _create(patch_layer, patch_editor)
    patch_editor.create_edge.assert_called_once_with("a", "o", "b", "i")


def test_an_annotation_link_is_created_on_stage(graph):
    _with_ports(graph, {"a": {"bottom_0": True}, "b": {"top_0": True}})
    stage, editor = _gated_layer(graph, STAGE)

    _create(stage, editor, outlet="bottom_0", inlet="top_0")

    editor.create_edge.assert_called_once_with("a", "bottom_0", "b", "top_0")


def test_a_drop_on_an_annotation_open_slot_is_created_on_stage(graph):
    # A side's open slot is an ADD[ANNOTATION] port, which travels on the annotation wire.
    _with_ports(graph, {"a": {"bottom_0": True}, "b": {"left_3": True}})
    stage, editor = _gated_layer(graph, STAGE)

    _create(stage, editor, outlet="bottom_0", inlet="left_3")

    editor.create_edge.assert_called_once()


def test_an_auto_wire_from_a_data_pin_is_refused_on_stage(graph):
    from haywire.ui.components.graph.event_definitions import SyncEdgeConnectCancelEvent

    _with_ports(graph, {"a": {"o": False}})
    stage, editor = _gated_layer(graph, STAGE)
    stage.context = MagicMock()
    new_node = MagicMock()
    new_node.node_id = "new"
    new_node.node.ports = {}
    pending = {"pin_dir": "outlet", "wire": "", "data_type": "", "node_id": "a", "pin_id": "o"}

    with patch.object(vl_module.ui, "notify") as notify:
        stage._try_auto_wire(new_node, pending)

    editor.create_edge.assert_not_called()
    notify.assert_called_once_with(_REFUSED, type="warning")
    sent = [call.args[0] for call in stage.canvas_vue.emit_sync_event.call_args_list]
    assert any(isinstance(e, SyncEdgeConnectCancelEvent) for e in sent)
