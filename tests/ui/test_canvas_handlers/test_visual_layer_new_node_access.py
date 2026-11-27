"""New Node and Clone to Library write into a library, so their handler needs the admin tier."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from nicegui import ui

import haybale_graph_editor._new_node_flow as new_node_flow
import haywire.core.authoring as authoring
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haywire.api.workbench import AccessTier
from haywire.core.di import config
from haywire.ui.components.graph.event_definitions import OpenNewNodeWizardEvent
from tests.conftest import edit_route

pytestmark = pytest.mark.unit


def _open_wizard(
    monkeypatch, tier: AccessTier, event: OpenNewNodeWizardEvent
) -> tuple[MagicMock, MagicMock]:
    """Send ``event`` as a ``tier`` principal; returns ``(show_new_node_flow, notify)``."""
    wrapper = SimpleNamespace(node=SimpleNamespace(props=MagicMock()))
    graph = MagicMock()
    graph.get_node_wrapper.side_effect = lambda node_id: wrapper if node_id == "card" else None
    context = MagicMock()
    context.can_access.side_effect = tier.satisfies
    handler = VisualLayerHandlers(
        graph=graph,
        route=edit_route(MagicMock()),
        skin_factory=MagicMock(),
        canvas_vue=MagicMock(),
        context=context,
    )
    handler.channel = MagicMock()
    handler.channel.to_canvas.return_value = (0.0, 0.0)
    show = MagicMock()
    monkeypatch.setattr(new_node_flow, "show_new_node_flow", show)
    monkeypatch.setattr(new_node_flow, "new_node_flow", MagicMock())
    monkeypatch.setattr(new_node_flow, "EditorNewNodeHost", MagicMock())
    monkeypatch.setattr(authoring, "is_clone_source", lambda cls: True)
    monkeypatch.setattr(config, "get_library_system", MagicMock())
    notify = MagicMock()
    monkeypatch.setattr(ui, "notify", notify)

    handler.process_open_new_node_wizard(event)
    return show, notify


_NEW_NODE = OpenNewNodeWizardEvent(position={"x": 10, "y": 20})
_CLONE = OpenNewNodeWizardEvent(node_id="card")


def test_an_edit_principal_cannot_open_new_node(monkeypatch):
    show, notify = _open_wizard(monkeypatch, AccessTier.EDIT, _NEW_NODE)

    show.assert_not_called()
    assert "admin" in notify.call_args.args[0]


def test_an_edit_principal_cannot_clone_to_a_library(monkeypatch):
    show, notify = _open_wizard(monkeypatch, AccessTier.EDIT, _CLONE)

    show.assert_not_called()
    assert "admin" in notify.call_args.args[0]


def test_an_admin_principal_opens_new_node(monkeypatch):
    show, _ = _open_wizard(monkeypatch, AccessTier.ADMIN, _NEW_NODE)

    show.assert_called_once()


def test_an_admin_principal_opens_clone_to_library(monkeypatch):
    show, _ = _open_wizard(monkeypatch, AccessTier.ADMIN, _CLONE)

    show.assert_called_once()
