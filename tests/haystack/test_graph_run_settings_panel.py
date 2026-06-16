# tests/haystack/test_graph_run_settings_panel.py
"""GraphRunSettingsPanel — poll + resolution logic (no live NiceGUI render)."""

from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def _ctx_with_active_graph(graph, container):
    """Build a SessionContext double exposing EditState.active_graph and
    GraphAppState.get_by_graph."""
    ctx = MagicMock()
    edit_state = MagicMock()
    edit_state.active_graph = graph
    graph_app_state = MagicMock()
    graph_app_state.get_by_graph.return_value = container
    from haybale_graph_editor.state.edit_state import EditState
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    ctx.data.__getitem__.side_effect = lambda k: edit_state if k is EditState else MagicMock()
    ctx.app_data.__getitem__.side_effect = lambda k: graph_app_state if k is GraphAppState else MagicMock()
    return ctx


def test_poll_false_when_no_active_graph():
    from haybale_haystack.panels.properties.introspect.graph_run_settings_panel import GraphRunSettingsPanel

    ctx = _ctx_with_active_graph(graph=None, container=None)
    assert GraphRunSettingsPanel.poll(ctx) is False


def test_poll_false_when_active_graph_has_no_entry():
    from haybale_haystack.panels.properties.introspect.graph_run_settings_panel import GraphRunSettingsPanel

    ctx = _ctx_with_active_graph(graph=MagicMock(), container=None)
    assert GraphRunSettingsPanel.poll(ctx) is False


def test_poll_true_when_entry_resolves():
    from haybale_haystack.panels.properties.introspect.graph_run_settings_panel import GraphRunSettingsPanel
    from haybale_haystack.graph_entry import GraphEntry

    g = MagicMock()
    entry = GraphEntry(graph=g, editor=MagicMock())
    ctx = _ctx_with_active_graph(graph=g, container=entry)
    assert GraphRunSettingsPanel.poll(ctx) is True
