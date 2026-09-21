"""Detaching a placement: the card stops tracking its template.

Not the inverse of promotion. Promoting consumed the only card standing for a
Subgraph; detaching acts on one placement of possibly many, and leaves both the
macro file and every other placement alone.
"""

import json

import pytest

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_PRINT = "haybale-testing:node:TestPrintNode"
_CARD = "haywire-core:node:GraphNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_MACRO = "testlib:macro:Blur"


def _identity(folder_path):
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(
        label="testlib", name="testlib", folder_path=str(folder_path), module_name="testlib"
    )


def _document():
    return {
        "format_version": 1,
        "meta": {"description": ""},
        "nodes": {
            "b_in": {"node_id": "b_in", "registry_key": _INPUT, "position": [0, 0]},
            "b_out": {"node_id": "b_out", "registry_key": _OUTPUT, "position": [200, 0]},
            "inner": {"node_id": "inner", "registry_key": _PRINT, "position": [100, 0]},
        },
        "edges": {},
        "variables": {},
        "props": {},
        "subgraphs": {},
    }


@pytest.fixture
def macro_folder(tmp_path, library_system):
    (tmp_path / "Blur.hwm").write_text(json.dumps(_document()))
    registry = library_system.get_macro_registry()
    identity = _identity(tmp_path)
    registry.add_folder(str(tmp_path), identity)
    try:
        yield tmp_path
    finally:
        registry.remove_folder(str(tmp_path), identity)


def _editor(graph, library_system):
    from haywire.core.graph.editor import Editor

    return Editor(graph, library_system.get_node_factory())


def _place(graph, library_system):
    """One placement of the macro, and an editor over its graph."""
    card = make_node(graph, _MACRO)
    graph.force_validation()
    return _editor(graph, library_system), card.node_id


def _detach(editor, node_id):
    return editor.detach_placement_from_macro(node_id, _CARD)


def test_the_placement_becomes_a_group_card(graph_with_library_system, library_system, macro_folder):
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)

    card_id, refusal = _detach(editor, placement_id)

    assert refusal is None
    assert graph.get_node_wrapper(placement_id) is None
    card = graph.get_node_wrapper(card_id)
    assert card is not None
    assert card.registry_key == _CARD


def test_the_interior_survives_the_swap(graph_with_library_system, library_system, macro_folder):
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)
    before = len(graph.get_node_wrapper(placement_id).node.resolve_definition().node_wrappers)

    card_id, _ = _detach(editor, placement_id)

    interior = graph.get_node_wrapper(card_id).node.resolve_definition()
    assert interior is not None
    assert len(interior.node_wrappers) == before


def test_the_interior_is_now_serialized_into_the_host(
    graph_with_library_system, library_system, macro_folder
):
    """Clearing template_key is the whole conversion: the host file owns it now."""
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)
    assert graph.to_dict()["subgraphs"] == {}

    card_id, _ = _detach(editor, placement_id)

    key = graph.get_node_wrapper(card_id).node.subgraph_key
    assert key in graph.to_dict()["subgraphs"]


def test_the_definition_no_longer_carries_a_template_key(
    graph_with_library_system, library_system, macro_folder
):
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)

    card_id, _ = _detach(editor, placement_id)

    interior = graph.get_node_wrapper(card_id).node.resolve_definition()
    assert interior.template_key is None


def test_the_card_lands_where_the_placement_was(graph_with_library_system, library_system, macro_folder):
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)
    was = graph.get_node_wrapper(placement_id).node.props.get_position()

    card_id, _ = _detach(editor, placement_id)

    assert graph.get_node_wrapper(card_id).node.props.get_position() == was


def test_the_macro_file_is_untouched(graph_with_library_system, library_system, macro_folder):
    """Detaching one card is not deleting the macro."""
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)

    _detach(editor, placement_id)

    assert (macro_folder / "Blur.hwm").exists()


def test_the_template_stays_registered(graph_with_library_system, library_system, macro_folder):
    """Other graphs may still place it, so the key must keep resolving."""
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)

    _detach(editor, placement_id)

    assert library_system.get_macro_registry().template(_MACRO) is not None


def test_a_sibling_placement_keeps_tracking_the_template(
    graph_with_library_system, library_system, macro_folder
):
    """Detaching one card must not reach the others."""
    graph = graph_with_library_system
    editor, first_id = _place(graph, library_system)
    second = make_node(graph, _MACRO)
    graph.force_validation()

    _detach(editor, first_id)

    sibling = graph.get_node_wrapper(second.node_id)
    assert sibling is not None
    assert sibling.registry_key == _MACRO
    assert sibling.node.resolve_definition().template_key == _MACRO


def test_undo_restores_the_placement(graph_with_library_system, library_system, macro_folder):
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)

    card_id, _ = _detach(editor, placement_id)
    editor.undo()

    assert graph.get_node_wrapper(card_id) is None
    restored = graph.get_node_wrapper(placement_id)
    assert restored is not None
    assert restored.registry_key == _MACRO


def test_undo_makes_the_interior_a_template_interior_again(
    graph_with_library_system, library_system, macro_folder
):
    """The mark goes back on, so the host stops serializing it."""
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)

    _detach(editor, placement_id)
    editor.undo()

    assert graph.to_dict()["subgraphs"] == {}
    interior = graph.get_node_wrapper(placement_id).node.resolve_definition()
    assert interior.template_key == _MACRO


def test_a_group_cannot_be_detached(graph_with_library_system, library_system):
    """It is already its own; there is no template to stop tracking."""
    graph = graph_with_library_system
    a, b = make_node(graph, _PRINT), make_node(graph, _PRINT)
    graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
    editor = _editor(graph, library_system)
    card_id, reason = editor.collapse_to_group(
        node_ids=[a.node_id, b.node_id],
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
    )
    assert reason is None

    detached_id, refusal = _detach(editor, card_id)

    assert detached_id is None
    assert refusal is not None


def test_a_plain_node_cannot_be_detached(graph_with_library_system, library_system):
    graph = graph_with_library_system
    plain = make_node(graph, _PRINT)
    editor = _editor(graph, library_system)

    detached_id, refusal = _detach(editor, plain.node_id)

    assert detached_id is None
    assert refusal is not None
