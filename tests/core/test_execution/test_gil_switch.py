"""The thread switch interval is short while graphs run."""

import sys

import pytest
from haywire.core.di.config import LibrarySystemService
from haywire.core.execution import gil_switch
from haywire.core.execution.interpreter import Interpreter
from haywire.core.graph.base import BaseGraph

from tests.conftest import make_node


@pytest.fixture(autouse=True)
def _restored():
    # Interpreters that earlier tests never stopped may still hold the interval.
    while gil_switch.running_graphs():
        gil_switch.restore_after_run()
    yield
    while gil_switch.running_graphs():
        gil_switch.restore_after_run()


@pytest.mark.unit
def test_the_first_graph_shortens_and_the_last_restores():
    before = sys.getswitchinterval()
    gil_switch.shorten_for_run()
    assert sys.getswitchinterval() == pytest.approx(gil_switch.RUN_SWITCH_INTERVAL)
    gil_switch.shorten_for_run()
    gil_switch.restore_after_run()
    assert sys.getswitchinterval() == pytest.approx(gil_switch.RUN_SWITCH_INTERVAL), "one graph still runs"
    gil_switch.restore_after_run()
    assert sys.getswitchinterval() == pytest.approx(before)


@pytest.mark.unit
def test_an_unpaired_restore_changes_nothing():
    before = sys.getswitchinterval()
    gil_switch.restore_after_run()
    assert sys.getswitchinterval() == pytest.approx(before)
    assert gil_switch.running_graphs() == 0


@pytest.mark.integration
def test_an_interpreter_holds_the_short_interval_between_start_and_stop(
    graph_with_library_system: BaseGraph, library_system: LibrarySystemService
):
    from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode

    make_node(graph_with_library_system, TestBeginPlayNode.class_identity.registry_key, position=(0, 0))
    interpreter = Interpreter()
    interpreter.load_graph(graph_with_library_system)
    before = sys.getswitchinterval()

    interpreter.start_execution()
    interpreter.start_execution()  # a second start while running holds nothing more
    assert gil_switch.running_graphs() == 1
    assert sys.getswitchinterval() == pytest.approx(gil_switch.RUN_SWITCH_INTERVAL)

    interpreter.stop_execution()
    assert gil_switch.running_graphs() == 0
    assert sys.getswitchinterval() == pytest.approx(before)


@pytest.mark.integration
def test_shutdown_restores_an_interval_that_was_not_stopped(
    graph_with_library_system: BaseGraph, library_system: LibrarySystemService
):
    from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode

    make_node(graph_with_library_system, TestBeginPlayNode.class_identity.registry_key, position=(0, 0))
    interpreter = Interpreter()
    interpreter.load_graph(graph_with_library_system)
    interpreter.start_execution()
    interpreter.shutdown()
    assert gil_switch.running_graphs() == 0
