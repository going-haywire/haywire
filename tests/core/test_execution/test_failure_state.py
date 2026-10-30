"""A raising node is failed and stays dirty; a normal return clears it (ADR 0066)."""

import importlib
from typing import Any

import pytest

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.execution.vm import HaywireVM
from haywire.core.execution.failures import failure_counts
from haywire.core.execution.flow import LocalizedDataFlow
from tests.conftest import make_node

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _release_failures(graph_with_library_system):
    """Clear every node's failed/blocked state after a test: the test graph is not cleaned up."""
    before = (failure_counts.failed, failure_counts.flagged)
    yield
    for wrapper in list(graph_with_library_system.node_wrappers.values()):
        if not wrapper.is_cleaned_up:
            wrapper.node._clear_failed()
            wrapper.node._clear_blocked()
    assert (failure_counts.failed, failure_counts.flagged) == before


def _odd_raiser(graph: Any) -> Any:
    """A data node that raises on odd ``x`` and passes even ``x`` on."""
    cls = importlib.import_module("haybale_testing.nodes.benchmark.bench_loop_raise_node").BenchLoopRaiseNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _run(node: Any, x: float) -> None:
    """Evaluate a one-node data flow, the way the VM runs a data node."""
    node.ports["x"].set_value(x)
    flow = LocalizedDataFlow(control_node_id="k", execution_sequence=[node])
    HaywireVM()._evaluate_data_flow(flow, ExecutionContext(global_ctx={}, local_ctx={}))


@pytest.fixture
def count_before():
    return failure_counts.failed


def test_a_raising_node_is_failed_and_stays_dirty(graph_with_library_system, count_before):
    node = _odd_raiser(graph_with_library_system)

    _run(node, 1.0)

    assert node.failed
    assert "x" in node._has_dirty_ports
    assert node.wrapper.state.error_runtime is not None
    assert failure_counts.failed == count_before + 1


def test_a_normal_return_clears_failed(graph_with_library_system, count_before):
    node = _odd_raiser(graph_with_library_system)
    _run(node, 1.0)

    _run(node, 2.0)

    assert not node.failed
    assert not node._has_dirty_ports
    assert node.ports["y"].get_value() == 2.0
    assert failure_counts.failed == count_before


def test_failing_twice_counts_once(graph_with_library_system, count_before):
    node = _odd_raiser(graph_with_library_system)
    _run(node, 1.0)
    _run(node, 3.0)
    assert failure_counts.failed == count_before + 1
    _run(node, 4.0)
    assert failure_counts.failed == count_before


def test_on_validate_raising_puts_the_dirty_ports_back(graph_with_library_system, count_before):
    node = _odd_raiser(graph_with_library_system)

    def boom(_context: Any) -> None:
        raise RuntimeError("bad setup")

    node.on_validate = boom
    _run(node, 2.0)

    assert node.failed
    assert "x" in node._has_dirty_ports


def test_cleanup_while_failed_releases_the_count(graph_with_library_system, count_before):
    node = _odd_raiser(graph_with_library_system)
    _run(node, 1.0)
    assert failure_counts.failed == count_before + 1

    node.wrapper.cleanup()

    assert failure_counts.failed == count_before


def test_a_clean_data_node_still_skips_its_worker(graph_with_library_system, count_before):
    node = _odd_raiser(graph_with_library_system)
    node._has_dirty_ports.clear()

    assert node._execute(ExecutionContext(global_ctx={}, local_ctx={})) is None
    assert not node.failed
