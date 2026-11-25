"""A model port with no model chosen: the run leaves a ledger entry naming the node and the cause (#244)."""

from __future__ import annotations

import importlib
import threading
from typing import Any

import pytest

from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.execution.event_source import Trigger
from haywire.core.execution.vm import HaywireVM
from haywire.core.volumes import VolumeStore
from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


@pytest.fixture
def ledger() -> Any:
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=500)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


def test_a_run_with_no_model_chosen_leaves_a_ledger_entry(
    graph_with_library_system: Any, models_env: VolumeStore, ledger: ErrorLedger
) -> None:
    graph = graph_with_library_system
    begin = _add(graph, "haybale_core.nodes.events.begin_play_event", "BeginPlayEventNode")
    resolve = _add(graph, "haybale_models.nodes.resolve_model", "ResolveModelNode")
    printer = _add(graph, "haybale_core.nodes.print", "PrintNode")
    graph.create_edge_wrapper(begin.node_id, "exec", printer.node_id, "exec")
    graph.create_edge_wrapper(resolve.node_id, "size", printer.node_id, "message")

    graph.force_validation()
    flows = FlowAssemblyManager().assemble_graph(graph)
    flow = next(f for f in flows if f.get_entry_node_id() == begin.node_id)
    trigger = Trigger(source_key=flow.get_subscription_key(), payload={}, timestamp=0.0)
    runner = threading.Thread(target=lambda: HaywireVM().execute_control_flow(flow, trigger))
    runner.start()
    runner.join()

    rows = [e.to_dict() for e in ledger.query().entries]
    assert [(r["node_id"], r["graph_id"], r["cause"]) for r in rows] == [
        (resolve.node_id, graph.graph_id, "ModelMissing: no model chosen")
    ], rows
    from haybale_graph_editor.farmhands.editor_tools import _state_row

    assert _state_row(resolve.wrapper)["errors"] == [
        {
            "stage": "error_runtime",
            "message": "Error executing node 'Resolve Model'",
            "cause": "ModelMissing: no model chosen",
        }
    ]
