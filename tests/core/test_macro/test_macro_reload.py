"""Saving a macro file updates every placement, in every open graph.

The watcher's MODIFIED is the only trigger (decision 9). A reload is absorbed
in place, so values, labels and edges on surviving pins are kept; a pin whose
interface port is gone drops its edges, which the edge itself reports.
"""

import itertools
import json

import pytest

pytestmark = pytest.mark.integration

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_ADD = "haybale-testing:node:TestAddFloatNode"
_MACRO = "testlib:macro:Blur"

#: Scratch subgraph keys for building template documents, unique per call.
_SCRATCH_KEYS = itertools.count()


def _identity(folder_path):
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(label="testlib", name="testlib", folder_path=folder_path, module_name="testlib")


def _document(graph, interface_ports=("gain",), description=""):
    """A macro document, built by serializing a real Subgraph.

    Hand-writing the node table would encode a guess at the serialized port
    shape; this produces whatever the current format actually is.
    """
    from haywire.barn.builtin.types import FLOAT
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.core.graph.subgraph import SubgraphDefinition

    # Unique per call: reusing a key would remove a subgraph this graph already
    # holds — including a placement's own interior, which lives here too.
    key = f"tpl_{next(_SCRATCH_KEYS)}"
    definition = graph.add_subgraph(
        SubgraphDefinition(key=key, label="Blur", validation_scheduler=SyncScheduler())
    )
    boundary_in = definition.create_node_wrapper(_INPUT, position=(0, 0))
    definition.create_node_wrapper(_OUTPUT, position=(200, 0))
    with boundary_in.node.rejig():
        for name in interface_ports:
            boundary_in.node.add(FLOAT.as_outlet(name, label=name.title()))
    definition.force_validation()

    document = definition.to_dict()
    graph.remove_subgraph(key)

    document["meta"] = {"description": description}
    document.pop("key", None)
    return document


def _save(path, document):
    path.write_text(json.dumps(document))


def _modified(registry, path, identity):
    """Deliver the watcher event a studio save produces."""
    from haywire.core.registry.events import FileChangeEvent, FileEventType

    registry.event_dispatcher(
        FileChangeEvent(
            file_path=str(path),
            event_type=FileEventType.MODIFIED,
            library_identity=identity,
            timestamp=0.0,
        )
    )


@pytest.fixture
def macro_file(tmp_path, library_system, graph_with_library_system):
    """One registered macro; yields (path, identity, registry)."""
    path = tmp_path / "Blur.hwm"
    _save(path, _document(graph_with_library_system))
    registry = library_system.get_macro_registry()
    identity = _identity(str(tmp_path))
    registry.add_folder(str(tmp_path), identity)
    try:
        yield path, identity, registry
    finally:
        registry.remove_folder(str(tmp_path), identity)


def _place(graph):
    from tests.conftest import make_node

    return make_node(graph, _MACRO)


def test_one_save_reaches_placements_in_two_graphs(macro_file, graph_with_library_system, library_system):
    """The per-key relay spans every open graph, because they share one factory."""
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    path, identity, registry = macro_file
    first_graph = graph_with_library_system
    second_graph = BaseGraph(filestem="other", validation_scheduler=SyncScheduler())

    first = _place(first_graph)
    second = _place(second_graph)

    _save(path, _document(first_graph, interface_ports=("gain", "radius")))
    _modified(registry, path, identity)

    for card in (first, second):
        pins = {port.id for port in card.node.get_ports(has_pin=True)}
        assert "in_radius" in pins, "the grown interface port reached this placement"


def test_a_reload_keeps_the_users_label(macro_file, graph_with_library_system):
    path, identity, registry = macro_file
    graph = graph_with_library_system
    card = _place(graph)
    card.node.props.label = "My Blur"

    _save(path, _document(graph, interface_ports=("gain", "radius")))
    _modified(registry, path, identity)

    assert card.node.props.label == "My Blur"


