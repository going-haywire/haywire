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


# --- Revert to Macro: a modified instance goes back to the current template ---


_CHANGED = "changed in the instance"


def _message(definition):
    """The ``message`` value of the interior's first print node."""
    wrapper = next(w for w in definition.node_wrappers.values() if w.registry_key == _PRINT)
    return wrapper.node.ports["message"].get_value()


def _modify(graph, card_id):
    """Change an interior value and add a node, so the instance differs from the template."""
    definition = graph.get_node_wrapper(card_id).node.resolve_definition()
    wrapper = next(w for w in definition.node_wrappers.values() if w.registry_key == _PRINT)
    wrapper.node.ports["message"].set_value(_CHANGED)
    added = make_node(definition, _PRINT)
    return definition, added.node_id


def _revert(editor, card_id):
    origin = graph_origin(editor.graph, card_id)
    return editor.promote_to_macro(card_id, origin.key, description="Revert to Macro")


def graph_origin(graph, card_id):
    from haywire.core.macro.source import modified_instance_origin

    return modified_instance_origin(graph.get_node_wrapper(card_id).node)


def test_revert_makes_a_placement_of_the_current_template(
    graph_with_library_system, library_system, macro_folder
):
    from haywire.core.macro.source import is_macro_placement

    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)
    template_interior = graph.get_node_wrapper(placement_id).node.resolve_definition()
    template_size = len(template_interior.node_wrappers)
    template_message = _message(template_interior)
    card_id, _ = _detach(editor, placement_id)
    modified, _ = _modify(graph, card_id)
    assert _message(modified) == _CHANGED
    assert len(modified.node_wrappers) == template_size + 1

    new_id, refusal = _revert(editor, card_id)

    assert refusal is None
    assert graph.get_node_wrapper(card_id) is None
    placement = graph.get_node_wrapper(new_id)
    assert is_macro_placement(placement.node)
    assert placement.registry_key == _MACRO
    interior = placement.node.resolve_definition()
    assert interior.template_key == _MACRO
    assert len(interior.node_wrappers) == template_size
    assert _message(interior) == template_message != _CHANGED
    assert graph.to_dict()["subgraphs"] == {}


def test_undo_of_revert_restores_the_modified_instance(
    graph_with_library_system, library_system, macro_folder
):
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)
    card_id, _ = _detach(editor, placement_id)
    _, added_id = _modify(graph, card_id)
    editor.history_manager.add_fence()

    new_id, _ = _revert(editor, card_id)
    editor.undo()

    assert graph.get_node_wrapper(new_id) is None
    restored = graph.get_node_wrapper(card_id)
    assert restored is not None
    origin = graph_origin(graph, card_id)
    assert origin is not None
    assert origin.key == _MACRO
    assert added_id in restored.node.resolve_definition().node_wrappers


def test_revert_history_entry_is_named(graph_with_library_system, library_system, macro_folder):
    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)
    card_id, _ = _detach(editor, placement_id)

    _revert(editor, card_id)

    assert editor.history_manager.get_undo_description() == "Revert to Macro"


def _group_with_stale_boundary(graph, library_system):
    """A Group whose boundary has pins the macro lacks, wired on both sides, claiming the macro as origin."""
    from haywire.core.macro.origin import MacroOrigin

    x, a, b, y = (make_node(graph, _PRINT) for _ in range(4))
    graph.create_edge_wrapper(x.node_id, "done", a.node_id, "exec")
    graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
    graph.create_edge_wrapper(b.node_id, "done", y.node_id, "exec")
    editor = _editor(graph, library_system)
    card_id, reason = editor.collapse_to_group(
        node_ids=[a.node_id, b.node_id],
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
    )
    assert reason is None
    definition = graph.get_node_wrapper(card_id).node.resolve_definition()
    definition.origin = MacroOrigin(key=_MACRO, hash="stale")
    return editor, card_id


def _formal_errors(graph):
    return [e for e in graph.edge_wrappers.values() if e.state.error_formal]


def test_revert_drops_edges_to_pins_the_macro_lacks(graph_with_library_system, library_system, macro_folder):
    graph = graph_with_library_system
    editor, card_id = _group_with_stale_boundary(graph, library_system)
    card_ports = graph.get_node_wrapper(card_id).node.ports
    assert "in_exec" in card_ports
    edges_before = len(graph._get_all_edges(card_id))
    assert edges_before == 2

    new_id, refusal = editor.promote_to_macro(
        card_id, _MACRO, description="Revert to Macro", drop_unmatched_edges=True
    )

    assert refusal is None
    assert new_id is not None
    placement_ports = graph.get_node_wrapper(new_id).node.ports
    dropped = editor.last_promotion_dropped_edges
    assert dropped == edges_before - len(graph._get_all_edges(new_id))
    assert dropped == 2
    assert "in_exec" not in placement_ports
    assert _formal_errors(graph) == []


def test_undo_of_a_revert_that_dropped_edges_restores_them(
    graph_with_library_system, library_system, macro_folder
):
    graph = graph_with_library_system
    editor, card_id = _group_with_stale_boundary(graph, library_system)
    edges_before = len(graph._get_all_edges(card_id))
    new_id, _ = editor.promote_to_macro(card_id, _MACRO, drop_unmatched_edges=True)
    assert editor.last_promotion_dropped_edges == 2

    editor.undo()

    assert graph.get_node_wrapper(new_id) is None
    assert graph.get_node_wrapper(card_id) is not None
    assert len(graph._get_all_edges(card_id)) == edges_before
    assert _formal_errors(graph) == []


def test_promote_without_the_flag_keeps_every_edge(graph_with_library_system, library_system, macro_folder):
    graph = graph_with_library_system
    editor, card_id = _group_with_stale_boundary(graph, library_system)

    new_id, _ = editor.promote_to_macro(card_id, _MACRO)

    assert editor.last_promotion_dropped_edges == 0
    assert len(graph._get_all_edges(new_id)) == 2


def test_a_reloaded_instance_keeps_its_origin_when_the_macro_is_gone(
    graph_with_library_system, library_system, macro_folder
):
    """The origin is stored in the host file, so the instance survives its macro."""
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.core.macro.source import modified_instance_origin

    graph = graph_with_library_system
    editor, placement_id = _place(graph, library_system)
    card_id, _ = _detach(editor, placement_id)
    document = json.loads(json.dumps(graph.to_dict()))

    registry = library_system.get_macro_registry()
    registry.remove_folder(str(macro_folder), _identity(macro_folder))
    reloaded = BaseGraph(filestem="Reloaded", validation_scheduler=SyncScheduler())
    assert reloaded.load_from_dict(document)

    reloaded_card = reloaded.get_node_wrapper(card_id)
    assert reloaded_card is not None
    origin = modified_instance_origin(reloaded_card.node)
    assert origin is not None
    assert origin.key == _MACRO
    assert registry.template(_MACRO) is None
    registry.add_folder(str(macro_folder), _identity(macro_folder))
