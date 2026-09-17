"""A loopback node returning an outlet id that names no port ends its branch.

The worker contract lets a worker return any string (``_parse_worker_result``
only type-checks it), and the Graph-node/boundary-node crossings return outlet
ids that deliberately name no port. A strict lookup in the loopback check would
raise out of the VM loop, and the scheduler's frame-level handler logs it
against the *flow* — so the frame is abandoned with no error on any node.
"""

from unittest.mock import MagicMock

import pytest

from haywire.core.execution.flow import ControlFlowGraph, ControlNodeInfo
from haywire.core.execution.vm import HaywireVM

pytestmark = pytest.mark.unit


def _node(node_id: str, returns: str | None, ports: dict | None = None) -> MagicMock:
    node = MagicMock()
    node.node_id = node_id
    node.ports = ports if ports is not None else {}
    node._execute.return_value = returns
    return node


def _flow(control_nodes: dict[str, ControlNodeInfo], entry_id: str) -> MagicMock:
    control_graph = ControlFlowGraph(entry_node=control_nodes[entry_id].node)
    control_graph.control_nodes = control_nodes

    flow = MagicMock()
    flow.is_assembled.return_value = True
    flow.control_graph = control_graph
    flow.get_entry_node_id.return_value = entry_id
    flow.get_nodes_with_on_frame_start.return_value = []
    flow.get_nodes_with_on_frame_end.return_value = []
    flow.graph_ref.variables = {}
    return flow


def test_a_loopback_node_returning_an_unknown_outlet_id_ends_the_branch():
    """No KeyError, no frame abort — the branch just ends."""
    node = _node("loop", returns="enter_subgraph")  # no such port
    info = ControlNodeInfo(node=node, is_loopback=True)

    exec_count = HaywireVM().execute_control_flow(_flow({"loop": info}, "loop"), MagicMock())

    assert exec_count == 1
    node._execute.assert_called_once()


def test_a_real_loopback_outlet_still_pushes_and_re_enters():
    """The guard must not have become permissive about actual loopback outlets."""
    body = MagicMock()
    body.needs_loopback = True
    done = MagicMock()
    done.needs_loopback = False

    # Returns the loopback outlet once, then the exit outlet on re-entry.
    node = _node("loop", returns=None, ports={"body": body, "done": done})
    node._execute.side_effect = ["body", "done"]

    tail = _node("tail", returns=None)
    info = ControlNodeInfo(node=node, is_loopback=True, outlet_map={"body": ("tail", "exec")})
    tail_info = ControlNodeInfo(node=tail)

    flow = _flow({"loop": info, "tail": tail_info}, "loop")
    exec_count = HaywireVM().execute_control_flow(flow, MagicMock())

    # loop → tail → (branch ends, pop) → loop again
    assert exec_count == 3
    assert node._execute.call_count == 2
