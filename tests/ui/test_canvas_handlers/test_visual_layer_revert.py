"""Revert to Macro names the macro in its notice, also when the template lookup fails after the swap."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from nicegui import ui

from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haywire.core.macro import source
from haywire.ui.components.graph.event_definitions import RevertToMacroEvent

from tests.conftest import edit_route

pytestmark = pytest.mark.unit

_KEY = "haybale-testing:macro:blur_stack"


def test_the_revert_notice_names_the_macro(monkeypatch):
    origin = SimpleNamespace(key=_KEY)
    definition = SimpleNamespace(label="Blur Stack", origin=origin, template_key=None)
    wrapper = SimpleNamespace(node=SimpleNamespace(resolve_definition=lambda: definition))
    graph = MagicMock()
    graph.get_node_wrapper.side_effect = lambda node_id: wrapper if node_id == "card" else None
    editor = MagicMock()
    editor.promote_to_macro.return_value = ("placement", None)
    editor.last_promotion_dropped_edges = 0
    handler = VisualLayerHandlers(
        graph=graph, route=edit_route(editor), skin_factory=MagicMock(), canvas_vue=MagicMock()
    )
    monkeypatch.setattr(handler, "sync_with_graph", MagicMock())
    monkeypatch.setattr(source, "modified_instance_origin", lambda node: origin)
    monkeypatch.setattr(source, "macro_template", lambda key: None)
    notify = MagicMock()
    monkeypatch.setattr(ui, "notify", notify)

    handler.process_revert_to_macro(RevertToMacroEvent(node_id="card"))

    assert notify.call_args.args[0] == "Reverted to Blur Stack"
