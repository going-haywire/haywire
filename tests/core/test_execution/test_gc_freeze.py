"""The collector skips the long-lived heap while graphs run."""

import gc

import pytest
from haywire.core.di.config import LibrarySystemService
from haywire.core.execution import gc_freeze
from haywire.core.execution.interpreter import Interpreter
from haywire.core.graph.base import BaseGraph

from tests.conftest import make_node


def _release_all() -> None:
    # Interpreters that earlier tests never stopped may still hold the freeze.
    while gc_freeze.running_graphs():
        gc_freeze.unfreeze_after_run()
    gc.unfreeze()


@pytest.fixture(autouse=True)
def _released():
    _release_all()
    yield
    _release_all()


@pytest.fixture
def calls(monkeypatch) -> list[str]:
    """Record every ``gc.freeze`` and ``gc.unfreeze``, still running them.

    The frozen count is no record of them: threads that earlier tests left running
    free frozen objects at any time, so the count drifts between two reads.
    """
    recorded: list[str] = []
    freeze, unfreeze = gc.freeze, gc.unfreeze

    def _freeze() -> None:
        recorded.append("freeze")
        freeze()

    def _unfreeze() -> None:
        recorded.append("unfreeze")
        unfreeze()

    monkeypatch.setattr(gc, "freeze", _freeze)
    monkeypatch.setattr(gc, "unfreeze", _unfreeze)
    return recorded


@pytest.mark.unit
def test_the_first_graph_freezes_and_the_last_unfreezes(calls):
    gc_freeze.freeze_for_run()
    frozen = gc.get_freeze_count()
    assert calls == ["freeze"]
    assert frozen > 0
    gc_freeze.freeze_for_run()
    assert calls == ["freeze"], "a second graph does not freeze again"
    gc_freeze.unfreeze_after_run()
    assert calls == ["freeze"], "one graph is still running"
    gc_freeze.unfreeze_after_run()
    assert calls == ["freeze", "unfreeze"]
    assert gc.get_freeze_count() < frozen // 10, "the heap is back with the collector"
    assert gc_freeze.running_graphs() == 0


@pytest.mark.unit
def test_an_unpaired_release_changes_nothing():
    gc_freeze.unfreeze_after_run()
    assert gc_freeze.running_graphs() == 0


@pytest.mark.integration
def test_an_interpreter_holds_the_freeze_between_start_and_stop(
    graph_with_library_system: BaseGraph, library_system: LibrarySystemService
):
    from haybale_testing.nodes.testbed.begin_play_probe import BeginPlayProbeNode

    make_node(graph_with_library_system, BeginPlayProbeNode.class_identity.registry_key, position=(0, 0))
    interpreter = Interpreter()
    interpreter.load_graph(graph_with_library_system)

    interpreter.start_execution()
    interpreter.start_execution()  # a second start while running holds nothing more
    assert gc_freeze.running_graphs() == 1
    frozen = gc.get_freeze_count()
    assert frozen > 1000

    interpreter.stop_execution()
    assert gc_freeze.running_graphs() == 0
    assert gc.get_freeze_count() < frozen // 10


@pytest.mark.integration
def test_shutdown_releases_a_freeze_that_was_not_stopped(
    graph_with_library_system: BaseGraph, library_system: LibrarySystemService
):
    from haybale_testing.nodes.testbed.begin_play_probe import BeginPlayProbeNode

    make_node(graph_with_library_system, BeginPlayProbeNode.class_identity.registry_key, position=(0, 0))
    interpreter = Interpreter()
    interpreter.load_graph(graph_with_library_system)
    interpreter.start_execution()
    interpreter.shutdown()
    assert gc_freeze.running_graphs() == 0


@pytest.mark.unit
def test_the_collector_is_off_only_while_a_pause_is_open():
    assert gc.isenabled()
    with gc_freeze.collection_paused():
        assert not gc.isenabled()
        with gc_freeze.collection_paused():
            assert not gc.isenabled()
        assert not gc.isenabled(), "an outer pause is still open"
    assert gc.isenabled()


@pytest.mark.unit
def test_a_pause_ends_when_its_block_raises():
    with pytest.raises(RuntimeError):
        with gc_freeze.collection_paused():
            raise RuntimeError("load failed")
    assert gc.isenabled()


@pytest.mark.unit
def test_a_collector_that_was_off_stays_off():
    gc.disable()
    try:
        with gc_freeze.collection_paused():
            pass
        assert not gc.isenabled()
    finally:
        gc.enable()


@pytest.mark.unit
def test_objects_built_in_a_pause_join_the_frozen_heap_while_a_graph_runs(calls):
    gc_freeze.freeze_for_run()
    with gc_freeze.collection_paused():
        kept = [[i] for i in range(5000)]
        assert calls == ["freeze"]
    assert calls == ["freeze", "freeze"], "the pause's objects are frozen when it ends"
    del kept


@pytest.mark.unit
def test_a_pause_without_a_running_graph_freezes_nothing(calls):
    with gc_freeze.collection_paused():
        kept = [[i] for i in range(5000)]
    assert calls == []
    del kept
