"""A successful hot reload is one undo step per graph: Undo puts the reloaded nodes back exactly.

The reload is driven as ``NodeWrapper._on_node_lifecycle_event`` ends for a class that
does not absorb it: each node is marked ``NODE_HOT_RELOADED`` and the pass rebuilds it.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.types import ChangeReason
from haywire.core.undo.config import UndoConfig

pytestmark = pytest.mark.integration


class _ParkedScheduler:
    """Never fires on its own: every mark waits for ``force_immediate_validation``, so they share a batch."""

    def schedule(self, delay_seconds: float, fn: Callable[[], object]) -> Any:
        class _Handle:
            def cancel(self) -> None:
                pass

        return _Handle()


def _print_cls() -> Any:
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return TestPrintNode


def _graph_with_editor(library_system, *, parked: bool = True) -> tuple[BaseGraph, Editor]:
    graph = BaseGraph("Reloaded", validation_scheduler=_ParkedScheduler() if parked else None)
    editor = Editor(
        graph, library_system.get_node_factory(), undo_config=UndoConfig(enable_auto_grouping=False)
    )
    return graph, editor


def _printer(graph: BaseGraph, message: str) -> Any:
    wrapper: Any = graph.create_node_wrapper(_print_cls().class_identity.registry_key, position=(10.0, 10.0))
    graph._validation.force_immediate_validation()
    wrapper.node.ports["message"].set_value(message)
    return wrapper


def _reload(graph: BaseGraph, *wrappers: Any) -> None:
    for wrapper in wrappers:
        graph._validation.mark_node_dirty(wrapper.node_id, ChangeReason.NODE_HOT_RELOADED)
    graph._validation.force_immediate_validation()


def _message(wrapper: Any) -> str:
    return wrapper.node.ports["message"].get_value()


def test_a_reload_records_one_step_for_the_graph(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    first, second = _printer(graph, "one"), _printer(graph, "two")
    label = _print_cls().class_identity.label

    _reload(graph, first, second)

    assert (_message(first), _message(second)) == ("Hello, World!", "Hello, World!")
    assert editor.history_manager.get_undo_description() == f"Reload {label} (2 nodes)"

    assert editor.undo()
    graph._validation.force_immediate_validation()
    assert (_message(first), _message(second)) == ("one", "two")

    assert editor.redo()
    graph._validation.force_immediate_validation()
    assert (_message(first), _message(second)) == ("Hello, World!", "Hello, World!")


def test_each_graph_records_its_own_step(graph_with_library_system, library_system):
    graph_a, editor_a = _graph_with_editor(library_system)
    graph_b, editor_b = _graph_with_editor(library_system)
    in_a, in_b = _printer(graph_a, "a"), _printer(graph_b, "b")

    _reload(graph_a, in_a)
    _reload(graph_b, in_b)

    assert editor_a.history_manager.can_undo()
    assert editor_b.history_manager.can_undo()
    editor_a.undo()
    graph_a._validation.force_immediate_validation()
    assert _message(in_a) == "a"
    assert _message(in_b) == "Hello, World!"


def _fresh_printer(graph: BaseGraph) -> Any:
    wrapper: Any = graph.create_node_wrapper(_print_cls().class_identity.registry_key, position=(10.0, 10.0))
    graph._validation.force_immediate_validation()
    return wrapper


def test_the_reload_of_an_untouched_node_records_nothing(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _fresh_printer(graph)

    _reload(graph, wrapper)

    assert not editor.history_manager.can_undo()


def test_a_reload_step_holds_only_the_nodes_it_changed(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    fresh, changed = _fresh_printer(graph), _printer(graph, "changed")
    label = _print_cls().class_identity.label

    _reload(graph, fresh, changed)

    assert editor.history_manager.get_undo_description() == f"Reload {label}"
    assert editor.undo()
    graph._validation.force_immediate_validation()
    assert (_message(fresh), _message(changed)) == ("Hello, World!", "changed")


def test_a_failed_reload_records_nothing(graph_with_library_system, library_system, construction_fails):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")

    construction_fails(1)
    _reload(graph, wrapper)

    assert wrapper.is_stand_in
    assert not editor.history_manager.can_undo()


def test_the_reload_that_fixes_a_class_records_nothing(
    graph_with_library_system, library_system, construction_fails
):
    """The fixed node comes back with its kept data (ADR 0058), so there is nothing to undo."""
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")
    construction_fails(1)
    _reload(graph, wrapper)
    assert wrapper.is_stand_in

    _reload(graph, wrapper)

    assert isinstance(wrapper.node, _print_cls())
    assert _message(wrapper) == "kept"
    assert not editor.history_manager.can_undo()


def test_a_graph_without_an_editor_records_nothing(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = _printer(graph, "kept")

    _reload(graph, wrapper)

    assert graph.history is None
    assert _message(wrapper) == "Hello, World!"


def test_a_reload_validated_off_the_main_thread_records_nothing(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")
    graph._validation.mark_node_dirty(wrapper.node_id, ChangeReason.NODE_HOT_RELOADED)

    worker = threading.Thread(target=graph._validation.force_immediate_validation)
    worker.start()
    worker.join()

    assert _message(wrapper) == "Hello, World!"
    assert not editor.history_manager.can_undo()


def test_undo_and_redo_rebuilds_are_not_recorded(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")
    _reload(graph, wrapper)

    editor.undo()
    graph._validation.force_immediate_validation()

    assert not editor.history_manager.can_undo()
    assert editor.history_manager.can_redo()


def test_two_quick_undos_reach_the_state_before_both(graph_with_library_system, library_system):
    """Undo rebuilds at once: a second Ctrl+Z before any pass must not land on a stale node."""
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "a")
    assert editor.set_property(wrapper.node_id, "message", "b")
    _reload(graph, wrapper)

    editor.undo()
    editor.undo()
    graph._validation.force_immediate_validation()

    assert _message(wrapper) == "a"


def test_undoing_a_reset_and_then_its_delete_quickly_restores_the_node(
    graph_with_library_system, library_system
):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")
    assert editor.reset_nodes([wrapper.node_id])
    assert editor.remove_elements([wrapper.node_id], [])

    editor.undo()
    editor.undo()
    graph._validation.force_immediate_validation()

    restored = graph.node_wrappers[wrapper.node_id]
    assert _message(restored) == "kept"
    assert restored._rebuild_data is None


def test_a_recorded_reload_is_its_own_step(graph_with_library_system, library_system):
    """With grouping on (the studio's default), a user action still pending is not folded into the reload."""
    graph = BaseGraph("Grouped", validation_scheduler=_ParkedScheduler())
    editor = Editor(graph, library_system.get_node_factory())
    wrapper = _printer(graph, "kept")
    assert editor.move_nodes([wrapper.node_id], 40.0, 0.0)

    _reload(graph, wrapper)
    editor.undo()

    assert _message(wrapper) == "kept"
    assert wrapper.node.props.get_position() == (50.0, 10.0)


def test_a_reload_inside_a_group_is_a_step_on_the_host_history(graph_with_library_system, library_system):
    """An opened interior shares its host's history, as SubgraphContainer builds it."""
    from haywire.core.graph.subgraph import SubgraphDefinition

    graph, editor = _graph_with_editor(library_system)
    definition = graph.add_subgraph(SubgraphDefinition(key="sg", label="Group"))
    Editor(definition, library_system.get_node_factory(), history_manager=editor.history_manager)
    inner = _printer(definition, "inner")

    _reload(definition, inner)

    assert _message(inner) == "Hello, World!"
    assert editor.history_manager.get_undo_description() == f"Reload {_print_cls().class_identity.label}"
    assert editor.undo()
    definition._validation.force_immediate_validation()
    assert _message(inner) == "inner"


def test_reload_batches_in_a_row_undo_one_by_one(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "one")
    _reload(graph, wrapper)
    wrapper.node.ports["message"].set_value("two")
    _reload(graph, wrapper)

    assert editor.undo()
    graph._validation.force_immediate_validation()
    assert _message(wrapper) == "two"
    assert editor.undo()
    graph._validation.force_immediate_validation()
    assert _message(wrapper) == "one"
    assert not editor.history_manager.can_undo()


def test_an_undone_reload_saves_and_reopens_with_the_old_data(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")
    _reload(graph, wrapper)
    editor.undo()
    graph._validation.force_immediate_validation()

    reopened = BaseGraph("Reopened", validation_scheduler=_ParkedScheduler())
    try:
        assert reopened.load_from_dict(graph.to_dict())
        reopened._validation.force_immediate_validation()
        assert _message(reopened.node_wrappers[wrapper.node_id]) == "kept"
    finally:
        reopened._validation.clear()
        reopened.cleanup()


def test_a_node_that_absorbs_its_reload_records_no_step(graph_with_library_system, library_system):
    from tests.core.test_node.test_on_class_reloaded import _event

    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")
    node = wrapper.node
    node.on_class_reloaded = lambda event: True

    wrapper._on_node_lifecycle_event(_event(wrapper.registry_key, type(node)))
    graph._validation.force_immediate_validation()

    assert wrapper.node is node
    assert _message(wrapper) == "kept"
    assert not editor.history_manager.can_undo()
