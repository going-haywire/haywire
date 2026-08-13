"""Tests for the PropertiesEditor event-bus integration.

Verifies that:

- ``cast(Any, PropertiesEditor)._panel_registry`` returns the registry from
  ``context.app.library_service.get_panel_registry()``.
- The migrated editor no longer carries the legacy ``_RELEVANT_SIGNALS``,
  ``redraw_on_signal`` / ``on_signal``, or framework-side
  ``get_panel_registry`` surface.
- After first-draw wiring, publishing a signal a registered panel cares
  about redraws the wrapper (end-to-end through the editor seam).
- ``cleanup()`` drops all subscriptions and clears the coordinator.
- Hot-reload of PropertiesEditor cleans up the old instance's subscriptions.
- The editor handles absent / raising panel-registry chains gracefully.

Pure subscription-mechanics tests (signal union, catalog reconciliation,
resilience) are in ``tests/ui/panel/test_redraw_coordinator.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional, cast
from unittest.mock import MagicMock


from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.session.session import Session
from haywire.core.session.signals import SelectionMoved
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.editor.wrapper import EditorWrapper
from haywire.ui.panel import PanelRegistry

from haybale_studio.editors.properties_editor import PropertiesEditor
from haybale_graph_editor.panels.properties.setting.node import NodeSettingsPanel


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    folder_path="/tmp/fake",
    module_name="fake",
    name="fake",
)


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def _make_session_with_panel_registry(
    panel_registry: Optional[PanelRegistry],
) -> Session:
    """..."""
    library_service = MagicMock()
    library_service.get_panel_registry.return_value = panel_registry
    app = MagicMock()
    app.library_service = library_service

    session = Session(
        project_state=app,
        workspace_manager=MagicMock(),
        session_manager=MagicMock(),
    )
    session.context.app = app
    return session


def _make_properties_editor_wrapper(session: Session) -> EditorWrapper:
    """Build a real ``EditorWrapper`` around ``PropertiesEditor`` and
    instantiate it (without calling ``draw``).

    Returns the wrapper; callers can read ``wrapper.instance`` for the
    editor, set the redraw callback, and trigger the panel-subscription
    path via ``_wire_coordinator(editor, context)``.
    """
    wrapper = EditorWrapper(
        editor_key=PropertiesEditor.class_identity.registry_key,
        editor_cls=PropertiesEditor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True
    return wrapper


def _wire_coordinator(editor, context) -> None:
    """Drive the editor's first-draw subscription wiring without a full
    NiceGUI render.

    ``PropertiesEditor.draw()`` resolves the panel registry and, on
    success, constructs + starts a PanelRedrawCoordinator. We replicate
    exactly that gate here so tests can exercise subscription behaviour
    without building the two-column layout.
    """
    editor._context = context
    registry = editor._resolve_panel_registry(context)
    if registry is not None and cast(Any, editor)._coordinator is None:
        from haywire.ui.panel import PanelRedrawCoordinator

        cast(Any, editor)._coordinator = PanelRedrawCoordinator(
            registry=registry,
            session=context.session,
            on_redraw=editor.wrapper.redraw,
            focus_provider=lambda: editor._compute_toolbar_focuses(registry),
        )
        cast(Any, editor)._coordinator.start()


# ----------------------------------------------------------------------
# Editor surface
# ----------------------------------------------------------------------


def test_properties_editor_panel_registry_helper_returns_app_registry():
    panel_registry = PanelRegistry()
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None
    assert cast(Any, editor)._panel_registry(session.context) is panel_registry


def test_properties_editor_no_longer_carries_legacy_signal_surface():
    assert not hasattr(PropertiesEditor, "_RELEVANT_SIGNALS")
    assert "redraw_on_signal" not in PropertiesEditor.__dict__
    assert "on_signal" not in PropertiesEditor.__dict__
    assert "get_panel_registry" not in PropertiesEditor.__dict__


# ----------------------------------------------------------------------
# Panel-driven redraw subscriptions (via coordinator seam)
# ----------------------------------------------------------------------


def test_editor_redraws_on_panel_signal_after_first_draw():
    """End-to-end through the editor seam: after wiring, publishing a
    signal a registered panel cares about redraws the wrapper."""
    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    _wire_coordinator(editor, session.context)
    session.publish(SelectionMoved())

    assert redraws == [wrapper]


def test_cleanup_stops_redraws_and_clears_coordinator():
    """After cleanup, a previously-subscribed signal no longer redraws,
    and the coordinator reference is cleared."""
    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    _wire_coordinator(editor, session.context)
    assert cast(Any, editor)._coordinator is not None

    editor.cleanup()
    assert cast(Any, editor)._coordinator is None

    session.publish(SelectionMoved())
    assert redraws == []


def test_hot_reload_triggers_cleanup_and_stops_redraws():
    """A CLASS_RELOADED event on the wrapper calls instance.cleanup() on
    the old instance, after which its subscriptions no longer redraw."""
    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    _wire_coordinator(editor, session.context)
    assert cast(Any, editor)._coordinator is not None

    class _ReloadedPropertiesEditor(PropertiesEditor):
        pass

    reload_event = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_RELOADED,
        registry_key=PropertiesEditor.class_identity.registry_key,
        affected_class=_ReloadedPropertiesEditor,
        library_identity=_FAKE_LIBRARY_IDENTITY,
    )
    wrapper._on_lifecycle_event(reload_event)

    assert cast(Any, editor)._coordinator is None
    redraws.clear()
    session.publish(SelectionMoved())
    assert redraws == []


def test_no_coordinator_when_chain_returns_none():
    """get_panel_registry() returning None → no coordinator, no crash."""
    session = _make_session_with_panel_registry(None)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    _wire_coordinator(editor, session.context)
    assert cast(Any, editor)._coordinator is None


def test_no_coordinator_when_chain_is_missing():
    """A context whose app lacks library_service → no coordinator."""
    session = Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=MagicMock(),
    )
    session.context.app = SimpleNamespace()

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    _wire_coordinator(editor, session.context)
    assert cast(Any, editor)._coordinator is None


def test_no_coordinator_when_get_panel_registry_raises():
    """get_panel_registry() raising is treated as 'absent' — logged, no
    coordinator, no propagation."""
    library_service = SimpleNamespace(
        get_panel_registry=MagicMock(side_effect=RuntimeError("intentional bad lookup"))
    )
    session = Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=MagicMock(),
    )
    session.context.app = SimpleNamespace(library_service=library_service)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    _wire_coordinator(editor, session.context)  # must not raise
    assert cast(Any, editor)._coordinator is None
