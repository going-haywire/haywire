"""``MacroNode``: a card standing for a macro template, with its own interior.

Each placement instantiates the template into its own ``SubgraphDefinition``,
keyed by the card's node id — so two cards never share an interior, and the
interior is never serialized into the host.
"""

import json

import pytest

pytestmark = pytest.mark.integration

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_ADD = "haybale-testing:node:TestAddFloatNode"
_MACRO = "testlib:macro:Blur"


def _identity(folder_path="/lib"):
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(label="testlib", name="testlib", folder_path=folder_path, module_name="testlib")


def _document(description="", extra_nodes=()):
    nodes = {
        "b_in": {"node_id": "b_in", "registry_key": _INPUT},
        "b_out": {"node_id": "b_out", "registry_key": _OUTPUT},
    }
    for i, key in enumerate(extra_nodes):
        nodes[f"x{i}"] = {"node_id": f"x{i}", "registry_key": key}
    return {
        "format_version": 1,
        "meta": {"description": description},
        "nodes": nodes,
        "edges": {},
        "variables": {},
        "props": {},
        "subgraphs": {},
    }


@pytest.fixture
def macro_registry(tmp_path, library_system):
    """A registry holding one macro, wired into the app's node factory.

    The registry is a DI singleton, so the folder is removed again — otherwise
    the next test's macro collides with this one's on the same key.
    """
    (tmp_path / "Blur.hwm").write_text(json.dumps(_document(extra_nodes=[_ADD])))
    registry = library_system.get_macro_registry()
    identity = _identity(str(tmp_path))
    registry.add_folder(str(tmp_path), identity)
    try:
        yield registry
    finally:
        registry.remove_folder(str(tmp_path), identity)


def _place(graph, registry_key=_MACRO):
    from tests.conftest import make_node

    return make_node(graph, registry_key)


def test_the_placement_derives_its_key_from_its_node_id(graph_with_library_system, macro_registry):
    """Decision 8: the key is derived, never stored, so two cards cannot share one."""
    card = _place(graph_with_library_system)

    assert card.node.subgraph_key == f"macro_{card.node_id}"


def test_the_key_is_not_written_to_the_store(graph_with_library_system, macro_registry):
    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

    card = _place(graph_with_library_system)

    assert SUBGRAPH_KEY not in card.node.store


def test_the_placement_instantiates_its_own_interior(graph_with_library_system, macro_registry):
    card = _place(graph_with_library_system)

    definition = card.node.resolve_definition()
    assert definition is not None
    assert definition.input_node is not None
    assert definition.output_node is not None


def test_two_placements_get_separate_interiors(graph_with_library_system, macro_registry):
    """Decision 8: each placement is its own instantiation."""
    graph = graph_with_library_system
    first = _place(graph)
    second = _place(graph)

    assert first.node.subgraph_key != second.node.subgraph_key
    first_ids = set(first.node.resolve_definition().node_wrappers)
    second_ids = set(second.node.resolve_definition().node_wrappers)
    assert first_ids.isdisjoint(second_ids)


def test_the_interior_is_marked_as_template_instantiated(graph_with_library_system, macro_registry):
    card = _place(graph_with_library_system)

    assert card.node.resolve_definition().template_key == _MACRO


def test_the_interior_is_not_serialized_into_the_host(graph_with_library_system, macro_registry):
    """Decision 8: the host carries the card, never the macro's interior."""
    graph = graph_with_library_system
    card = _place(graph)

    document = graph.to_dict()

    assert card.node.subgraph_key not in document["subgraphs"]


def test_a_group_subgraph_is_still_serialized(graph_with_library_system, macro_registry):
    """Only template-instantiated definitions are skipped."""
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.core.graph.subgraph import SubgraphDefinition

    graph = graph_with_library_system
    graph.add_subgraph(SubgraphDefinition(key="group_a", label="G", validation_scheduler=SyncScheduler()))

    assert "group_a" in graph.to_dict()["subgraphs"]


def test_the_card_mirrors_the_template_label(graph_with_library_system, macro_registry):
    card = _place(graph_with_library_system)

    assert card.node.display_label == "Blur"


def test_renaming_a_placement_leaves_the_others(graph_with_library_system, macro_registry):
    """Decision 20: the label write-back is Group-only."""
    graph = graph_with_library_system
    first = _place(graph)
    second = _place(graph)

    first.node.props.label = "My Blur"

    assert first.node.display_label == "My Blur"
    assert second.node.display_label == "Blur"


def test_renaming_a_placement_does_not_rename_its_interior(graph_with_library_system, macro_registry):
    """A shared template must not be renamed by one card that stands for it."""
    card = _place(graph_with_library_system)
    before = card.node.resolve_definition().label

    card.node.props.label = "My Blur"

    assert card.node.resolve_definition().label == before


