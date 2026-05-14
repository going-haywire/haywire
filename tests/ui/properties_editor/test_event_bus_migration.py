"""Tests for the PropertiesEditor event-bus integration.

Verifies that:

- ``PropertiesEditor._panel_registry`` returns the registry from
  ``context.app.library_service.get_panel_registry()``.
- The migrated editor no longer carries the legacy ``_RELEVANT_SIGNALS``,
  ``redraw_on_signal`` / ``on_signal``, or framework-side
  ``get_panel_registry`` surface.
- When a panel declares ``redraw_on=(SelectionMoved, ...)`` and is
  registered against ``PropertiesEditorActions``, the editor subscribes
  to that event on the session bus; publishing the event triggers
  ``wrapper.redraw()``.
- Unrelated events (no registered panel declares them) do NOT redraw.
- Panel-registry catalog changes (library install / panel hot-reload)
  cause the editor to recompute its subscription union and redraw.
- The editor cleanly handles sessions where the panel-registry chain is
  absent or its lookup raises.
- ``cleanup`` drops every panel-bus subscription and detaches from the
  panel registry's lifecycle channel.
- Hot-reload of PropertiesEditor itself goes through the wrapper's
  ``_instance.cleanup`` path and the new instance re-subscribes.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.session.session import Session
from haywire.core.session.events import ContextSignal, SelectionMoved
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


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def _make_session_with_panel_registry(
    panel_registry: Optional[PanelRegistry],
) -> Session:
    """Build a Session whose ``context.app.library_service.get_panel_registry()``
    returns ``panel_registry`` (or ``None`` to simulate an absent chain
    on a per-call basis)."""
    library_service = MagicMock()
    library_service.get_panel_registry.return_value = panel_registry
    app = MagicMock()
    app.library_service = library_service

    session = Session(
        project_state=app,
        workspace_manager=MagicMock(),
        session_manager=MagicMock(),
    )
    # SessionContext copies project_state at construction time; pin the
    # app attribute too so the editor's resolution chain hits our stub.
    session.context.app = app
    return session


def _make_properties_editor_wrapper(session: Session) -> EditorWrapper:
    """Build a real ``EditorWrapper`` around ``PropertiesEditor`` and
    instantiate it (without calling ``draw``).

    Returns the wrapper; callers can read ``wrapper.instance`` for the
    editor, set the redraw callback, and trigger the panel-subscription
    path directly by calling
    ``wrapper.instance._subscribe_panel_event_handlers(session.context)``.
    """
    wrapper = EditorWrapper(
        editor_key=PropertiesEditor.class_identity.registry_key,
        editor_cls=PropertiesEditor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True
    return wrapper


# ----------------------------------------------------------------------
# Editor surface
# ----------------------------------------------------------------------


def test_properties_editor_panel_registry_helper_returns_app_registry():
    panel_registry = PanelRegistry()
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
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


# ----------------------------------------------------------------------
# Panel-driven event-bus subscriptions
# ----------------------------------------------------------------------


def test_selection_moved_triggers_wrapper_redraw_via_panel_redraw_on():
    """The original PropertiesEditor bug, fixed structurally.

    Register NodeSettingsPanel (declares ``redraw_on=(SelectionMoved, ...)``)
    in the panel registry, then publish SelectionMoved. The editor's
    panel-union subscription should fire ``wrapper.redraw()``.
    """
    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    # The editor wires panel-bus subs on its first draw(). Since we don't
    # exercise the full layout-build path here, call the wiring step
    # directly — it's exactly what draw() does on first call.
    editor._context = session.context
    editor._subscribe_panel_event_handlers(session.context)

    session.publish(SelectionMoved())

    assert redraws == [wrapper]


def test_unregistered_panel_events_do_not_redraw():
    """If no registered panel cares about an event, publishing it must
    NOT redraw the wrapper."""

    @dataclass(frozen=True)
    class _UnrelatedEvent(ContextSignal):
        pass

    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    editor._context = session.context
    editor._subscribe_panel_event_handlers(session.context)

    session.publish(_UnrelatedEvent())

    assert redraws == []


def test_editor_attaches_to_panel_registry_lifecycle_channel():
    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    editor._context = session.context
    editor._subscribe_panel_event_handlers(session.context)

    assert editor._attached_panel_registry is panel_registry
    assert editor._on_panel_registry_event in panel_registry._batch_event_subscribers


def test_catalog_change_rebuilds_subscriptions_and_triggers_redraw():
    """When a new panel registers, the editor's panel-union expands. The
    catalog change itself also triggers one redraw — current rendered
    state may be stale relative to the new event types."""
    # Build a fresh, empty registry first; NodeSettingsPanel adds later.
    panel_registry = PanelRegistry()
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    editor._context = session.context
    editor._subscribe_panel_event_handlers(session.context)

    # No panels registered yet → no subscriptions, no redraws on
    # SelectionMoved.
    session.publish(SelectionMoved())
    assert redraws == []

    # Register a panel that cares about SelectionMoved and fire the
    # registry's batch lifecycle event so the editor reconciles.
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    panel_registry._notify_batch_event_subscribers()

    # The reconciliation itself triggered a redraw.
    assert len(redraws) >= 1
    redraws.clear()

    # And now SelectionMoved publishes reach the editor.
    session.publish(SelectionMoved())
    assert len(redraws) == 1


def test_cleanup_drops_panel_subs_and_detaches_from_registry():
    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    editor._context = session.context
    editor._subscribe_panel_event_handlers(session.context)
    assert editor._attached_panel_registry is panel_registry
    assert len(editor._panel_bus_unsubscribes) >= 1

    editor.cleanup()

    assert editor._attached_panel_registry is None
    assert editor._panel_bus_unsubscribes == []
    assert editor._on_panel_registry_event not in panel_registry._batch_event_subscribers


def test_hot_reload_of_properties_editor_triggers_cleanup():
    """A CLASS_RELOADED event on PropertiesEditor's wrapper calls
    ``instance.cleanup`` on the old instance, dropping its panel subs
    and detaching from the panel registry."""
    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    editor._context = session.context
    editor._subscribe_panel_event_handlers(session.context)
    assert editor._on_panel_registry_event in panel_registry._batch_event_subscribers

    # Simulate hot-reload: a fresh PropertiesEditor class object.
    class _ReloadedPropertiesEditor(PropertiesEditor):
        pass

    reload_event = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_RELOADED,
        registry_key=PropertiesEditor.class_identity.registry_key,
        affected_class=_ReloadedPropertiesEditor,
        library_identity=_FAKE_LIBRARY_IDENTITY,
    )
    wrapper._on_lifecycle_event(reload_event)

    # Old instance was cleaned up: its panel-bus subs are gone, and its
    # batch subscription is detached from the registry.
    assert editor._panel_bus_unsubscribes == []
    assert editor._attached_panel_registry is None
    assert editor._on_panel_registry_event not in panel_registry._batch_event_subscribers


# ----------------------------------------------------------------------
# Graceful handling when the registry chain is absent / raises
# ----------------------------------------------------------------------


def test_editor_subscribes_to_nothing_when_chain_returns_none():
    """``library_service.get_panel_registry()`` returning None is
    treated as "no panel registry available" — no subscriptions, no
    attach."""
    session = _make_session_with_panel_registry(None)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    editor._context = session.context
    editor._subscribe_panel_event_handlers(session.context)

    assert editor._attached_panel_registry is None
    assert editor._panel_bus_unsubscribes == []


def test_editor_subscribes_to_nothing_when_chain_is_missing():
    """A context whose ``app`` lacks ``library_service`` (test fixture,
    non-studio host) is treated as "no panel registry available"."""
    session = Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=MagicMock(),
    )
    # Pin app to a bare namespace so attribute resolution raises
    # AttributeError instead of producing yet another MagicMock.
    session.context.app = SimpleNamespace()

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    editor._context = session.context
    editor._subscribe_panel_event_handlers(session.context)

    assert editor._attached_panel_registry is None
    assert editor._panel_bus_unsubscribes == []


def test_editor_handles_get_panel_registry_raising():
    """A library_service whose get_panel_registry() raises is treated
    as "no panel registry available" — the editor logs and proceeds
    rather than propagating."""
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

    editor._context = session.context
    # Must not raise.
    editor._subscribe_panel_event_handlers(session.context)

    assert editor._attached_panel_registry is None
    assert editor._panel_bus_unsubscribes == []
