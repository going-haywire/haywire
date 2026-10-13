"""A double-click on a Graph-node card ends in an open level, labelled with the Group.

The browser harness stops at the published ``SubgraphNavigation`` (see
``tests/ui/harness/test_enter_by_double_click.py``); this is the other half. The
canvas handler publishes that signal with the card's node id, and the editor
holding the graph answers it by opening the Group and showing it.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from haywire.core.signals import SubgraphNavigation
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haywire.ui.components.graph.event_definitions import EnterGroupEvent

from tests.graph_editor.test_graph_editor_levels import _card, _definition, _editor

pytestmark = pytest.mark.unit


def test_the_enter_event_publishes_the_navigation_the_editor_answers():
    editor, context, document = _editor()
    definition = _definition(key="sg_a", label="Filter")
    document.editor.graph.node_wrappers["GraphNode_1"] = _card(definition)
    document.editor.graph.subgraphs["sg_a"] = definition

    # The canvas side: the handler turns EnterGroupEvent into the signal.
    handlers = MagicMock()
    handlers.context = MagicMock()
    handlers.editor.graph.graph_id = document.editor.graph.graph_id
    VisualLayerHandlers.process_enter_group(handlers, EnterGroupEvent(node_id="GraphNode_1"))
    (signal,), _ = handlers.context.session.publish.call_args
    assert isinstance(signal, SubgraphNavigation)
    assert signal.node_id == "GraphNode_1"

    # The editor side: the same signal opens the Group and shows it.
    editor._on_subgraph_navigation(context, signal)

    assert editor._active_level == "sg_a"
    # The breadcrumb and the level bar both draw each open level's display name.
    assert [level.container.display_name for level in editor._descent_stack()] == ["main.haywire", "Filter"]
    editor._render_level_bar.assert_called()  # type: ignore[attr-defined]
    editor._update_header.assert_called()  # type: ignore[attr-defined]
