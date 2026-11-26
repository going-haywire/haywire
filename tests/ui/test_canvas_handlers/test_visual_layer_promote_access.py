"""Save new Macro… writes into a library, so its handler needs the admin tier."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from nicegui import ui

import haybale_graph_editor._promote_flow as promote_flow
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haywire.api.workbench import AccessTier
from haywire.core.authoring import targets
from haywire.core.di import config
from haywire.ui.components.graph.event_definitions import PromoteToMacroEvent
from tests.conftest import edit_route

pytestmark = pytest.mark.unit


def _promote(monkeypatch, tier: AccessTier) -> tuple[MagicMock, MagicMock]:
    """Send Save new Macro… on a Group as a ``tier`` principal; returns ``(show_promote_flow, notify)``."""
    wrapper = SimpleNamespace(node=SimpleNamespace(resolve_definition=lambda: SimpleNamespace()))
    graph = MagicMock()
    graph.get_node_wrapper.side_effect = lambda node_id: wrapper if node_id == "card" else None
    context = SimpleNamespace(can_access=tier.satisfies)
    handler = VisualLayerHandlers(
        graph=graph,
        route=edit_route(MagicMock()),
        skin_factory=MagicMock(),
        canvas_vue=MagicMock(),
        context=context,
    )
    show = MagicMock()
    monkeypatch.setattr(promote_flow, "show_promote_flow", show)
    monkeypatch.setattr(targets, "authoring_targets", MagicMock(return_value=[]))
    monkeypatch.setattr(config, "get_library_system", MagicMock())
    notify = MagicMock()
    monkeypatch.setattr(ui, "notify", notify)

    handler.process_promote_to_macro(PromoteToMacroEvent(node_id="card"))
    return show, notify


def test_an_edit_principal_cannot_save_a_new_macro(monkeypatch):
    show, notify = _promote(monkeypatch, AccessTier.EDIT)

    show.assert_not_called()
    assert "admin" in notify.call_args.args[0]


def test_an_admin_principal_opens_the_save_new_macro_flow(monkeypatch):
    show, _ = _promote(monkeypatch, AccessTier.ADMIN)

    show.assert_called_once()
