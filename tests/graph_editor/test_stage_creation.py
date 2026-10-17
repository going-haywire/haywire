"""A node made on a stage canvas lands on stage, and near its siblings in the patch."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from haybale_graph_editor.editors.graph_canvas.handlers.selection import DUPLICATE_OFFSET, SelectionHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.clipboard import build_clipboard_payload
from haywire.core.graph.editor import Editor
from haywire.core.graph.stage import next_stage_spot, stage_position_for_patch
from haywire.core.node.layout import PATCH, STAGE, LayoutChannel
from haywire.ui.components.graph.event_definitions import (
    NodeCreateRequestEvent,
    SplitEdgeWithRerouteEvent,
    UserPasteClipboardEvent,
)

from tests.conftest import edit_route, make_node

pytestmark = pytest.mark.unit

_ADD = "haybale-testing:node:TestAddFloatNode"


@pytest.fixture
def editor(graph_with_library_system: BaseGraph, library_system) -> Editor:
    return Editor(graph_with_library_system, library_system.get_node_factory())


def _visual(editor: Editor, channel: LayoutChannel, viewport_centre=None) -> VisualLayerHandlers:
    handler = object.__new__(VisualLayerHandlers)
    handler.patch_viewport_centre = (lambda: viewport_centre) if viewport_centre else None
    handler.route = edit_route(editor)
    handler.graph = editor.graph
    handler.channel = channel
    handler._make_sole_active_node = MagicMock()  # type: ignore[method-assign]
    return handler


def _selection(editor: Editor, channel: LayoutChannel, viewport_centre=None) -> SelectionHandlers:
    session = MagicMock()
    session.context.data.__getitem__.return_value.clipboard = None
    handler = SelectionHandlers(
        graph=editor.graph,
        route=edit_route(editor),
        session_id="s",
        session=session,
        channel=channel,
        patch_viewport_centre=(lambda: viewport_centre) if viewport_centre else None,
    )
    handler._select_pasted = MagicMock()  # type: ignore[method-assign]
    return handler


@pytest.fixture(autouse=True)
def _no_notify():
    with (
        patch("haybale_graph_editor.editors.graph_canvas.handlers.visual_layer.ui.notify"),
        patch("haybale_graph_editor.editors.graph_canvas.handlers.selection.ui.notify"),
    ):
        yield


def _values(editor: Editor, node_id: str) -> dict[str, Any]:
    wrapper = editor.graph.get_node_wrapper(node_id)
    assert wrapper is not None
    return wrapper.serialize()["node_data"]["props"]["values"]


def _props(editor: Editor, node_id: str):
    wrapper = editor.graph.get_node_wrapper(node_id)
    assert wrapper is not None
    return wrapper.node.props


def _assert_on_stage(
    editor: Editor, node_id: str, x: float, y: float, patch: tuple[float, float] | None = None
) -> None:
    props = _props(editor, node_id)
    assert props.on_stage is True
    assert props.get_position(STAGE) == (x, y)
    assert props.get_position(PATCH) == (patch or (x, y))
    assert props.stage_size_adapt == "auto"


def _assert_patch(editor: Editor, node_id: str, x: float, y: float) -> None:
    props = _props(editor, node_id)
    assert props.on_stage is False
    assert props.get_position(PATCH) == (x, y)


def _new_ids(editor: Editor, before: set[str]) -> list[str]:
    return sorted(set(editor.graph.node_wrappers) - before)


# ---------------------------------------------------------------------------
# Create at a click (background menu, add-node search, wizard, edge drop)
# ---------------------------------------------------------------------------


def test_create_on_stage_canvas_lands_on_stage_and_undoes_in_one_step(editor):
    handler = _visual(editor, STAGE)
    handler.process_node_creation_request(
        NodeCreateRequestEvent(registryKey=_ADD, position={"x": 500.0, "y": 340.0})
    )
    (node_id,) = _new_ids(editor, set())
    _assert_on_stage(editor, node_id, 300.0, 140.0)

    assert editor.undo()
    assert not editor.graph.node_wrappers


def test_create_on_patch_canvas_is_unchanged(editor):
    handler = _visual(editor, PATCH)
    handler.process_node_creation_request(
        NodeCreateRequestEvent(registryKey=_ADD, position={"x": 500.0, "y": 340.0})
    )
    (node_id,) = _new_ids(editor, set())
    _assert_patch(editor, node_id, 500.0, 340.0)


def test_create_from_edge_drop_on_stage_lands_on_stage(editor):
    # Drop-to-create is the same event with a pending connection.
    source = make_node(editor.graph, _ADD, position=(0, 0))
    handler = _visual(editor, STAGE)
    handler._try_auto_wire = MagicMock()  # type: ignore[method-assign]
    pending = {"pin_id": "value_out", "node_id": source.node_id, "pin_dir": "outlet"}
    handler.process_node_creation_request(
        NodeCreateRequestEvent(
            registryKey=_ADD, position={"x": 260.0, "y": 240.0}, pending_connection=pending
        )
    )
    (node_id,) = _new_ids(editor, {source.node_id})
    _assert_on_stage(editor, node_id, 60.0, 40.0, patch=(0.0, 0.0))
    handler._try_auto_wire.assert_called_once()


def _stage_node(editor: Editor, stage: tuple[float, float], patch: tuple[float, float]):
    wrapper = make_node(editor.graph, _ADD, position=patch)
    wrapper.node.props.on_stage = True
    wrapper.node.props.stage_x, wrapper.node.props.stage_y = stage
    return wrapper


def test_create_on_stage_lands_in_the_patch_at_the_same_offset_from_its_siblings(editor):
    _stage_node(editor, (0.0, 0.0), (1000.0, 800.0))
    _stage_node(editor, (100.0, 40.0), (1200.0, 880.0))
    before = set(editor.graph.node_wrappers)

    # Stage centroid (50, 20), patch centroid (1100, 840); new node at stage (150, 120).
    _visual(editor, STAGE).process_node_creation_request(
        NodeCreateRequestEvent(registryKey=_ADD, position={"x": 350.0, "y": 320.0})
    )

    (node_id,) = _new_ids(editor, before)
    _assert_on_stage(editor, node_id, 150.0, 120.0, patch=(1200.0, 940.0))
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_create_on_an_empty_stage_uses_the_patch_viewport_centre(editor):
    make_node(editor.graph, _ADD, position=(10, 10))  # off stage: must not matter
    before = set(editor.graph.node_wrappers)
    _visual(editor, STAGE, viewport_centre=(2000.0, 1500.0)).process_node_creation_request(
        NodeCreateRequestEvent(registryKey=_ADD, position={"x": 500.0, "y": 340.0})
    )
    (node_id,) = _new_ids(editor, before)
    _assert_on_stage(editor, node_id, 300.0, 140.0, patch=(2000.0, 1500.0))


def test_siblings_win_over_the_patch_viewport_centre(editor):
    _stage_node(editor, (0.0, 0.0), (1000.0, 800.0))
    before = set(editor.graph.node_wrappers)
    _visual(editor, STAGE, viewport_centre=(2000.0, 1500.0)).process_node_creation_request(
        NodeCreateRequestEvent(registryKey=_ADD, position={"x": 250.0, "y": 230.0})
    )
    (node_id,) = _new_ids(editor, before)
    _assert_on_stage(editor, node_id, 50.0, 30.0, patch=(1050.0, 830.0))


def test_create_on_an_empty_stage_without_a_patch_canvas_uses_the_all_nodes_centroid(editor):
    make_node(editor.graph, _ADD, position=(100, 100))
    make_node(editor.graph, _ADD, position=(300, 200))
    before = set(editor.graph.node_wrappers)
    _visual(editor, STAGE).process_node_creation_request(
        NodeCreateRequestEvent(registryKey=_ADD, position={"x": 500.0, "y": 340.0})
    )
    (node_id,) = _new_ids(editor, before)
    _assert_on_stage(editor, node_id, 300.0, 140.0, patch=(200.0, 150.0))


def test_patch_canvas_ignores_the_viewport_centre_and_siblings(editor):
    _stage_node(editor, (0.0, 0.0), (1000.0, 800.0))
    before = set(editor.graph.node_wrappers)
    _visual(editor, PATCH, viewport_centre=(2000.0, 1500.0)).process_node_creation_request(
        NodeCreateRequestEvent(registryKey=_ADD, position={"x": 500.0, "y": 340.0})
    )
    (node_id,) = _new_ids(editor, before)
    _assert_patch(editor, node_id, 500.0, 340.0)


# ---------------------------------------------------------------------------
# Paste
# ---------------------------------------------------------------------------


def _paste_event(editor: Editor, ids: list[str], x: float, y: float) -> UserPasteClipboardEvent:
    payload = build_clipboard_payload(editor.graph, ids, [], "s")
    return UserPasteClipboardEvent(canvasX=x, canvasY=y, clipboardText=json.dumps(payload))


def test_paste_on_stage_canvas_lands_on_stage_keeping_relative_layout(editor):
    a = make_node(editor.graph, _ADD, position=(100, 100))
    b = make_node(editor.graph, _ADD, position=(160, 130))
    before = set(editor.graph.node_wrappers)
    event = _paste_event(editor, [a.node_id, b.node_id], 400.0, 300.0)

    _selection(editor, STAGE).process_paste_clipboard(event)

    new_a, new_b = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).posX)
    # No node on stage and no patch canvas: the anchor is the centroid of all nodes, (130, 115).
    _assert_on_stage(editor, new_a, 200.0, 100.0, patch=(130.0, 115.0))
    _assert_on_stage(editor, new_b, 260.0, 130.0, patch=(190.0, 145.0))

    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_paste_on_stage_keeps_relative_layout_in_both_views_anchored_at_the_viewport_centre(editor):
    a = make_node(editor.graph, _ADD, position=(100, 100))
    b = make_node(editor.graph, _ADD, position=(160, 130))
    event = _paste_event(editor, [a.node_id, b.node_id], 400.0, 300.0)
    before = set(editor.graph.node_wrappers)

    _selection(editor, STAGE, viewport_centre=(2000.0, 1500.0)).process_paste_clipboard(event)

    new_a, new_b = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).posX)
    _assert_on_stage(editor, new_a, 200.0, 100.0, patch=(2000.0, 1500.0))
    _assert_on_stage(editor, new_b, 260.0, 130.0, patch=(2060.0, 1530.0))
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_paste_on_stage_canvas_overrides_copied_stage_props(editor):
    a = make_node(editor.graph, _ADD, position=(100, 100))
    props = a.node.props
    props.on_stage = True
    props.stage_x, props.stage_y = 50.0, 70.0
    before = set(editor.graph.node_wrappers)

    _selection(editor, STAGE).process_paste_clipboard(_paste_event(editor, [a.node_id], 400.0, 300.0))

    (new_id,) = _new_ids(editor, before)
    # The one node on stage is the sibling: patch (100, 100) + (stage (200, 100) - stage (50, 70)).
    _assert_on_stage(editor, new_id, 200.0, 100.0, patch=(250.0, 130.0))


def test_paste_on_patch_canvas_is_unchanged(editor):
    a = make_node(editor.graph, _ADD, position=(100, 100))
    before = set(editor.graph.node_wrappers)

    _selection(editor, PATCH).process_paste_clipboard(_paste_event(editor, [a.node_id], 400.0, 300.0))

    (new_id,) = _new_ids(editor, before)
    _assert_patch(editor, new_id, 400.0, 300.0)


def test_stage_position_for_patch_mirrors_the_sibling_offset_and_is_none_on_an_empty_stage(editor):
    assert stage_position_for_patch(editor.graph, (5.0, 5.0)) is None
    _stage_node(editor, (0.0, 0.0), (1000.0, 800.0))
    _stage_node(editor, (100.0, 40.0), (1200.0, 880.0))

    # Stage centroid (50, 20), patch centroid (1100, 840).
    assert stage_position_for_patch(editor.graph, (1150.0, 900.0)) == (100.0, 80.0)


def test_patch_paste_of_an_on_stage_copy_lands_on_stage_by_the_mirrored_centroid_rule(editor):
    a = _stage_node(editor, (0.0, 0.0), (1000.0, 800.0))
    b = _stage_node(editor, (100.0, 40.0), (1200.0, 880.0))
    before = set(editor.graph.node_wrappers)

    # Stage centroid (50, 20), patch centroid (1100, 840): paste point (1150, 900) -> stage (100, 80).
    _selection(editor, PATCH).process_paste_clipboard(_paste_event(editor, [a.node_id], 1150.0, 900.0))

    (new_id,) = _new_ids(editor, before)
    _assert_on_stage(editor, new_id, 100.0, 80.0, patch=(1150.0, 900.0))
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before
    assert b.node.props.on_stage


def test_patch_paste_of_several_on_stage_copies_keeps_their_relative_stage_layout(editor):
    a = _stage_node(editor, (0.0, 0.0), (1000.0, 800.0))
    b = _stage_node(editor, (100.0, 40.0), (1200.0, 880.0))
    before = set(editor.graph.node_wrappers)

    _selection(editor, PATCH).process_paste_clipboard(
        _paste_event(editor, [a.node_id, b.node_id], 1150.0, 900.0)
    )

    new_a, new_b = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).posX)
    _assert_on_stage(editor, new_a, 100.0, 80.0, patch=(1150.0, 900.0))
    _assert_on_stage(editor, new_b, 200.0, 120.0, patch=(1350.0, 980.0))
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_patch_paste_of_an_off_stage_copy_stays_off_stage(editor):
    _stage_node(editor, (0.0, 0.0), (1000.0, 800.0))
    off = make_node(editor.graph, _ADD, position=(100, 100))
    before = set(editor.graph.node_wrappers)

    _selection(editor, PATCH).process_paste_clipboard(_paste_event(editor, [off.node_id], 400.0, 300.0))

    (new_id,) = _new_ids(editor, before)
    _assert_patch(editor, new_id, 400.0, 300.0)


def test_patch_paste_mixing_on_and_off_stage_copies_places_only_the_on_stage_ones(editor):
    a = _stage_node(editor, (0.0, 0.0), (1000.0, 800.0))
    off = make_node(editor.graph, _ADD, position=(1100, 800))
    before = set(editor.graph.node_wrappers)

    _selection(editor, PATCH).process_paste_clipboard(
        _paste_event(editor, [a.node_id, off.node_id], 1000.0, 800.0)
    )

    new_on, new_off = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).posX)
    _assert_on_stage(editor, new_on, 0.0, 0.0, patch=(1000.0, 800.0))
    _assert_patch(editor, new_off, 1100.0, 800.0)
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_patch_paste_anchors_the_stage_copies_on_their_own_patch_corner_not_the_selections(editor):
    a = _stage_node(editor, (0.0, 0.0), (1000.0, 800.0))
    _stage_node(editor, (100.0, 40.0), (1200.0, 880.0))
    off = make_node(editor.graph, _ADD, position=(900, 700))  # holds the selection's top-left
    before = set(editor.graph.node_wrappers)

    # The on-stage copy lands at patch (1300, 1100): stage centroid (50, 20), patch centroid (1100, 840).
    _selection(editor, PATCH).process_paste_clipboard(
        _paste_event(editor, [a.node_id, off.node_id], 1200.0, 1000.0)
    )

    new_off, new_on = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).posX)
    _assert_patch(editor, new_off, 1200.0, 1000.0)
    _assert_on_stage(editor, new_on, 250.0, 280.0, patch=(1300.0, 1100.0))
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_patch_paste_clamps_the_stage_copies_at_the_stage_origin_keeping_their_layout(editor):
    a = _stage_node(editor, (0.0, 0.0), (1000.0, 800.0))
    b = _stage_node(editor, (100.0, 40.0), (1200.0, 880.0))
    before = set(editor.graph.node_wrappers)

    # The mapped corner is stage (-50, 180): x clamps to 0, y stays.
    _selection(editor, PATCH).process_paste_clipboard(
        _paste_event(editor, [a.node_id, b.node_id], 1000.0, 1000.0)
    )

    new_a, new_b = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).posX)
    _assert_on_stage(editor, new_a, 0.0, 180.0, patch=(1000.0, 1000.0))
    _assert_on_stage(editor, new_b, 100.0, 220.0, patch=(1200.0, 1080.0))
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_patch_paste_clamps_both_axes_at_the_stage_origin(editor):
    a = _stage_node(editor, (0.0, 0.0), (1000.0, 800.0))
    _stage_node(editor, (100.0, 40.0), (1200.0, 880.0))
    before = set(editor.graph.node_wrappers)

    # The mapped corner is stage (-250, -120).
    _selection(editor, PATCH).process_paste_clipboard(_paste_event(editor, [a.node_id], 800.0, 700.0))

    (new_id,) = _new_ids(editor, before)
    _assert_on_stage(editor, new_id, 0.0, 0.0, patch=(800.0, 700.0))
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_stage_paste_clamps_the_patch_copies_at_the_patch_origin_keeping_their_layout(editor):
    a = make_node(editor.graph, _ADD, position=(100, 100))
    b = make_node(editor.graph, _ADD, position=(160, 130))
    _stage_node(editor, (60.0, 40.0), (10.0, 100.0))
    before = set(editor.graph.node_wrappers)
    event = _paste_event(editor, [a.node_id, b.node_id], 200.0, 200.0)  # stage (0, 0)

    # The sibling offset maps the patch corner to (-50, 60): x clamps to 0, y stays.
    _selection(editor, STAGE).process_paste_clipboard(event)

    new_a, new_b = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).posX)
    _assert_on_stage(editor, new_a, 0.0, 0.0, patch=(0.0, 60.0))
    _assert_on_stage(editor, new_b, 60.0, 30.0, patch=(60.0, 90.0))
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_stage_paste_left_of_the_stage_origin_lands_at_the_origin(editor):
    a = make_node(editor.graph, _ADD, position=(100, 100))
    before = set(editor.graph.node_wrappers)

    _selection(editor, STAGE).process_paste_clipboard(_paste_event(editor, [a.node_id], 100.0, 340.0))

    (new_id,) = _new_ids(editor, before)
    assert _props(editor, new_id).get_position(STAGE) == (0.0, 140.0)
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_create_on_stage_canvas_left_of_the_origin_clamps_to_the_origin(editor):
    handler = _visual(editor, STAGE)
    handler.process_node_creation_request(
        NodeCreateRequestEvent(registryKey=_ADD, position={"x": 100.0, "y": 340.0})
    )
    (node_id,) = _new_ids(editor, set())
    _assert_on_stage(editor, node_id, 0.0, 140.0)

    assert editor.undo()
    assert not editor.graph.node_wrappers


def test_patch_paste_on_an_empty_stage_uses_next_stage_spot(editor):
    a = make_node(editor.graph, _ADD, position=(100, 100))
    a.node.props.on_stage = True
    a.node.props.stage_x, a.node.props.stage_y = 70.0, 90.0
    event = _paste_event(editor, [a.node_id], 400.0, 300.0)
    a.node.props.on_stage = False  # the stage is empty when the paste lands
    before = set(editor.graph.node_wrappers)

    _selection(editor, PATCH).process_paste_clipboard(event)

    (new_id,) = _new_ids(editor, before)
    assert next_stage_spot(editor.graph, 1)[0] != (40.0, 40.0)  # the copy now occupies the stage
    _assert_on_stage(editor, new_id, 40.0, 40.0, patch=(400.0, 300.0))
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


# ---------------------------------------------------------------------------
# Duplicate
# ---------------------------------------------------------------------------


def test_duplicate_on_stage_canvas_offsets_from_the_originals_stage_position(editor):
    a = make_node(editor.graph, _ADD, position=(900, 900))
    a.node.props.on_stage = True
    a.node.props.stage_x, a.node.props.stage_y = 30.0, 50.0
    before = set(editor.graph.node_wrappers)

    _selection(editor, STAGE).duplicate_selection([a.node_id], [])

    (new_id,) = _new_ids(editor, before)
    _assert_on_stage(
        editor,
        new_id,
        30.0 + DUPLICATE_OFFSET,
        50.0 + DUPLICATE_OFFSET,
        patch=(900.0 + DUPLICATE_OFFSET, 900.0 + DUPLICATE_OFFSET),
    )

    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_duplicate_on_stage_offsets_the_patch_position_from_the_originals_patch_position(editor):
    a = _stage_node(editor, (30.0, 50.0), (900.0, 700.0))
    b = _stage_node(editor, (130.0, 90.0), (1000.0, 760.0))
    before = set(editor.graph.node_wrappers)

    _selection(editor, STAGE, viewport_centre=(5.0, 5.0)).duplicate_selection([a.node_id, b.node_id], [])

    new_a, new_b = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).posX)
    off = DUPLICATE_OFFSET
    _assert_on_stage(editor, new_a, 30.0 + off, 50.0 + off, patch=(900.0 + off, 700.0 + off))
    _assert_on_stage(editor, new_b, 130.0 + off, 90.0 + off, patch=(1000.0 + off, 760.0 + off))


def test_duplicate_in_patch_offsets_the_on_stage_copy_from_the_originals_stage_position(editor):
    a = _stage_node(editor, (30.0, 50.0), (900.0, 700.0))
    b = _stage_node(editor, (130.0, 90.0), (1000.0, 760.0))
    before = set(editor.graph.node_wrappers)

    _selection(editor, PATCH).duplicate_selection([a.node_id, b.node_id], [])

    new_a, new_b = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).posX)
    off = DUPLICATE_OFFSET
    _assert_on_stage(editor, new_a, 30.0 + off, 50.0 + off, patch=(900.0 + off, 700.0 + off))
    _assert_on_stage(editor, new_b, 130.0 + off, 90.0 + off, patch=(1000.0 + off, 760.0 + off))
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_duplicate_in_patch_mixing_on_and_off_stage_places_only_the_on_stage_copy(editor):
    a = _stage_node(editor, (30.0, 50.0), (900.0, 700.0))
    off = make_node(editor.graph, _ADD, position=(400, 300))
    before = set(editor.graph.node_wrappers)

    _selection(editor, PATCH).duplicate_selection([a.node_id, off.node_id], [])

    new_off, new_on = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).posX)
    d = DUPLICATE_OFFSET
    _assert_patch(editor, new_off, 400.0 + d, 300.0 + d)
    _assert_on_stage(editor, new_on, 30.0 + d, 50.0 + d, patch=(900.0 + d, 700.0 + d))
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_duplicate_on_patch_canvas_is_unchanged(editor):
    a = make_node(editor.graph, _ADD, position=(100, 100))
    before = set(editor.graph.node_wrappers)

    _selection(editor, PATCH).duplicate_selection([a.node_id], [])

    (new_id,) = _new_ids(editor, before)
    _assert_patch(editor, new_id, 100.0 + DUPLICATE_OFFSET, 100.0 + DUPLICATE_OFFSET)


def test_duplicate_on_stage_canvas_clamps_a_legacy_negative_patch_corner(editor):
    # Legacy originals sit above and left of the patch origin: the copy's patch corner is clamped
    # to (0, 0), the pair keeps its relative layout, and one undo removes both.
    a = _stage_node(editor, (30.0, 50.0), (-100.0, -80.0))
    b = _stage_node(editor, (130.0, 90.0), (-40.0, -50.0))
    before = set(editor.graph.node_wrappers)

    _selection(editor, STAGE).duplicate_selection([a.node_id, b.node_id], [])

    new_a, new_b = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).get_position(STAGE)[0])
    pa, pb = _props(editor, new_a).get_position(PATCH), _props(editor, new_b).get_position(PATCH)
    assert (min(pa[0], pb[0]), min(pa[1], pb[1])) == (0.0, 0.0)
    assert (pb[0] - pa[0], pb[1] - pa[1]) == (60.0, 30.0)
    assert _props(editor, new_a).get_position(STAGE) == (30.0 + DUPLICATE_OFFSET, 50.0 + DUPLICATE_OFFSET)
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


def test_duplicate_in_patch_clamps_a_legacy_negative_stage_corner(editor):
    # Legacy on-stage originals at negative stage numbers: the copies' stage corner is clamped to
    # (0, 0) with the relative stage layout kept, and one undo removes both.
    a = _stage_node(editor, (-60.0, -40.0), (900.0, 700.0))
    b = _stage_node(editor, (-10.0, -20.0), (1000.0, 760.0))
    before = set(editor.graph.node_wrappers)

    _selection(editor, PATCH).duplicate_selection([a.node_id, b.node_id], [])

    new_a, new_b = sorted(_new_ids(editor, before), key=lambda i: _props(editor, i).posX)
    sa, sb = _props(editor, new_a).get_position(STAGE), _props(editor, new_b).get_position(STAGE)
    assert (min(sa[0], sb[0]), min(sa[1], sb[1])) == (0.0, 0.0)
    assert (sb[0] - sa[0], sb[1] - sa[1]) == (50.0, 20.0)
    assert _props(editor, new_a).get_position(PATCH) == (900.0 + DUPLICATE_OFFSET, 700.0 + DUPLICATE_OFFSET)
    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


# ---------------------------------------------------------------------------
# Split an edge with a reroute
# ---------------------------------------------------------------------------


def _edge(editor: Editor) -> str:
    source = make_node(editor.graph, _ADD, position=(0, 0))
    sink = make_node(editor.graph, _ADD, position=(300, 0))
    edge = editor.graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    assert edge is not None
    return edge.edge_id


@pytest.mark.parametrize("channel", [STAGE, PATCH], ids=["stage", "patch"])
def test_split_with_reroute_places_the_reroute_per_channel(editor, channel):
    edge_id = _edge(editor)
    before = set(editor.graph.node_wrappers)

    _visual(editor, channel).process_split_edge_with_reroute(
        SplitEdgeWithRerouteEvent(edge_id=edge_id, position={"x": 350.0, "y": 240.0})
    )

    (reroute_id,) = _new_ids(editor, before)
    if channel.stage:
        _assert_on_stage(editor, reroute_id, 150.0, 40.0, patch=(150.0, 0.0))
    else:
        _assert_patch(editor, reroute_id, 350.0, 240.0)

    assert editor.undo()
    assert set(editor.graph.node_wrappers) == before


# ---------------------------------------------------------------------------
# Collapse to Group / Expand: the card is a new node, the interior keeps its stage props
# ---------------------------------------------------------------------------

_CARD = "haywire-core:node:GraphNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"


def _stage_state(wrapper) -> tuple[bool, float, float]:
    p = wrapper.node.props
    return (p.on_stage, p.stage_x, p.stage_y)


def _collapse_fixture(editor: Editor):
    on = make_node(editor.graph, _ADD, position=(0, 0))
    off = make_node(editor.graph, _ADD, position=(200, 0))
    on.node.props.on_stage = True
    on.node.props.stage_x, on.node.props.stage_y = 30.0, 50.0
    editor.graph.create_edge_wrapper(on.node_id, "result", off.node_id, "value_a")
    card_id, reason = editor.collapse_to_group(
        node_ids=[on.node_id, off.node_id],
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
    )
    assert reason is None, reason
    assert card_id is not None
    return on, off, card_id


def _interior(editor: Editor, card_id: str, node_id: str):
    card = editor.graph.get_node_wrapper(card_id)
    assert card is not None
    sub = editor.graph.get_subgraph(card.node.subgraph_key)  # type: ignore[attr-defined]
    assert sub is not None
    wrapper = sub.get_node_wrapper(node_id)
    assert wrapper is not None
    return wrapper


def test_collapse_to_group_lands_the_card_off_stage_and_keeps_interior_stage_props(editor):
    on, off, card_id = _collapse_fixture(editor)

    card = editor.graph.get_node_wrapper(card_id)
    assert card is not None
    assert card.node.props.on_stage is False
    assert _stage_state(_interior(editor, card_id, on.node_id)) == (True, 30.0, 50.0)
    assert _stage_state(_interior(editor, card_id, off.node_id))[0] is False


def test_undo_of_collapse_restores_the_nodes_with_their_stage_props(editor):
    on, off, card_id = _collapse_fixture(editor)
    assert editor.undo()

    assert editor.graph.get_node_wrapper(card_id) is None
    restored_on = editor.graph.get_node_wrapper(on.node_id)
    restored_off = editor.graph.get_node_wrapper(off.node_id)
    assert restored_on is not None
    assert restored_off is not None
    assert _stage_state(restored_on) == (True, 30.0, 50.0)
    assert restored_off.node.props.on_stage is False


def test_expand_restores_the_interior_with_its_stage_props(editor):
    on, off, card_id = _collapse_fixture(editor)
    assert editor.expand_group(card_id)

    assert editor.graph.get_node_wrapper(card_id) is None
    expanded_on = editor.graph.get_node_wrapper(on.node_id)
    expanded_off = editor.graph.get_node_wrapper(off.node_id)
    assert expanded_on is not None
    assert expanded_off is not None
    assert _stage_state(expanded_on) == (True, 30.0, 50.0)
    assert expanded_off.node.props.on_stage is False