def test_a_reload_keeps_a_pin_value(macro_file, graph_with_library_system):
    """The card owns its port values; a template edit must not reset them."""
    path, identity, registry = macro_file
    graph = graph_with_library_system
    card = _place(graph)
    card.node.ports["in_gain"].set_value(0.75)

    _save(path, _document(graph, interface_ports=("gain", "radius")))
    _modified(registry, path, identity)

    assert card.node.ports["in_gain"].get_value() == pytest.approx(0.75)


def test_a_reload_keeps_an_edge_on_a_surviving_pin(macro_file, graph_with_library_system):
    from tests.conftest import make_node

    path, identity, registry = macro_file
    graph = graph_with_library_system
    card = _place(graph)
    producer = make_node(graph, _ADD)
    graph.create_edge_wrapper(producer.node_id, "result", card.node_id, "in_gain")
    graph.force_validation()

    _save(path, _document(graph, interface_ports=("gain", "radius")))
    _modified(registry, path, identity)
    graph.force_validation()

    linked = [e for e in graph.edge_wrappers.values() if e.sink_node_id == card.node_id]
    assert len(linked) == 1


def test_a_removed_interface_port_drops_its_pin(macro_file, graph_with_library_system):
    path, identity, registry = macro_file
    graph = graph_with_library_system
    card = _place(graph)
    assert "in_gain" in {port.id for port in card.node.get_ports(has_pin=True)}

    _save(path, _document(graph, interface_ports=("radius",)))
    _modified(registry, path, identity)

    pins = {port.id for port in card.node.get_ports(has_pin=True)}
    assert "in_gain" not in pins
    assert "in_radius" in pins


def test_the_interior_is_replaced_not_accumulated(macro_file, graph_with_library_system):
    """Each reload swaps the interior; nodes must not pile up."""
    path, identity, registry = macro_file
    graph = graph_with_library_system
    card = _place(graph)
    before = len(card.node.resolve_definition().node_wrappers)

    for _ in range(3):
        _save(path, _document(graph, interface_ports=("gain",), description="again"))
        _modified(registry, path, identity)

    assert len(card.node.resolve_definition().node_wrappers) == before


def test_an_unchanged_save_changes_nothing(macro_file, graph_with_library_system):
    """A save that does not change the bytes must not disturb a placement.

    Rewritten byte-for-byte, as an atomic save of an unedited file is: a fresh
    document would carry new node ids and so be a real change.
    """
    path, identity, registry = macro_file
    graph = graph_with_library_system
    card = _place(graph)
    card.node.props.label = "My Blur"
    definition_before = card.node.resolve_definition()

    path.write_text(path.read_text())
    _modified(registry, path, identity)

    assert card.node.props.label == "My Blur"
    assert card.node.resolve_definition() is definition_before


def test_a_reload_is_not_an_undo_subject(macro_file, graph_with_library_system, library_system):
    """Decision 10: the interface is the template's, never an action's."""
    from haywire.core.graph.editor import Editor

    path, identity, registry = macro_file
    graph = graph_with_library_system
    _place(graph)
    editor = Editor(graph, library_system.get_node_factory())
    history = editor.history_manager
    could_undo = history.can_undo()
    description_before = history.get_undo_description()

    _save(path, _document(graph, interface_ports=("gain", "radius")))
    _modified(registry, path, identity)

    assert history.can_undo() is could_undo
    assert history.get_undo_description() == description_before


def test_a_broken_save_keeps_the_previous_interior(macro_file, graph_with_library_system):
    """Decision 13: a refused reload badges the placement and keeps what works."""
    path, identity, registry = macro_file
    graph = graph_with_library_system
    card = _place(graph)
    before = card.node.resolve_definition()

    path.write_text("{not json")
    _modified(registry, path, identity)

    assert card.node.resolve_definition() is before
    assert registry.get_lastevent(_MACRO).error is not None
