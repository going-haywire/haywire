"""A successful hot reload keeps each changed node's previous setup; it records no undo step.

The reload is driven as ``NodeWrapper._on_node_lifecycle_event`` ends for a class that
does not absorb it: each node is marked ``NODE_HOT_RELOADED`` and the pass rebuilds it.
See ADR 0062.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

import pytest

from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.types import ChangeReason
from haywire.core.undo.config import UndoConfig

pytestmark = pytest.mark.integration


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=20)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


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


def _fresh_printer(graph: BaseGraph) -> Any:
    wrapper: Any = graph.create_node_wrapper(_print_cls().class_identity.registry_key, position=(10.0, 10.0))
    graph._validation.force_immediate_validation()
    return wrapper


def _reload(graph: BaseGraph, *wrappers: Any) -> None:
    for wrapper in wrappers:
        graph._validation.mark_node_dirty(wrapper.node_id, ChangeReason.NODE_HOT_RELOADED)
    graph._validation.force_immediate_validation()


def _message(wrapper: Any) -> str:
    return wrapper.node.ports["message"].get_value()


def _setup(wrapper: Any) -> dict:
    data = wrapper.serialize()["node_data"]
    data.pop("previous_setup", None)
    return data


def test_a_reload_keeps_the_previous_setup_and_records_no_step(
    graph_with_library_system, library_system, ledger
):
    graph, editor = _graph_with_editor(library_system)
    first = _printer(graph, "one")
    before = _setup(first)

    _reload(graph, first)

    assert _message(first) == "Hello, World!"
    assert first.previous_setup == before
    assert [w.kind for w in first.state.warnings] == ["previous_setup"]
    assert not editor.history_manager.can_undo()
    (entry,) = ledger.query().entries
    assert (entry.operation, entry.node_id) == ("Hot reload", first.node_id)


def test_an_untouched_node_keeps_nothing(graph_with_library_system, library_system, ledger):
    graph, _editor = _graph_with_editor(library_system)
    untouched = _fresh_printer(graph)

    _reload(graph, untouched)

    assert untouched.previous_setup is None
    assert untouched.state.warnings == []
    assert ledger.query().total == 0


def test_only_the_changed_nodes_keep_one(graph_with_library_system, library_system):
    graph, _editor = _graph_with_editor(library_system)
    fresh, changed = _fresh_printer(graph), _printer(graph, "changed")

    _reload(graph, fresh, changed)

    assert fresh.previous_setup is None
    assert changed.previous_setup is not None


def test_a_graph_without_an_editor_keeps_the_previous_setup(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = _printer(graph, "kept")
    before = _setup(wrapper)

    _reload(graph, wrapper)

    assert wrapper.previous_setup == before


def test_a_reload_validated_off_the_main_thread_keeps_the_previous_setup(
    graph_with_library_system, library_system
):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")
    graph._validation.mark_node_dirty(wrapper.node_id, ChangeReason.NODE_HOT_RELOADED)

    worker = threading.Thread(target=graph._validation.force_immediate_validation)
    worker.start()
    worker.join()

    assert _message(wrapper) == "Hello, World!"
    assert wrapper.previous_setup is not None
    assert not editor.history_manager.can_undo()


def test_a_reload_inside_a_never_opened_group_keeps_the_previous_setup(
    graph_with_library_system, library_system, ledger
):
    from haywire.barn.builtin.nodes.graph_node import GraphNode
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode

    graph, editor = _graph_with_editor(library_system, parked=False)
    printer = _printer(graph, "inner")
    host_id, _ = editor.collapse_to_group(
        [printer.node_id],
        GraphNode.class_identity.registry_key,
        SubgraphInputNode.class_identity.registry_key,
        SubgraphOutputNode.class_identity.registry_key,
    )
    assert host_id is not None
    graph._validation.force_immediate_validation()
    host: Any = graph.get_node_wrapper(host_id)
    definition: Any = graph.get_subgraph(host.node.subgraph_key)
    definition._validation.force_immediate_validation()
    inner = next(w for w in definition.node_wrappers.values() if isinstance(w.node, _print_cls()))
    assert _message(inner) == "inner"
    ledger.clear()

    _reload(definition, inner)

    assert _message(inner) == "Hello, World!"
    assert inner.previous_setup is not None
    (entry,) = ledger.query().entries
    assert entry.node_id == inner.node_id
    assert entry.message.endswith(f"(inside '{host.node.display_label}')")


def test_a_second_reload_keeps_the_first_previous_setup(graph_with_library_system, library_system):
    graph, _editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "one")
    before = _setup(wrapper)

    _reload(graph, wrapper)
    _reload(graph, wrapper)

    assert wrapper.previous_setup == before


def test_a_reload_back_to_the_previous_setup_clears_it(graph_with_library_system, library_system):
    graph, _editor = _graph_with_editor(library_system)
    wrapper = _fresh_printer(graph)
    wrapper.set_previous_setup(_setup(wrapper))
    wrapper.node.ports["message"].set_value("changed since")

    _reload(graph, wrapper)

    assert wrapper.previous_setup is None
    assert wrapper.state.warnings == []


def test_a_failed_reload_keeps_the_held_previous_setup(
    graph_with_library_system, library_system, construction_fails
):
    graph, _editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")
    before = _setup(wrapper)
    _reload(graph, wrapper)

    construction_fails(1)
    _reload(graph, wrapper)
    assert wrapper.is_stand_in
    assert wrapper.previous_setup == before

    _reload(graph, wrapper)
    assert isinstance(wrapper.node, _print_cls())
    assert wrapper.previous_setup == before


def test_a_reload_that_fails_keeps_nothing_new(
    graph_with_library_system, library_system, construction_fails
):
    graph, _editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")

    construction_fails(1)
    _reload(graph, wrapper)

    assert wrapper.is_stand_in
    assert wrapper.previous_setup is None


def test_the_reload_that_fixes_a_class_brings_the_kept_data_back(
    graph_with_library_system, library_system, construction_fails
):
    """The fixed node comes back with its kept data (ADR 0058): nothing to hold."""
    graph, _editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")
    construction_fails(1)
    _reload(graph, wrapper)
    assert wrapper.is_stand_in

    _reload(graph, wrapper)

    assert isinstance(wrapper.node, _print_cls())
    assert _message(wrapper) == "kept"
    assert wrapper.previous_setup is None


def test_a_held_previous_setup_saves_and_reopens(graph_with_library_system, library_system):
    graph, _editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")
    before = _setup(wrapper)
    _reload(graph, wrapper)

    reopened = BaseGraph("Reopened", validation_scheduler=_ParkedScheduler())
    try:
        assert reopened.load_from_dict(graph.to_dict())
        reopened._validation.force_immediate_validation()
        assert reopened.node_wrappers[wrapper.node_id].previous_setup == before
    finally:
        reopened._validation.clear()
        reopened.cleanup()


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


def test_a_node_that_absorbs_its_reload_keeps_nothing(graph_with_library_system, library_system):
    from tests.core.test_node.test_on_class_reloaded import _event

    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "kept")
    node = wrapper.node
    node.on_class_reloaded = lambda event: True

    wrapper._on_node_lifecycle_event(_event(wrapper.registry_key, type(node)))
    graph._validation.force_immediate_validation()

    assert wrapper.node is node
    assert _message(wrapper) == "kept"
    assert wrapper.previous_setup is None
    assert not editor.history_manager.can_undo()


def test_apply_restores_the_previous_setup_and_undo_brings_the_warning_back(
    graph_with_library_system, library_system
):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "one")
    _reload(graph, wrapper)
    label = _print_cls().class_identity.label

    assert editor.apply_previous_setup([wrapper.node_id])

    assert _message(wrapper) == "one"
    assert wrapper.previous_setup is None
    assert wrapper.state.warnings == []
    assert editor.history_manager.get_undo_description() == f"Apply previous setup {label}"
    assert editor.undo()
    graph._validation.force_immediate_validation()
    assert _message(wrapper) == "Hello, World!"
    assert wrapper.previous_setup is not None
    assert [w.kind for w in wrapper.state.warnings] == ["previous_setup"]


def test_apply_keeps_the_node_where_it_is_now(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "one")
    _reload(graph, wrapper)
    wrapper.node.props.set_position((500.0, 300.0))
    wrapper.node.props.z = 4

    assert editor.apply_previous_setup([wrapper.node_id])

    assert wrapper.node.props.get_position() == (500.0, 300.0)
    assert wrapper.node.props.z == 4
    assert _message(wrapper) == "one"


def test_apply_restores_the_old_label(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "one")
    wrapper.node.props.label = "Logger A"
    _reload(graph, wrapper)
    assert wrapper.node.props.label == ""

    assert editor.apply_previous_setup([wrapper.node_id])

    assert wrapper.node.props.label == "Logger A"


def test_dismiss_drops_it_and_undo_brings_it_back(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "one")
    _reload(graph, wrapper)
    label = _print_cls().class_identity.label

    assert editor.dismiss_previous_setup([wrapper.node_id])

    assert wrapper.previous_setup is None
    assert _message(wrapper) == "Hello, World!"
    assert editor.history_manager.get_undo_description() == f"Dismiss previous setup {label}"
    assert editor.undo()
    graph._validation.force_immediate_validation()
    assert wrapper.previous_setup is not None


def test_reset_dismisses_and_undo_of_reset_restores(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "one")
    _reload(graph, wrapper)

    assert editor.reset_nodes([wrapper.node_id])

    assert wrapper.previous_setup is None
    assert wrapper.state.warnings == []
    assert editor.undo()
    graph._validation.force_immediate_validation()
    assert wrapper.previous_setup is not None
    assert [w.kind for w in wrapper.state.warnings] == ["previous_setup"]


def test_apply_and_dismiss_refuse_a_node_without_a_previous_setup(graph_with_library_system, library_system):
    graph, editor = _graph_with_editor(library_system)
    untouched = _fresh_printer(graph)

    assert editor.apply_previous_setup([untouched.node_id]) is False
    assert editor.dismiss_previous_setup([untouched.node_id]) is False
    assert editor.apply_previous_setup([]) is False
    assert editor.apply_previous_setup(["missing"]) is False
    assert not editor.history_manager.can_undo()


def test_a_class_label_or_version_change_alone_keeps_nothing(
    graph_with_library_system, library_system, ledger
):
    """identity and library describe the class, not the user's setup; a load never restores them."""
    from haywire.core.graph.validation import ValidationManager

    graph, _editor = _graph_with_editor(library_system)
    wrapper = _fresh_printer(graph)
    before = _setup(wrapper)
    before["identity"] = {**before.get("identity", {}), "label": "Old label"}
    before["library"] = {**before.get("library", {}), "version": "0.0.1"}

    ValidationManager._keep_previous_setup(wrapper, before)

    assert wrapper.previous_setup is None
    assert ledger.query().total == 0


