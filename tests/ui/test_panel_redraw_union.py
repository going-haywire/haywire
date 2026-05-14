"""Tests for the panel-contributed event-bus subscription union.

Covers:

- PanelRegistry.get_redraw_events_for unions ``redraw_on=`` across panels
  whose ``action`` is satisfied by the provider; skips panels with empty
  redraw_on, no action, or non-matching action.
- EditorWrapper subscribes to the panel-contributed union when the
  session's context exposes a panel registry via
  ``context.app.library_service.get_panel_registry()``; that subscription
  fires wrapper.redraw() on publish.
- Sessions whose context exposes no registry chain subscribe to nothing.
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


def _attach_panel_registry(session: Session, registry: Optional[PanelRegistry]) -> None:
    """Wire ``context.app.library_service.get_panel_registry()`` to return ``registry``.

    The wrapper resolves the registry through this chain; tests use this
    helper to mount a per-test PanelRegistry on a fresh Session's context.
    """
    library_service = SimpleNamespace(get_panel_registry=lambda: registry)
    session.context.app = SimpleNamespace(library_service=library_service)


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
    session = Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=MagicMock(),
    )
    # Default: no panel registry chain. Tests that need one call
    # ``_attach_panel_registry(session, registry)`` to wire it on.
    session.context.app = SimpleNamespace()
    return session


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
    """Editor that satisfies _HostActions.

    The panel registry the framework subscribes to is resolved from the
    session's context (see ``_attach_panel_registry``) — not from the
    editor.
    """

    class_identity = _identity("test:editor:panel_host")

    def do_thing(self) -> None:  # satisfies _HostActions structurally
        pass


def test_wrapper_subscribes_to_panel_redraw_events_when_registry_available():
    session = _make_session()
    registry = _fresh_registry_with_panels(_PanelX, _PanelY)
    _attach_panel_registry(session, registry)

    wrapper = EditorWrapper(
        editor_key="test:editor:auto_pulls_registry",
        editor_cls=_PanelHostingEditor,
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


def test_wrapper_opts_out_when_session_exposes_no_registry():
    """A session whose context does not expose a library_service /
    get_panel_registry chain has the wrapper subscribe to nothing on
    the panel-bus channel."""
    session = _make_session()
    # Replace the auto-mock with a concrete object that lacks
    # ``library_service`` so attribute resolution raises AttributeError.
    session.context.app = SimpleNamespace()

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


def test_wrapper_opts_out_when_registry_chain_returns_none():
    """A library_service that returns ``None`` from get_panel_registry()
    is treated the same as a missing chain — no panel subs."""
    session = _make_session()
    _attach_panel_registry(session, None)

    wrapper = EditorWrapper(
        editor_key="test:editor:none_registry",
        editor_cls=_PanelHostingEditor,
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
    _attach_panel_registry(session, registry)

    class _ComboEditor(_PanelHostingEditor):
        class_identity = _identity("test:editor:combo")

        def __init__(self, wrapper):
            super().__init__(wrapper)
            self.method_calls = 0

        @redraw_on(_UnrelatedEvent)
        def on_event(self, ctx, event):
            self.method_calls += 1

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
    _attach_panel_registry(session, registry)

    wrapper = EditorWrapper(
        editor_key="test:editor:lifecycle",
        editor_cls=_PanelHostingEditor,
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
    _attach_panel_registry(session, registry)

    wrapper = EditorWrapper(
        editor_key="test:editor:catalog_change",
        editor_cls=_PanelHostingEditor,
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
    _attach_panel_registry(session, registry)

    wrapper = EditorWrapper(
        editor_key="test:editor:cleanup",
        editor_cls=_PanelHostingEditor,
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
    _attach_panel_registry(session, registry)

    wrapper = EditorWrapper(
        editor_key="test:editor:hot_reload_panel",
        editor_cls=_PanelHostingEditor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True
    assert len(wrapper._panel_bus_unsubscribes) == 1
    assert wrapper._on_panel_registry_event in registry._batch_event_subscribers

    class _ReloadedEditor(_PanelHostingEditor):
        class_identity = _identity("test:editor:hot_reload_panel")

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


def test_wrapper_handles_registry_resolution_raising():
    """A library_service whose ``get_panel_registry`` raises is treated
    the same as a missing chain: the wrapper logs and ends up with no
    panel subs rather than propagating the exception."""
    session = _make_session()
    library_service = SimpleNamespace(
        get_panel_registry=MagicMock(side_effect=RuntimeError("intentional bad lookup"))
    )
    session.context.app = SimpleNamespace(library_service=library_service)

    wrapper = EditorWrapper(
        editor_key="test:editor:bad_get_registry",
        editor_cls=_PanelHostingEditor,
        registry=EditorTypeRegistry(),
        session=session,
    )
    # Must not raise; wrapper simply ends up without panel subs.
    assert wrapper._instantiate() is True
    assert wrapper._panel_bus_unsubscribes == []
    assert wrapper._panel_registry is None
