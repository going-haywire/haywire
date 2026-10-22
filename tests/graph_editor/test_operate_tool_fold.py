"""``graph_editor_operate`` sets a port inside a closed fold, and leaves the fold closed.

Opening a fold is itself an operate-level action, so refusing the write would only
cost the agent a round trip; the card shows the value once the fold is open.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from haywire.core.graph.editor import Editor

pytestmark = pytest.mark.integration


def test_a_port_inside_a_closed_fold_can_be_operated(graph_with_library_system, library_system, monkeypatch):
    from haybale_graph_editor.farmhands import editor_tools
    from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

    editor = Editor(graph_with_library_system, library_system.get_node_factory())
    wrapper: Any = graph_with_library_system.create_node_wrapper(
        FoldProbeNode.class_identity.registry_key, position=(10.0, 10.0)
    )
    assert isinstance(wrapper.node, FoldProbeNode)
    epsilon = wrapper.node.ports["epsilon"]
    assert epsilon.parent_fold is not None
    fold = wrapper.node.ports[epsilon.parent_fold]
    assert fold.get_value() is False, "the probe's Advanced fold starts closed"
    monkeypatch.setattr(editor_tools, "_editor", lambda ctx, binding_id: editor)
    ctx: Any = SimpleNamespace(broadcast=lambda signal: None)

    result = asyncio.run(
        editor_tools.GraphEditorOperateTool().run(ctx, "graph", wrapper.node_id, "epsilon", 0.5)
    )

    assert epsilon.get_value() == 0.5
    assert fold.get_value() is False
    assert "epsilon" in result["summary"]
