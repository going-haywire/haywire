"""``BaseNode.on_class_reloaded``: a node may absorb its own class reload.

The generic path rebuilds the node from current code, which is deliberate —
carrying state across a class reload would hide an author's new ports. A node
whose definition lives elsewhere (a macro placement) needs the opposite, so it
answers ``True`` and takes the reload itself.
"""

import pytest

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


def _event(registry_key, affected_class):
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType

    return LifeCycleEvent(
        registry_key=registry_key,
        event_type=LifeCycleEventType.CLASS_RELOADED,
        affected_class=affected_class,
        library_identity=LibraryIdentity(label="testlib", name="haybale-testing"),
    )


def test_the_default_answers_false(graph_with_library_system):
    """An ordinary node does not absorb its reload; the generic rebuild runs."""
    from tests.conftest import make_node

    wrapper = make_node(graph_with_library_system, _ADD)

    assert wrapper.node.on_class_reloaded(_event(_ADD, type(wrapper.node))) is False


def test_a_default_node_still_takes_the_generic_rebuild(graph_with_library_system):
    """The hook answering False must leave the existing path untouched."""
    from haywire.core.graph.types import ChangeReason
    from tests.conftest import make_node

    graph = graph_with_library_system
    wrapper = make_node(graph, _ADD)
    marked: list[tuple[str, ChangeReason]] = []
    graph._validation.mark_node_dirty = lambda node_id, reason: marked.append((node_id, reason))

    wrapper._on_node_lifecycle_event(_event(_ADD, type(wrapper.node)))

    assert (wrapper.node_id, ChangeReason.NODE_HOT_RELOADED) in marked


def test_a_node_answering_true_skips_the_rebuild(graph_with_library_system):
    """The absorbing node handles the reload; nothing marks it for a rebuild."""
    from haywire.core.graph.types import ChangeReason
    from tests.conftest import make_node

    graph = graph_with_library_system
    wrapper = make_node(graph, _ADD)
    absorbed: list[object] = []

    def _absorb(event):
        absorbed.append(event)
        return True

    wrapper.node.on_class_reloaded = _absorb  # type: ignore[method-assign]

    marked: list[tuple[str, ChangeReason]] = []
    graph._validation.mark_node_dirty = lambda node_id, reason: marked.append((node_id, reason))

    wrapper._on_node_lifecycle_event(_event(_ADD, type(wrapper.node)))

    assert len(absorbed) == 1
    assert (wrapper.node_id, ChangeReason.NODE_HOT_RELOADED) not in marked


def test_the_hook_is_not_consulted_on_a_failure_event(graph_with_library_system):
    """Only a successful reload is absorbable; a failure still reports."""
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
    from tests.conftest import make_node

    wrapper = make_node(graph_with_library_system, _ADD)
    consulted: list[object] = []

    def _absorb(event):
        consulted.append(event)
        return True

    wrapper.node.on_class_reloaded = _absorb  # type: ignore[method-assign]

    from haywire.core.errors.haywire_exception import HaywireException

    error = HaywireException(message="reload blew up", operation="Registry Hotreload")
    wrapper._on_node_lifecycle_event(
        LifeCycleEvent(
            registry_key=_ADD,
            event_type=LifeCycleEventType.CLASS_RELOAD_FAILED,
            affected_class=type(wrapper.node),
            library_identity=LibraryIdentity(label="testlib", name="haybale-testing"),
            error=error,
        )
    )

    assert consulted == []
    assert wrapper._state.error_import is error


def test_a_raising_hook_falls_back_to_the_generic_rebuild(graph_with_library_system):
    """A node that breaks absorbing its reload must not wedge the reload path."""
    from haywire.core.graph.types import ChangeReason
    from tests.conftest import make_node

    graph = graph_with_library_system
    wrapper = make_node(graph, _ADD)

    def _boom(event):
        raise RuntimeError("absorb failed")

    wrapper.node.on_class_reloaded = _boom  # type: ignore[method-assign]
    marked: list[tuple[str, ChangeReason]] = []
    graph._validation.mark_node_dirty = lambda node_id, reason: marked.append((node_id, reason))

    wrapper._on_node_lifecycle_event(_event(_ADD, type(wrapper.node)))

    assert (wrapper.node_id, ChangeReason.NODE_HOT_RELOADED) in marked


def test_the_dead_rebuild_helper_is_gone():
    """``_rebuild`` carried state over, then marked the reload that discards it."""
    from haywire.core.node.node_wrapper import NodeWrapper

    assert not hasattr(NodeWrapper, "_rebuild")
