"""Stacking order: the ``z``/``stage_z`` fields, the order a view paints in, the four verbs."""

from __future__ import annotations

import pytest

from haywire.core.graph.editor import Editor
from haywire.core.graph.stacking import Restack, stacking_order
from haywire.core.graph.types import ValidationResult
from haywire.core.node.layout import PATCH, STAGE

pytestmark = pytest.mark.integration


def _key() -> str:
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return TestPrintNode.class_identity.registry_key


def _editor(graph, library_system) -> Editor:
    return Editor(graph, library_system.get_node_factory())


def _collect(graph) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    graph._validation.subscribe(results.append)
    return results


def _node(graph, x: float = 0.0, y: float = 0.0):
    return graph.create_node_wrapper(_key(), position=(x, y))


def _four(graph):
    """Nodes ``a, b, c, d``, made in that order, all at z 0; returned with their ids."""
    wrappers = [_node(graph, 0, 100 * i) for i in range(4)]
    return wrappers, [w.node_id for w in wrappers]


def _zs(wrappers, channel=PATCH) -> list[int]:
    return [getattr(w.node.props, channel.z) for w in wrappers]


# ---------------------------------------------------------------------------
# Fields and order
# ---------------------------------------------------------------------------


def test_channels_name_their_stacking_field():
    assert PATCH.z == "z"
    assert STAGE.z == "stage_z"


def test_an_untouched_graph_saves_no_stacking_fields(graph_with_library_system):
    wrapper = _node(graph_with_library_system)
    values = wrapper.serialize()["node_data"]["props"]["values"]
    assert "z" not in values
    assert "stage_z" not in values


def test_stacking_order_sorts_by_z_then_graph_order(graph_with_library_system):
    graph = graph_with_library_system
    (_, _, c, _), (a, b, c_id, d) = _four(graph)
    c.node.props.z = 5
    assert stacking_order(graph, PATCH) == [a, b, d, c_id]


def test_stage_order_holds_only_on_stage_nodes(graph_with_library_system):
    graph = graph_with_library_system
    (_, wb, _, wd), (_, b, _, d) = _four(graph)
    wb.node.props.on_stage = True
    wd.node.props.on_stage = True
    assert stacking_order(graph, STAGE) == [b, d]


# ---------------------------------------------------------------------------
# Verbs
# ---------------------------------------------------------------------------


def test_bring_to_front_writes_only_the_moving_nodes(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    (wa, wb, wc, wd), (a, b, c, d) = _four(graph)

    assert editor.restack_nodes([a, c], Restack.FRONT)
    assert stacking_order(graph, PATCH) == [b, d, a, c]
    assert (wa.node.props.z, wc.node.props.z) == (1, 2)
    assert not wb.node.props._is_locally_set("z")
    assert not wd.node.props._is_locally_set("z")


def test_send_to_back_goes_below_zero_writing_only_the_moving_node(
    graph_with_library_system, library_system
):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    (wa, wb, wc, wd), (a, b, c, d) = _four(graph)

    assert editor.restack_nodes([d], Restack.BACK)

    assert stacking_order(graph, PATCH) == [d, a, b, c]
    assert wd.node.props.z == -1
    assert not any(w.node.props._is_locally_set("z") for w in (wa, wb, wc))


def test_front_past_the_limit_renumbers_as_ranks(graph_with_library_system, library_system):
    from haywire.core.graph.stacking import _Z_LIMIT

    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    (wa, wb, wc, wd), (a, b, c, d) = _four(graph)
    wd.node.props.z = _Z_LIMIT

    assert editor.restack_nodes([a], Restack.FRONT)

    assert stacking_order(graph, PATCH) == [b, c, d, a]
    assert _zs([wb, wc, wd, wa]) == [0, 1, 2, 3]


def test_a_plain_string_names_the_restack_and_an_unknown_one_raises(graph_with_library_system):
    from haywire.core.graph.stacking import restacked

    graph = graph_with_library_system
    _, (a, _b, _c, _d) = _four(graph)

    assert restacked(graph, [a], "front", PATCH) == restacked(graph, [a], Restack.FRONT, PATCH)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="top"):
        restacked(graph, [a], "top", PATCH)  # type: ignore[arg-type]