def test_a_placement_absorbs_a_template_reload(graph_with_library_system, macro_registry, tmp_path):
    """Decision 7: swap the interior in place rather than rebuilding the node."""
    graph = graph_with_library_system
    card = _place(graph)
    card.node.props.label = "My Blur"
    before_key = card.node.subgraph_key

    (tmp_path / "Blur.hwm").write_text(json.dumps(_document(description="v2", extra_nodes=[_ADD, _ADD])))
    from haywire.core.registry.events import FileChangeEvent, FileEventType

    macro_registry.event_dispatcher(
        FileChangeEvent(
            file_path=str(tmp_path / "Blur.hwm"),
            event_type=FileEventType.MODIFIED,
            library_identity=_identity(str(tmp_path)),
            timestamp=0.0,
        )
    )

    assert card.node.props.label == "My Blur", "the user's label survives the reload"
    assert card.node.subgraph_key == before_key, "the interior is keyed by the card, not remade"
    assert len(card.node.resolve_definition().node_wrappers) == 4


def test_the_placement_does_not_claim_the_graph_node_slot(library_system):
    """Identity flags are inherited, so ``_is_graph_node`` must be cleared.

    Left set, a placement would register as the Graph-node and collapsing a
    selection into a Group would build a macro card instead.
    """
    from haywire.barn.builtin.nodes.graph_node import GraphNode
    from haywire.barn.builtin.nodes.macro_node import MacroNode

    assert MacroNode.class_identity._is_macro_node is True
    assert MacroNode.class_identity._is_graph_node is False
    assert library_system.get_node_factory().get_graph_node() is GraphNode


def test_a_placement_of_an_absent_macro_loads_as_the_error_node(graph_with_library_system):
    """A graph using a macro from an uninstalled library still opens."""
    graph = graph_with_library_system

    card = _place(graph, "absent-lib:macro:Gone")

    assert card.node.identity._is_error is True


# =============================================================================
# A placement's interior is runtime state: its edits do not mark the host
# =============================================================================


def _interior_adder(card):
    """The macro's Add node inside a placed card's interior."""
    definition = card.node.resolve_definition()
    return next(w for w in definition.node_wrappers.values() if w.registry_key == _ADD)


def test_an_interior_value_edit_does_not_mark_the_host(graph_with_library_system, macro_registry):
    """A value edit inside a placement delivers nothing a save would record, and no reassembly."""
    graph = graph_with_library_system
    card = _place(graph)
    interior = _interior_adder(card)
    graph.force_validation()
    seen: list = []
    graph.subscribe_to_validation(seen.append)

    interior.mark_value_edited()

    assert [r for r in seen if r.requires_save()] == []
    assert [r for r in seen if r.requires_reassembly()] == []


def test_an_interior_structure_edit_still_reassembles_the_host(graph_with_library_system, macro_registry):
    """Adding a node inside a placement reassembles the running host."""
    from haywire.core.graph.types import ChangeReason
    from tests.conftest import make_node

    graph = graph_with_library_system
    card = _place(graph)
    graph.force_validation()
    seen: list = []
    graph.subscribe_to_validation(seen.append)

    make_node(card.node.resolve_definition(), _ADD)

    assert ChangeReason.GRAPH_REQUIRE_REASSEMBLY in [r.graph for r in seen]


def test_a_group_still_forwards_content_changes(graph_with_library_system):
    """An edit inside a Group's interior still marks the host unsaved."""
    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY, GraphNode
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.core.graph.subgraph import SubgraphDefinition
    from haywire.core.graph.types import ChangeReason
    from tests.conftest import make_node

    graph = graph_with_library_system
    definition = graph.add_subgraph(
        SubgraphDefinition(key="sg", label="Group", validation_scheduler=SyncScheduler())
    )
    make_node(definition, _OUTPUT)
    interior = make_node(definition, _ADD)
    card = make_node(graph, "haywire-core:node:GraphNode", node_data={"store": {SUBGRAPH_KEY: "sg"}})
    assert isinstance(card.node, GraphNode)
    card.node.reconcile_interface()
    graph.force_validation()
    seen: list = []
    graph.subscribe_to_validation(seen.append)

    interior.mark_value_edited()

    assert ChangeReason.GRAPH_CONTENT_CHANGED in [r.graph for r in seen]
    assert any(r.requires_save() for r in seen)


def test_an_interior_value_is_still_live(graph_with_library_system, macro_registry):
    """A card widget on the locked placement level may write; the value changes, the host is not marked."""
    from haybale_graph_editor.access import NodeWriteGate, allows
    from haywire.core.access import AccessTier

    graph = graph_with_library_system
    card = _place(graph)
    interior = _interior_adder(card)
    graph.force_validation()
    seen: list = []
    graph.subscribe_to_validation(seen.append)

    def on_locked_level(required: AccessTier) -> bool:
        return allows(AccessTier.EDIT.satisfies, True, required)

    gate = NodeWriteGate(AccessTier.OPERATE, on_locked_level, interior)
    assert gate.allows() is True
    assert NodeWriteGate(AccessTier.EDIT, on_locked_level, interior).allows() is False

    port = interior.node.ports["value_a"]
    assert port.get_value() != 2.5
    port.set_value(2.5)
    gate.written()

    assert port.get_value() == 2.5
    assert [r for r in seen if r.requires_save()] == []
    assert [r for r in seen if r.requires_reassembly()] == []
