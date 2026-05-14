"""Tests for the panel-contributed event-bus subscription union (Step 5b).

Covers:

- PanelRegistry.get_redraw_events_for unions ``redraw_on=`` across panels
  whose ``action`` is satisfied by the provider; skips panels with empty
  redraw_on, no action, or non-matching action.
- EditorWrapper subscribes to the panel-contributed union when the editor
  returns a registry from get_panel_registry; that subscription fires
  wrapper.redraw() on publish.
- Editors that opt out (return None) subscribe to nothing.
- Panel-contributed subscriptions are independent from the editor's own
  @redraw_on/@react_on decorator subscriptions.
- Catalog changes (PanelRegistry batch lifecycle events) trigger a
  rebuild of the panel-contributed subscription set.
- Wrapper cleanup detaches from the registry and drops panel subs.
- Hot-reload of the editor class drops & re-establishes panel subs.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional, Protocol, runtime_checkable
from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.session.session import Session
from haywire.core.session.signals_and_lifecycle import ContextSignal
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.editor.wrapper import EditorWrapper
from haywire.ui.panel import BasePanel, panel
from haywire.ui.panel.focus import Focus
from haywire.ui.panel.registry import PanelRegistry


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
# Test event types + fixtures
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _PanelEventX(ContextSignal):
    pass


@dataclass(frozen=True)
class _PanelEventY(ContextSignal):
    pass


@dataclass(frozen=True)
class _UnrelatedEvent(ContextSignal):
    pass


@runtime_checkable
class _HostActions(Protocol):
    def do_thing(self) -> None: ...


@runtime_checkable
class _OtherHostActions(Protocol):
    def do_other(self) -> None: ...


class _TestFocus(Focus):
    id = "panel_redraw_union_test_focus"
    label = "T"
    icon = "x"

    @classmethod
    def available(cls, ctx):
        return True


@panel(
    action=_HostActions,
    focus=_TestFocus,
    label="X",
    redraw_on=(_PanelEventX,),
    registry_id="prtest_panel_x",
)
class _PanelX(BasePanel):
    def draw(self, ctx, layout, actions):
        pass


@panel(
    action=_HostActions,
    focus=_TestFocus,
    label="Y",
    redraw_on=(_PanelEventY,),
    registry_id="prtest_panel_y",
)
class _PanelY(BasePanel):
    def draw(self, ctx, layout, actions):
        pass


@panel(
    action=_HostActions,
    focus=_TestFocus,
    label="Empty",
    registry_id="prtest_panel_empty",
)
class _PanelNoRedraw(BasePanel):
    def draw(self, ctx, layout, actions):
        pass


@panel(
    action=_OtherHostActions,
    focus=_TestFocus,
    label="Other",
    redraw_on=(_UnrelatedEvent,),
    registry_id="prtest_panel_other_actions",
)
class _PanelOtherActions(BasePanel):
    def draw(self, ctx, layout, actions):
        pass


def _make_session() -> Session:
    return Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=MagicMock(),
    )


def _identity(key: str = "test:editor") -> SimpleNamespace:
    return SimpleNamespace(
        registry_key=key,
        label=key,
        default_slot="main",
        opens=None,
    )


# ----------------------------------------------------------------------
# PanelRegistry.get_redraw_events_for
# ----------------------------------------------------------------------


def _fresh_registry_with_panels(*panel_classes: type) -> PanelRegistry:
    reg = PanelRegistry()
    for cls in panel_classes:
        reg._register_class(cls, library_identity=_FAKE_LIBRARY_IDENTITY)
    return reg


class _HostingThing:
    def do_thing(self) -> None:
        pass


class _NonHostingThing:
    def something_else(self) -> None:
        pass


def test_get_redraw_events_for_unions_matching_panel_redraw_on():
    reg = _fresh_registry_with_panels(_PanelX, _PanelY, _PanelNoRedraw)
    events = reg.get_redraw_events_for(_HostingThing())
    assert events == {_PanelEventX, _PanelEventY}


def test_get_redraw_events_for_skips_panels_with_unsatisfied_action():
    reg = _fresh_registry_with_panels(_PanelX, _PanelOtherActions)
    events = reg.get_redraw_events_for(_HostingThing())
    # _PanelOtherActions's redraw_on is excluded — host doesn't satisfy
    # _OtherHostActions.
    assert events == {_PanelEventX}


def test_get_redraw_events_for_returns_empty_when_no_panels_apply():
    reg = _fresh_registry_with_panels(_PanelX, _PanelY)
    events = reg.get_redraw_events_for(_NonHostingThing())
    assert events == set()


def test_get_redraw_events_for_skips_empty_redraw_on_tuple():
    reg = _fresh_registry_with_panels(_PanelNoRedraw)
    events = reg.get_redraw_events_for(_HostingThing())
    assert events == set()


# ----------------------------------------------------------------------
# EditorWrapper panel-contributed subscriptions
# ----------------------------------------------------------------------


class _StubEditorBase(BaseEditor):
    class_identity = _identity()

    def draw(self, context, container):
        pass


class _PanelHostingEditor(_StubEditorBase):
    """Editor that satisfies _HostActions and exposes a panel registry."""

    class_identity = _identity("test:editor:panel_host")

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self._test_registry: Optional[PanelRegistry] = None

    def do_thing(self) -> None:  # satisfies _HostActions structurally
        pass

    def get_panel_registry(self, context):
        return self._test_registry


def _make_panel_hosting_wrapper(
    session: Session,
    panels: tuple[type, ...] = (_PanelX, _PanelY),
) -> tuple[EditorWrapper, PanelRegistry]:
    registry = _fresh_registry_with_panels(*panels)
    wrapper = EditorWrapper(
        editor_key="test:editor:panel_host",
        editor_cls=_PanelHostingEditor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    # Bind the registry the editor will return from get_panel_registry.
    # We attach via a mutable class attribute so the editor instance built
    # during _instantiate picks it up via the closed-over registry below.
    _PanelHostingEditor._pending_registry = registry  # type: ignore[attr-defined]
    return wrapper, registry


def test_wrapper_subscribes_to_panel_redraw_events_when_registry_available():
    session = _make_session()
    registry = _fresh_registry_with_panels(_PanelX, _PanelY)

    class _Editor(_PanelHostingEditor):
        class_identity = _identity("test:editor:auto_pulls_registry")

        def get_panel_registry(self, context):
            return registry

    wrapper = EditorWrapper(
        editor_key="test:editor:auto_pulls_registry",
        editor_cls=_Editor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True
    assert len(wrapper._panel_bus_unsubscribes) == 2

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    session.publish(_PanelEventX())
    session.publish(_PanelEventY())
    assert len(redraws) == 2

    # An unrelated event reaches nobody.
    redraws.clear()
    session.publish(_UnrelatedEvent())
    assert redraws == []


def test_wrapper_opts_out_when_editor_returns_no_registry():
    """Default BaseEditor.get_panel_registry returns None; the wrapper
    must subscribe to nothing on the panel-bus channel."""
    session = _make_session()

    class _NoRegistryEditor(_StubEditorBase):
        class_identity = _identity("test:editor:no_registry")

    wrapper = EditorWrapper(
        editor_key="test:editor:no_registry",
        editor_cls=_NoRegistryEditor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True
    assert wrapper._panel_bus_unsubscribes == []
    assert wrapper._panel_registry is None


def test_wrapper_panel_subscription_independent_from_decorator_subs():
    """An editor with both @redraw_on methods AND panel-contributed
    subscriptions tracks them in separate lists; both fire."""
    from haywire.core.session.handlers import redraw_on

    session = _make_session()
    registry = _fresh_registry_with_panels(_PanelX)

    class _ComboEditor(_PanelHostingEditor):
        class_identity = _identity("test:editor:combo")

        def __init__(self, wrapper):
            super().__init__(wrapper)
            self.method_calls = 0

        @redraw_on(_UnrelatedEvent)
        def on_event(self, ctx, event):
            self.method_calls += 1

        def get_panel_registry(self, context):
            return registry

    wrapper = EditorWrapper(
        editor_key="test:editor:combo",
        editor_cls=_ComboEditor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True
    assert len(wrapper._bus_unsubscribes) == 1  # @redraw_on(_UnrelatedEvent)
    assert len(wrapper._panel_bus_unsubscribes) == 1  # panel _PanelEventX

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    session.publish(_PanelEventX())
    session.publish(_UnrelatedEvent())

    assert wrapper.instance.method_calls == 1  # type: ignore[attr-defined]
    # 1 redraw from the panel-bus closure + 1 from the @redraw_on closure
    assert len(redraws) == 2


def test_wrapper_attaches_to_panel_registry_lifecycle_channel():
    session = _make_session()
    registry = _fresh_registry_with_panels(_PanelX)

    class _Editor(_PanelHostingEditor):
        class_identity = _identity("test:editor:lifecycle")

        def get_panel_registry(self, context):
            return registry

    wrapper = EditorWrapper(
        editor_key="test:editor:lifecycle",
        editor_cls=_Editor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True
    assert wrapper._panel_registry is registry
    # The wrapper's _on_panel_registry_event should be a batch subscriber now.
    assert wrapper._on_panel_registry_event in registry._batch_event_subscribers


def test_wrapper_rebuilds_panel_subscriptions_on_catalog_change():
    """When a new panel registers, the wrapper's panel-union expands to
    include its redraw_on=, and publishes on the new event now reach
    wrapper.redraw()."""
    session = _make_session()
    registry = _fresh_registry_with_panels(_PanelX)

    class _Editor(_PanelHostingEditor):
        class_identity = _identity("test:editor:catalog_change")

        def get_panel_registry(self, context):
            return registry

    wrapper = EditorWrapper(
        editor_key="test:editor:catalog_change",
        editor_cls=_Editor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    # Pre-condition: _PanelEventY currently has no subscribers; its publish
    # is a no-op for this wrapper.
    session.publish(_PanelEventY())
    assert redraws == []

    # Register _PanelY mid-flight and fire the batch lifecycle event so
    # the wrapper recomputes its union.
    registry._register_class(_PanelY, library_identity=_FAKE_LIBRARY_IDENTITY)
    registry._notify_batch_event_subscribers()

    # The reconciliation itself triggered one redraw (catalog change ⇒
    # current view may be stale).
    assert len(redraws) >= 1
    redraws.clear()

    # And now _PanelEventY publishes reach the wrapper.
    session.publish(_PanelEventY())
    assert len(redraws) == 1


def test_wrapper_cleanup_detaches_from_panel_registry_and_drops_panel_subs():
    session = _make_session()
    registry = _fresh_registry_with_panels(_PanelX)

    class _Editor(_PanelHostingEditor):
        class_identity = _identity("test:editor:cleanup")

        def get_panel_registry(self, context):
            return registry

    wrapper = EditorWrapper(
        editor_key="test:editor:cleanup",
        editor_cls=_Editor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True
    assert wrapper._panel_registry is registry
    assert len(wrapper._panel_bus_unsubscribes) == 1

    wrapper.cleanup()

    assert wrapper._panel_registry is None
    assert wrapper._panel_bus_unsubscribes == []
    assert wrapper._on_panel_registry_event not in registry._batch_event_subscribers


def test_wrapper_hot_reload_drops_panel_subs_and_resubscribes_against_new_class():
    session = _make_session()
    registry = _fresh_registry_with_panels(_PanelX)

    class _Editor(_PanelHostingEditor):
        class_identity = _identity("test:editor:hot_reload_panel")

        def get_panel_registry(self, context):
            return registry

    wrapper = EditorWrapper(
        editor_key="test:editor:hot_reload_panel",
        editor_cls=_Editor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True
    assert len(wrapper._panel_bus_unsubscribes) == 1
    assert wrapper._on_panel_registry_event in registry._batch_event_subscribers

    class _ReloadedEditor(_PanelHostingEditor):
        class_identity = _identity("test:editor:hot_reload_panel")

        def get_panel_registry(self, context):
            return registry

    reload_event = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_RELOADED,
        registry_key="test:editor:hot_reload_panel",
        affected_class=_ReloadedEditor,
        library_identity=_FAKE_LIBRARY_IDENTITY,
    )
    wrapper._on_lifecycle_event(reload_event)

    # Subs dropped + detached.
    assert wrapper._panel_bus_unsubscribes == []
    assert wrapper._panel_registry is None
    assert wrapper._on_panel_registry_event not in registry._batch_event_subscribers

    # Re-instantiate brings them back, against the reloaded class.
    assert wrapper._instantiate() is True
    assert len(wrapper._panel_bus_unsubscribes) == 1
    assert wrapper._on_panel_registry_event in registry._batch_event_subscribers


def test_wrapper_handles_get_panel_registry_raising():
    session = _make_session()

    class _Editor(_PanelHostingEditor):
        class_identity = _identity("test:editor:bad_get_registry")

        def get_panel_registry(self, context):
            raise RuntimeError("intentional bad registry resolution")

    wrapper = EditorWrapper(
        editor_key="test:editor:bad_get_registry",
        editor_cls=_Editor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    # Must not raise; wrapper simply ends up without panel subs.
    assert wrapper._instantiate() is True
    assert wrapper._panel_bus_unsubscribes == []
    assert wrapper._panel_registry is None
