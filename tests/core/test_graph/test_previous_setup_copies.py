"""A previous setup stays with its node: moves keep it, copies drop it. See ADR 0062."""

from __future__ import annotations

import json
from typing import Any

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.clipboard import build_clipboard_payload
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.macro.promote import macro_document

pytestmark = pytest.mark.integration


def _print_key() -> str:
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return TestPrintNode.class_identity.registry_key


def _graph_and_editor(library_system) -> tuple[BaseGraph, Editor]:
    graph = BaseGraph("Copies", validation_scheduler=SyncScheduler())
    return graph, Editor(graph, library_system.get_node_factory())


def _held_printer(graph: BaseGraph) -> Any:
    wrapper: Any = graph.create_node_wrapper(_print_key(), position=(10.0, 10.0))
    graph._validation.force_immediate_validation()
    wrapper.set_previous_setup(wrapper.serialize()["node_data"])
    return wrapper


def _group(graph: BaseGraph, editor: Editor, node_ids: list[str]) -> tuple[Any, Any]:
    from haywire.barn.builtin.nodes.graph_node import GraphNode
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode

    host_id, _ = editor.collapse_to_group(
        node_ids,
        GraphNode.class_identity.registry_key,
        SubgraphInputNode.class_identity.registry_key,
        SubgraphOutputNode.class_identity.registry_key,
    )
    assert host_id is not None
    host: Any = graph.get_node_wrapper(host_id)
    return host, graph.get_subgraph(host.node.subgraph_key)


def _held_inside(definition: Any) -> list[Any]:
    return [w for w in definition.node_wrappers.values() if w.previous_setup is not None]


def test_a_pasted_node_holds_no_previous_setup(graph_with_library_system, library_system):
    graph, editor = _graph_and_editor(library_system)
    held = _held_printer(graph)

    payload = build_clipboard_payload(graph, [held.node_id], [], "session")
    pasted = editor.paste_clipboard(payload, 400.0, 400.0)

    assert "previous_setup" not in json.dumps(payload)
    assert pasted is not None
    (new_id,) = pasted[0]
    copy: Any = graph.get_node_wrapper(new_id)
    assert copy.previous_setup is None
    assert held.previous_setup is not None


def test_a_pasted_group_holds_none_inside_either(graph_with_library_system, library_system):
    graph, editor = _graph_and_editor(library_system)
    held = _held_printer(graph)
    host, definition = _group(graph, editor, [held.node_id])
    assert _held_inside(definition)

    payload = build_clipboard_payload(graph, [host.node_id], [], "session")
    pasted = editor.paste_clipboard(payload, 600.0, 600.0)

    assert "previous_setup" not in json.dumps(payload)
    assert pasted is not None
    (new_host_id,) = pasted[0]
    new_host: Any = graph.get_node_wrapper(new_host_id)
    assert _held_inside(graph.get_subgraph(new_host.node.subgraph_key)) == []


def test_a_macro_document_holds_no_previous_setup(graph_with_library_system, library_system):
    graph, editor = _graph_and_editor(library_system)
    held = _held_printer(graph)
    _host, definition = _group(graph, editor, [held.node_id])
    assert _held_inside(definition)

    assert "previous_setup" not in json.dumps(macro_document(definition))
    assert _held_inside(definition)


def test_collapse_to_group_keeps_it(graph_with_library_system, library_system):
    graph, editor = _graph_and_editor(library_system)
    held = _held_printer(graph)
    kept = held.previous_setup

    _host, definition = _group(graph, editor, [held.node_id])

    (inside,) = _held_inside(definition)
    assert inside.previous_setup == kept
