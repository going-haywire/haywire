"""Swapping a Group's card for a placement — the undoable half of promotion.

``write_macro_file`` puts the document on disk; this is what exchanges the
cards. One undoable unit: undo restores the Group and leaves the file, because
a macro other graphs may already place must not vanish with one undo.
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
    """A macro document holding the boundary pair and one interior node."""
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
    """One macro registered, removed again so the next test starts clean."""
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


def _group_card(graph, library_system, label="Group"):
    """Collapse two connected nodes into a Group and return its card id."""
    a, b = make_node(graph, _PRINT), make_node(graph, _PRINT)
    graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
    editor = _editor(graph, library_system)
    card_id, reason = editor.collapse_to_group(
        node_ids=[a.node_id, b.node_id],
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
        label=label,
    )
    assert reason is None, reason
    return editor, card_id


def test_the_card_is_replaced_by_a_placement(graph_with_library_system, library_system, macro_folder):
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)

    placement_id, refusal = editor.promote_to_macro(card_id, _MACRO)

    assert refusal is None
    assert graph.get_node_wrapper(card_id) is None
    placement = graph.get_node_wrapper(placement_id)
    assert placement is not None
    assert placement.registry_key == _MACRO


def test_the_placement_lands_where_the_card_was(graph_with_library_system, library_system, macro_folder):
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)
    was = graph.get_node_wrapper(card_id).node.props.get_position()

    placement_id, _ = editor.promote_to_macro(card_id, _MACRO)

    assert graph.get_node_wrapper(placement_id).node.props.get_position() == was


def test_the_groups_definition_is_dropped(graph_with_library_system, library_system, macro_folder):
    """The Group's Subgraph served that one card; the placement builds its own."""
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)
    group_key = graph.get_node_wrapper(card_id).node.subgraph_key

    editor.promote_to_macro(card_id, _MACRO)

    assert graph.get_subgraph(group_key) is None


def test_the_placement_instantiates_its_own_interior(
    graph_with_library_system, library_system, macro_folder
):
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)

    placement_id, _ = editor.promote_to_macro(card_id, _MACRO)

    interior = graph.get_node_wrapper(placement_id).node.resolve_definition()
    assert interior is not None
    assert len(interior.node_wrappers) == len(_document()["nodes"])


def test_the_placements_interior_is_not_the_groups(graph_with_library_system, library_system, macro_folder):
    """It comes from the template, keyed by the placement's own node id."""
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)
    group_key = graph.get_node_wrapper(card_id).node.subgraph_key

    placement_id, _ = editor.promote_to_macro(card_id, _MACRO)

    assert graph.get_node_wrapper(placement_id).node.subgraph_key != group_key


def test_undo_restores_the_group(graph_with_library_system, library_system, macro_folder):
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)
    group_key = graph.get_node_wrapper(card_id).node.subgraph_key

    placement_id, _ = editor.promote_to_macro(card_id, _MACRO)
    editor.undo()

    assert graph.get_node_wrapper(placement_id) is None
    assert graph.get_node_wrapper(card_id) is not None
    assert graph.get_subgraph(group_key) is not None


def test_undo_does_not_reverse_the_collapse_before_it(
    graph_with_library_system, library_system, macro_folder
):
    """Auto-grouping would fold the swap into the collapse without a fence.

    One undo then took back the Group the user had just made, which they never
    asked to reverse.
    """
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)

    editor.promote_to_macro(card_id, _MACRO)
    editor.undo()

    assert graph.get_node_wrapper(card_id) is not None


def test_undo_takes_the_placements_interior_with_it(graph_with_library_system, library_system, macro_folder):
    """The interior is built in post_init, so nothing else would drop it."""
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)

    placement_id, _ = editor.promote_to_macro(card_id, _MACRO)
    interior_key = graph.get_node_wrapper(placement_id).node.subgraph_key
    editor.undo()

    assert graph.get_subgraph(interior_key) is None


def test_redo_rebuilds_the_placements_interior(graph_with_library_system, library_system, macro_folder):
    """A redo re-adds the existing wrapper, so post_init does not run again."""
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)

    placement_id, _ = editor.promote_to_macro(card_id, _MACRO)
    editor.undo()
    editor.redo()

    placement = graph.get_node_wrapper(placement_id)
    assert placement is not None
    interior = placement.node.resolve_definition()
    assert interior is not None
    assert len(interior.node_wrappers) == len(_document()["nodes"])


def test_the_placements_interior_is_never_serialized(
    graph_with_library_system, library_system, macro_folder
):
    """ADR 0038: the host file carries the card, never its interior."""
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)

    placement_id, _ = editor.promote_to_macro(card_id, _MACRO)
    interior_key = graph.get_node_wrapper(placement_id).node.subgraph_key

    assert interior_key not in graph.to_dict().get("subgraphs", {})


def test_undo_leaves_the_macro_file(graph_with_library_system, library_system, macro_folder):
    """A file other graphs may already place is not the undo stack's to remove."""
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)

    editor.promote_to_macro(card_id, _MACRO)
    editor.undo()

    assert (macro_folder / "Blur.hwm").exists()


def test_the_cards_label_carries_over(graph_with_library_system, library_system, macro_folder):
    """A renamed Group keeps its name; the macro's own is only the fallback."""
    graph = graph_with_library_system
    editor, card_id = _group_card(graph, library_system)
    graph.get_node_wrapper(card_id).node.props.label = "My Blur"
    graph.force_validation()

    placement_id, _ = editor.promote_to_macro(card_id, _MACRO)

    assert graph.get_node_wrapper(placement_id).node.display_label == "My Blur"


def test_a_node_that_is_not_a_group_is_refused(graph_with_library_system, library_system, macro_folder):
    graph = graph_with_library_system
    plain = make_node(graph, _PRINT)
    editor = _editor(graph, library_system)

    placement_id, refusal = editor.promote_to_macro(plain.node_id, _MACRO)

    assert placement_id is None
    assert refusal is not None
