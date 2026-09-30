"""A macro's callback interface relays like a Group's, through placement, reload and promotion."""

import itertools

import pytest

from tests.conftest import make_node
from tests.core.test_graph.callback_group import EMIT, INPUT, LISTEN, OUTPUT, subscriptions
from tests.core.test_macro.test_macro_reload import _identity, _modified, _save

pytestmark = pytest.mark.integration

_MACRO = "testlib:macro:Relay"
_KEYS = itertools.count()


def _document(graph, *, through: bool) -> dict:
    """A template with a callback interface: passed straight through, or fed to an interior emitter.

    A listener cannot sit inside a Subgraph (containment rules out EVENT nodes),
    so a subscription leaves a macro only on its way through.
    """
    from haybale_core.types import CALLBACK
    from haywire.core.graph.subgraph import SubgraphDefinition
    from haywire.core.graph.subgraph_crossing import RELAY_HANDLER
    from haywire.core.types.enums import PortOrigin

    key = f"tpl_cb_{next(_KEYS)}"
    definition = graph.add_subgraph(SubgraphDefinition(key=key, label="Relay"))
    b_in = make_node(definition, INPUT)
    b_out = make_node(definition, OUTPUT)
    with b_in.node.rejig(exclude=[PortOrigin.DECLARED]):
        b_in.node.add(CALLBACK.as_outlet("sub", origin=PortOrigin.RESOLVED))
    if through:
        with b_out.node.rejig(exclude=[PortOrigin.DECLARED]):
            b_out.node.add(CALLBACK.as_inlet("sub", origin=PortOrigin.RESOLVED, on_change=RELAY_HANDLER))
        definition.create_edge_wrapper(b_in.node_id, "sub", b_out.node_id, "sub")
    else:
        emitter = make_node(definition, EMIT)
        definition.create_edge_wrapper(b_in.node_id, "sub", emitter.node_id, "edge_callback")
    definition.force_validation()
    document = definition.to_dict()
    graph.remove_subgraph(key)
    document["meta"] = {"description": ""}
    document.pop("key", None)
    return document


@pytest.fixture
def macro(tmp_path, library_system):
    """Yield (path, identity, registry, register); ``register(document)`` writes and registers the file."""
    registry = library_system.get_macro_registry()
    identity = _identity(str(tmp_path))
    path = tmp_path / "Relay.hwm"
    registered = []

    def register(document):
        _save(path, document)
        registry.add_folder(str(tmp_path), identity)
        registered.append(True)

    try:
        yield path, identity, registry, register
    finally:
        if registered:
            registry.remove_folder(str(tmp_path), identity)


def _interior_nodes(placement, registry_key):
    definition = placement.node.resolve_definition()
    return [w for w in definition.node_wrappers.values() if w.registry_key == registry_key]


def _through_placement(graph, macro):
    """A pass-through placement between a listener and an emitter, both outside."""
    _path, _identity_, _registry, register = macro
    register(_document(graph, through=True))
    placement = make_node(graph, _MACRO)
    listener = make_node(graph, LISTEN)
    emitter = make_node(graph, EMIT)
    graph.create_edge_wrapper(listener.node_id, "listen_callback", placement.node_id, "in_sub")
    graph.create_edge_wrapper(placement.node_id, "out_sub", emitter.node_id, "edge_callback")
    return listener, emitter


def test_a_subscription_passes_through_a_placement(graph_with_library_system, macro):
    listener, emitter = _through_placement(graph_with_library_system, macro)

    assert subscriptions(emitter) == [listener.node.value("listen_callback")]


def test_a_subscription_through_a_placement_survives_a_reload(graph_with_library_system, macro):
    listener, emitter = _through_placement(graph_with_library_system, macro)
    path, identity, registry, _register = macro

    _save(path, _document(graph_with_library_system, through=True))
    _modified(registry, path, identity)

    assert subscriptions(emitter) == [listener.node.value("listen_callback")]


def test_an_inward_subscription_survives_a_reload(graph_with_library_system, macro):
    graph = graph_with_library_system
    path, identity, registry, register = macro
    register(_document(graph, through=False))
    placement = make_node(graph, _MACRO)
    listener = make_node(graph, LISTEN)
    graph.create_edge_wrapper(listener.node_id, "listen_callback", placement.node_id, "in_sub")

    _save(path, _document(graph, through=False))
    _modified(registry, path, identity)

    (emitter,) = _interior_nodes(placement, EMIT)
    assert subscriptions(emitter) == [listener.node.value("listen_callback")]


def test_promoting_a_group_keeps_a_subscription_through_it(graph_with_library_system, library_system, macro):
    from haywire.core.graph.editor import Editor
    from tests.core.test_edge.test_disconnect_semantics import _split_with_reroute
    from tests.core.test_undo.test_collapse_callback_crossing import _collapse

    graph = graph_with_library_system
    listener = make_node(graph, LISTEN)
    emitter = make_node(graph, EMIT)
    edge = graph.create_edge_wrapper(listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
    action = _collapse(graph, [_split_with_reroute(graph, edge.edge_id)])
    document = graph.get_subgraph(action.subgraph_key).to_dict()
    document.pop("key", None)
    document["meta"] = {"description": ""}
    _path, _identity_, _registry, register = macro
    register(document)

    placement_id, refusal = Editor(graph, library_system.get_node_factory()).promote_to_macro(
        action.card_node_id, _MACRO
    )

    assert refusal is None
    assert graph.get_node_wrapper(placement_id) is not None
    assert subscriptions(emitter) == [listener.node.value("listen_callback")]