def test_apply_refuses_when_the_previous_setup_vanished_meanwhile(graph_with_library_system, library_system):
    """A pass that clears the setup between the check and the capture must not turn Apply into a Reset."""
    graph, editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "one")
    _reload(graph, wrapper)
    wrapper.node.ports["message"].set_value("since")

    assert (
        editor._rebuild_previous_setup([wrapper.node_id], "Apply previous setup", lambda _w: None) is False
    )

    assert _message(wrapper) == "since"
    assert not editor.history_manager.can_undo()


def test_the_ledger_row_names_what_differs(graph_with_library_system, library_system, ledger):
    graph, _editor = _graph_with_editor(library_system)
    wrapper = _printer(graph, "one")

    _reload(graph, wrapper)

    (entry,) = ledger.query().entries
    assert "ports/message" in entry.details["differs"]
    assert "Differs" in entry.format_detailed()


def test_a_measured_size_alone_keeps_nothing(graph_with_library_system, library_system, ledger):
    """On an auto axis the canvas measures the size and writes it back; it is not the user's setup."""
    graph, _editor = _graph_with_editor(library_system)
    wrapper = _fresh_printer(graph)
    wrapper.node.props.width = 312
    wrapper.node.props.height = 148
    wrapper.node.props.stage_width = 280

    _reload(graph, wrapper)

    assert wrapper.previous_setup is None
    assert ledger.query().total == 0


def test_a_manual_size_is_kept(graph_with_library_system, library_system):
    graph, _editor = _graph_with_editor(library_system)
    wrapper = _fresh_printer(graph)
    wrapper.node.props.size_adapt = "manual_width"
    wrapper.node.props.width = 420

    _reload(graph, wrapper)

    assert wrapper.previous_setup is not None


def test_a_moved_node_still_clears_once_the_rebuild_matches(graph_with_library_system, library_system):
    graph, _editor = _graph_with_editor(library_system)
    wrapper = _fresh_printer(graph)
    wrapper.set_previous_setup(_setup(wrapper))
    wrapper.node.props.set_position((900.0, 700.0))

    _reload(graph, wrapper)

    assert wrapper.previous_setup is None
