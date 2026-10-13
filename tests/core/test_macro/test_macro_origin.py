"""The origin a detached placement records on its interior."""

from unittest.mock import MagicMock

import pytest

from tests.conftest import make_node
from tests.core.test_macro.test_detach_placement import (
    _CARD,
    _MACRO,
    _PRINT,
    _detach,
    _editor,
    _place,
    macro_folder as macro_folder,
)

pytestmark = pytest.mark.integration


def _definition(graph, card_id):
    return graph.get_node_wrapper(card_id).node.resolve_definition()


def _ctx(active_node):
    from haybale_graph_editor.state.edit_state import EditState

    edit = MagicMock()
    edit.active_node = active_node
    edit.selected_nodes = set()
    ctx = MagicMock()
    ctx.data = {EditState: edit}
    return ctx


@pytest.mark.usefixtures("macro_folder")
def test_detach_records_the_origin(graph_with_library_system, library_system):
    from haywire.core.macro.origin import MacroOrigin

    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)

    card_id, _ = _detach(editor, placement_id)

    template = library_system.get_macro_registry().template(_MACRO)
    assert _definition(graph, card_id).origin == MacroOrigin(_MACRO, template.content_hash)


@pytest.mark.usefixtures("macro_folder")
def test_undo_of_detach_clears_the_origin(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)
    card_id, _ = _detach(editor, placement_id)
    key = graph.get_node_wrapper(card_id).node.subgraph_key

    editor.undo()

    assert graph.get_subgraph(key) is None
    interior = graph.get_node_wrapper(placement_id).node.resolve_definition()
    assert interior.origin is None


@pytest.mark.usefixtures("macro_folder")
def test_the_origin_survives_save_and_load(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)
    card_id, _ = _detach(editor, placement_id)
    definition = _definition(graph, card_id)

    data = definition.to_dict()
    from haywire.core.graph.subgraph import SubgraphDefinition

    fresh = SubgraphDefinition(key="fresh")
    fresh.load_from_dict(data)

    assert fresh.origin == definition.origin
    assert fresh.origin is not None


def test_a_plain_group_has_no_origin_key(graph_with_library_system, library_system):
    graph = graph_with_library_system
    a, b = make_node(graph, _PRINT), make_node(graph, _PRINT)
    graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
    editor = _editor(graph, library_system)
    card_id, _ = editor.collapse_to_group(
        node_ids=[a.node_id, b.node_id],
        card_registry_key=_CARD,
        input_registry_key="haywire-core:node:SubgraphInputNode",
        output_registry_key="haywire-core:node:SubgraphOutputNode",
    )

    definition = _definition(graph, card_id)

    assert "origin" not in definition.to_dict()
    assert definition.origin is None


@pytest.mark.usefixtures("macro_folder")
def test_is_modified_instance_polls(graph_with_library_system, library_system):
    from haybale_graph_editor.panels._gating import is_modified_instance

    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)
    placement = graph.get_node_wrapper(placement_id)
    plain = make_node(graph, _PRINT)
    assert is_modified_instance(_ctx(placement)) is False
    assert is_modified_instance(_ctx(plain)) is False

    card_id, _ = _detach(editor, placement_id)
    assert is_modified_instance(_ctx(graph.get_node_wrapper(card_id))) is True
    assert is_modified_instance(_ctx(None)) is False


def test_a_plain_group_is_not_a_modified_instance(graph_with_library_system, library_system):
    from haybale_graph_editor.panels._gating import is_modified_instance

    graph = graph_with_library_system
    a, b = make_node(graph, _PRINT), make_node(graph, _PRINT)
    graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
    editor = _editor(graph, library_system)
    card_id, _ = editor.collapse_to_group(
        node_ids=[a.node_id, b.node_id],
        card_registry_key=_CARD,
        input_registry_key="haywire-core:node:SubgraphInputNode",
        output_registry_key="haywire-core:node:SubgraphOutputNode",
    )

    assert is_modified_instance(_ctx(graph.get_node_wrapper(card_id))) is False


@pytest.mark.usefixtures("macro_folder")
def test_count_placements_spans_graphs_and_interiors(graph_with_library_system, library_system):
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.core.macro.source import count_placements

    first = graph_with_library_system
    make_node(first, _MACRO)
    a, b = make_node(first, _PRINT), make_node(first, _PRINT)
    first.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
    card_id, _ = _editor(first, library_system).collapse_to_group(
        node_ids=[a.node_id, b.node_id],
        card_registry_key=_CARD,
        input_registry_key="haywire-core:node:SubgraphInputNode",
        output_registry_key="haywire-core:node:SubgraphOutputNode",
    )
    make_node(_definition(first, card_id), _MACRO)
    second = BaseGraph(filestem="second", validation_scheduler=SyncScheduler())
    make_node(second, _MACRO)
    empty = BaseGraph(filestem="empty", validation_scheduler=SyncScheduler())

    assert count_placements([first, second, empty], _MACRO) == (3, 2)
    assert count_placements([empty], _MACRO) == (0, 0)
    assert count_placements([first], "testlib:macro:Other") == (0, 0)


@pytest.mark.usefixtures("macro_folder")
def test_clone_to_library_never_polls_on_a_modified_instance(graph_with_library_system, library_system):
    """Both rows sit at order 39 on the selection menu; they never show together."""
    from haybale_graph_editor.panels._gating import is_cloneable_selection, is_modified_instance

    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)
    card_id, _ = _detach(editor, placement_id)
    card = graph.get_node_wrapper(card_id)
    ctx = _ctx(card)
    ctx.data[next(iter(ctx.data))].selected_nodes = {card_id}

    assert is_modified_instance(ctx) is True
    assert is_cloneable_selection(ctx) is False


def test_a_malformed_origin_does_not_fail_the_load(caplog):
    import logging

    from haywire.core.graph.subgraph import SubgraphDefinition

    fresh = SubgraphDefinition(key="fresh")
    data = {**SubgraphDefinition(key="other").to_dict(), "origin": {"key": "only-a-key"}}
    with caplog.at_level(logging.WARNING):
        assert fresh.load_from_dict(data) is True

    assert fresh.origin is None
    assert any("malformed macro origin" in r.getMessage() for r in caplog.records)


@pytest.mark.usefixtures("macro_folder")
def test_a_failing_registry_still_detaches_with_a_warning(
    graph_with_library_system, library_system, caplog, monkeypatch
):
    import logging

    from haywire.core.macro import source

    def _boom(key):
        raise ValueError("registry broke")

    monkeypatch.setattr(source, "macro_template", _boom)
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)

    with caplog.at_level(logging.WARNING):
        card_id, refusal = _detach(editor, placement_id)

    assert card_id is not None, refusal
    assert _definition(graph, card_id).origin is None
    record = next(r for r in caplog.records if "Could not look up macro" in r.getMessage())
    assert record.exc_info is not None
