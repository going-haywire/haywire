"""End-to-end test for the PropertiesEditor event-bus migration.

Verifies that:
- PropertiesEditor's ``_panel_registry`` helper returns the registry
  from ``context.app.library_service.get_panel_registry()``.
- When a panel declares ``redraw_on=(SelectionMoved, ...)`` and is
  registered against PropertiesEditorActions, the framework
  auto-subscribes the editor's wrapper to the panel's events (resolved
  via the same context chain). Publishing ``SelectionMoved`` then
  triggers ``wrapper.redraw()``.
- The migrated PropertiesEditor no longer carries the legacy
  ``_RELEVANT_SIGNALS`` / ``redraw_on_signal`` surface.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.library.identity import LibraryIdentity
from haywire.core.session.session import Session
from haywire.core.session.signals_and_lifecycle import SelectionMoved
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.editor.wrapper import EditorWrapper
from haywire.ui.panel import PanelRegistry

from haybale_studio.editors.properties_editor import PropertiesEditor
from haybale_studio.panels.node_settings import NodeSettingsPanel


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    description="test",
    url="",
    help_url="",
    author="",
    author_url="",
    folder_path="/tmp/fake",
    module_name="fake",
    id="fake",
)


def _make_session_with_panel_registry(panel_registry: PanelRegistry) -> Session:
    """Build a Session whose context.app.library_service routes to ``panel_registry``."""
    library_service = MagicMock()
    library_service.get_panel_registry.return_value = panel_registry
    app = MagicMock()
    app.library_service = library_service

    session = Session(
        project_state=app,
        workspace_manager=MagicMock(),
        session_manager=MagicMock(),
    )
    # SessionContext copies project_state into ``app`` at construction time;
    # patch the resolved attribute too so the wrapper's resolution chain
    # hits our stub.
    session.context.app = app
    return session


def test_properties_editor_panel_registry_helper_returns_app_registry():
    panel_registry = PanelRegistry()
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = EditorWrapper(
        editor_key=PropertiesEditor.class_identity.registry_key,
        editor_cls=PropertiesEditor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True
    editor = wrapper.instance
    assert editor is not None
    assert editor._panel_registry(session.context) is panel_registry


def test_properties_editor_no_longer_carries_legacy_signal_surface():
    """The migrated editor must not expose the old _RELEVANT_SIGNALS,
    redraw_on_signal / on_signal overrides, or a get_panel_registry
    framework hook (the framework now resolves the registry directly
    from the session's context).
    """
    assert not hasattr(PropertiesEditor, "_RELEVANT_SIGNALS")
    assert "redraw_on_signal" not in PropertiesEditor.__dict__
    assert "on_signal" not in PropertiesEditor.__dict__
    assert "get_panel_registry" not in PropertiesEditor.__dict__


def test_selection_moved_triggers_wrapper_redraw_via_panel_redraw_on():
    """The original PropertiesEditor bug, fixed structurally.

    Register NodeSettingsPanel (declares redraw_on=(SelectionMoved, ...))
    in the panel registry, then publish SelectionMoved. The framework's
    panel-union subscription should fire wrapper.redraw()."""
    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = EditorWrapper(
        editor_key=PropertiesEditor.class_identity.registry_key,
        editor_cls=PropertiesEditor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    session.publish(SelectionMoved())

    assert redraws == [wrapper]


def test_unregistered_panel_events_do_not_redraw():
    """If no registered panel cares about an event, publishing it must
    NOT redraw the wrapper."""
    from dataclasses import dataclass
    from haywire.core.session.signals_and_lifecycle import ContextSignal

    @dataclass(frozen=True)
    class _UnrelatedEvent(ContextSignal):
        pass

    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = EditorWrapper(
        editor_key=PropertiesEditor.class_identity.registry_key,
        editor_cls=PropertiesEditor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    session.publish(_UnrelatedEvent())

    assert redraws == []