def test_send_to_back_keeps_the_selections_order(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    _, (a, b, c, d) = _four(graph)

    assert editor.restack_nodes([d, b], Restack.BACK)
    assert stacking_order(graph, PATCH) == [b, d, a, c]


def test_forward_steps_one_node(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    wrappers, (a, b, c, d) = _four(graph)

    assert editor.restack_nodes([a], Restack.FORWARD)
    assert stacking_order(graph, PATCH) == [b, a, c, d]

    assert editor.history_manager.undo()
    assert _zs(wrappers) == [0, 0, 0, 0]
    assert editor.restack_nodes([a, b], Restack.FORWARD)
    assert stacking_order(graph, PATCH) == [c, a, b, d]


def test_backward_steps_one_node(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    _, (a, b, c, d) = _four(graph)

    assert editor.restack_nodes([d], Restack.BACKWARD)
    assert stacking_order(graph, PATCH) == [a, b, d, c]


def test_forward_at_the_top_records_nothing(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    _, (_, _, _, d) = _four(graph)

    assert editor.restack_nodes([d], Restack.FORWARD) is False
    assert not editor.history_manager.can_undo()


def test_unknown_and_off_channel_ids_are_ignored(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    _, (a, _, _, _) = _four(graph)

    assert editor.restack_nodes(["missing", a], Restack.FRONT, STAGE) is False


def test_a_restack_is_one_undo_step_and_marks_unsaved(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    wrappers, (a, b, c, d) = _four(graph)
    results = _collect(graph)

    assert editor.restack_nodes([a], Restack.FRONT)
    assert any(r.requires_save() for r in results)

    assert editor.history_manager.undo()
    assert stacking_order(graph, PATCH) == [a, b, c, d]
    assert _zs(wrappers) == [0, 0, 0, 0]

    assert editor.history_manager.redo()
    assert stacking_order(graph, PATCH) == [b, c, d, a]


def test_a_stage_restack_writes_stage_z_only(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    wrappers, (a, b, _, _) = _four(graph)
    for w in wrappers[:2]:
        w.node.props.on_stage = True

    assert editor.restack_nodes([a], Restack.FRONT, STAGE)
    assert stacking_order(graph, STAGE) == [b, a]
    assert _zs(wrappers, STAGE)[:2] == [1, 0]
    assert _zs(wrappers) == [0, 0, 0, 0]


# ---------------------------------------------------------------------------
# New nodes land on top
# ---------------------------------------------------------------------------


def test_a_created_node_lands_on_top(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    _, (a, _, _, _) = _four(graph)

    fresh = editor.create_wrapper(_key(), (0.0, 0.0))
    assert fresh is not None
    assert fresh.node.props.z == 1
    assert stacking_order(graph, PATCH)[-1] == fresh.node_id

    assert editor.restack_nodes([a], Restack.FRONT)
    assert graph.node_wrappers[a].node.props.z == 2
    newer = editor.create_wrapper(_key(), (0.0, 0.0))
    assert newer is not None
    assert newer.node.props.z == 3
    assert stacking_order(graph, PATCH)[-1] == newer.node_id


def test_a_node_made_in_the_stage_view_lands_on_top_in_both_views(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    wrappers, _ = _four(graph)
    for w in wrappers:
        w.node.props.on_stage = True

    made = editor.create_wrapper(_key(), STAGE.to_canvas(40.0, 40.0), STAGE)
    assert made is not None
    assert stacking_order(graph, PATCH)[-1] == made.node_id
    assert stacking_order(graph, STAGE)[-1] == made.node_id


def test_redo_of_a_create_keeps_its_z(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    _four(graph)
    made = editor.create_wrapper(_key(), (0.0, 0.0))
    assert made is not None
    z = made.node.props.z

    assert editor.history_manager.undo()
    assert editor.history_manager.redo()
    assert graph.node_wrappers[made.node_id].node.props.z == z
    assert stacking_order(graph, PATCH)[-1] == made.node_id


def test_paste_lands_on_top_keeping_relative_order(graph_with_library_system, library_system):
    from haywire.core.graph.clipboard import build_clipboard_payload

    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    wrappers, ids = _four(graph)
    for w in wrappers:
        w.node.props.on_stage = True
    p, q = wrappers[0], wrappers[1]
    p.node.props.stage_z, q.node.props.stage_z = 2, 1
    p.node.props.z, q.node.props.z = 2, 1

    payload = build_clipboard_payload(graph, [p.node_id, q.node_id], [], "s")
    pasted = editor.paste_clipboard(payload, *STAGE.to_canvas(300.0, 300.0), channel=STAGE)
    assert pasted is not None
    new_ids, _ = pasted
    assert len(new_ids) == 2

    for channel in (PATCH, STAGE):
        order = stacking_order(graph, channel)
        assert set(order[-2:]) == set(new_ids), channel.name
        # The copy of p (above q in the source) stays above the copy of q.
        top = graph.node_wrappers[order[-1]].node.props
        below = graph.node_wrappers[order[-2]].node.props
        assert getattr(top, channel.z) > getattr(below, channel.z)
    copy_of_p = new_ids[0]
    assert stacking_order(graph, STAGE)[-1] == copy_of_p


def test_add_to_stage_lands_on_top_of_the_stage(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    wrappers, (_, _, _, d) = _four(graph)
    for w in wrappers[:3]:
        w.node.props.on_stage = True
    wrappers[2].node.props.stage_z = 6
    wrappers[3].node.props.stage_z = 2

    assert editor.add_to_stage([d])
    assert wrappers[3].node.props.stage_z == 7
    assert stacking_order(graph, STAGE)[-1] == d

    assert editor.history_manager.undo()
    assert wrappers[3].node.props.stage_z == 2


def test_expanding_a_group_keeps_its_contents_stacking_order(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    wrappers, (a, b, c, d) = _four(graph)
    for w in wrappers:
        w.node.props.on_stage = True
    assert editor.restack_nodes([a], Restack.FRONT)  # order b, c, d, a
    assert editor.restack_nodes([b], Restack.FRONT, STAGE)  # stage order a, c, d, b

    card_id, _ = editor.collapse_to_group(
        [a, b],
        "haywire-core:node:GraphNode",
        "haywire-core:node:SubgraphInputNode",
        "haywire-core:node:SubgraphOutputNode",
    )
    assert card_id is not None
    assert editor.expand_group(card_id)

    patch_order = [n for n in stacking_order(graph, PATCH) if n in (a, b)]
    stage_order = [n for n in stacking_order(graph, STAGE) if n in (a, b)]
    assert patch_order == [b, a]
    assert stage_order == [a, b]
    # Lifted out on top of what stayed in the host.
    assert set(stacking_order(graph, PATCH)[-2:]) == {a, b}
