"""Tests for editor-side @redraw_on / @react_on dispatch wiring (Step 5a).

Covers:

- discover_handlers walks the MRO, indexes by event type, tags kind
- subclass override without re-decoration drops the inherited subscription
- caching: same call returns identical dict; fresh class object rebuilds
- EditorWrapper._subscribe_event_handlers attaches one bus subscription
  per (event_type, method) binding after _instantiate
- @redraw_on handler invoking ``self.redraw()`` reaches the redraw callback
- @react_on handler does NOT trigger redraw
- multiple handlers on the same editor, same event, both fire
- handler exception is captured into state.error_runtime and the redraw
  is suppressed (no broken render after a failed handler)
- bus subscriptions are dropped on wrapper.cleanup()
- bus subscriptions are dropped on hot-reload, and re-subscription happens
  on the next _instantiate against the new class
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.session.handlers import (
    HandlerBinding,
    discover_handlers,
    react_on,
    redraw_on,
)
from haywire.core.session.session import Session
from haywire.core.session.events import ContextSignal
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.editor.wrapper import EditorWrapper


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
# Test event types
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _EventA(ContextSignal):
    pass


@dataclass(frozen=True)
class _EventB(ContextSignal):
    pass


@dataclass(frozen=True)
class _EventC(ContextSignal):
    pass


# ----------------------------------------------------------------------
# Fixtures: real Session + editor wrapper helpers
# ----------------------------------------------------------------------


def _make_session() -> Session:
    session = Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=MagicMock(),
    )
    # Decouple the wrapper's panel-registry resolution chain from the
    # auto-mock — these tests don't host panels; we want the wrapper to
    # cleanly skip the panel-bus subscription path rather than chase a
    # MagicMock.
    session.context.app = SimpleNamespace()
    return session


def _make_wrapper(editor_cls: type, session: Session) -> EditorWrapper:
    return EditorWrapper(
        editor_key=getattr(editor_cls.class_identity, "registry_key", "test:editor"),
        editor_cls=editor_cls,
        registry=EditorTypeRegistry(),
        session=session,
    )


def _identity(key: str = "test:editor") -> SimpleNamespace:
    return SimpleNamespace(
        registry_key=key,
        label=key,
        default_slot="main",
        opens=None,
    )


# ----------------------------------------------------------------------
# discover_handlers
# ----------------------------------------------------------------------


class _OneRedrawHandler:
    class_identity = _identity()

    @redraw_on(_EventA)
    def handle_a(self, ctx, event):
        pass


def test_discover_handlers_finds_redraw_on():
    index = discover_handlers(_OneRedrawHandler)
    assert list(index.keys()) == [_EventA]
    assert index[_EventA] == [HandlerBinding("handle_a", "redraw_on")]


class _MixedHandlers:
    class_identity = _identity()

    @redraw_on(_EventA, _EventB)
    def handle_state(self, ctx, event):
        pass

    @react_on(_EventC)
    def handle_side(self, ctx, event):
        pass


def test_discover_handlers_indexes_multiple_event_types_per_decorator():
    index = discover_handlers(_MixedHandlers)
    assert set(index.keys()) == {_EventA, _EventB, _EventC}
    assert index[_EventA] == [HandlerBinding("handle_state", "redraw_on")]
    assert index[_EventB] == [HandlerBinding("handle_state", "redraw_on")]
    assert index[_EventC] == [HandlerBinding("handle_side", "react_on")]


class _StackedHandler:
    class_identity = _identity()

    @redraw_on(_EventA)
    @react_on(_EventB)
    def handle(self, ctx, event):
        pass


def test_discover_handlers_handles_stacked_decorators_on_one_method():
    index = discover_handlers(_StackedHandler)
    assert set(index.keys()) == {_EventA, _EventB}
    assert index[_EventA] == [HandlerBinding("handle", "redraw_on")]
    assert index[_EventB] == [HandlerBinding("handle", "react_on")]


class _BaseHandler:
    class_identity = _identity()

    @redraw_on(_EventA)
    def from_base(self, ctx, event):
        pass

    @react_on(_EventB)
    def reaction(self, ctx, event):
        pass


class _ChildExtends(_BaseHandler):
    class_identity = _identity()

    @redraw_on(_EventC)
    def from_child(self, ctx, event):
        pass


def test_discover_handlers_walks_mro_to_pick_up_inherited_decorations():
    index = discover_handlers(_ChildExtends)
    assert set(index.keys()) == {_EventA, _EventB, _EventC}
    # Order in the index reflects MRO walk (subclass-first). The base
    # methods land in their own bindings; not duplicated.
    assert HandlerBinding("from_base", "redraw_on") in index[_EventA]
    assert HandlerBinding("reaction", "react_on") in index[_EventB]
    assert HandlerBinding("from_child", "redraw_on") in index[_EventC]


class _ChildOverridesWithoutDecorator(_BaseHandler):
    class_identity = _identity()

    def from_base(self, ctx, event):  # type: ignore[override]
        # No decorator — subscription should silently disappear.
        pass


def test_discover_handlers_drops_inherited_subscription_when_subclass_overrides_without_redecorating():
    index = discover_handlers(_ChildOverridesWithoutDecorator)
    # _EventA had its only handler stripped; _EventB still fires from the base.
    assert _EventA not in index
    assert _EventB in index
    assert index[_EventB] == [HandlerBinding("reaction", "react_on")]


def test_discover_handlers_caches_result_on_class():
    first = discover_handlers(_OneRedrawHandler)
    second = discover_handlers(_OneRedrawHandler)
    assert first is second


def test_discover_handlers_fresh_class_rebuilds_cache():
    """A hot-reload produces a brand-new class object — the cache is
    attached to the old class only, so the new class computes its own."""

    class _Fresh:
        class_identity = _identity()

        @redraw_on(_EventA)
        def handle(self, ctx, event):
            pass

    first = discover_handlers(_Fresh)

    class _FreshReload:
        class_identity = _identity()

        @redraw_on(_EventA)
        def handle(self, ctx, event):
            pass

    second = discover_handlers(_FreshReload)
    assert first is not second
    # But the *content* still describes the same shape.
    assert list(first.keys()) == list(second.keys()) == [_EventA]


def test_discover_handlers_returns_empty_for_undecorated_class():
    class _Plain:
        class_identity = _identity()

        def draw(self, ctx, container):
            pass

    assert discover_handlers(_Plain) == {}


# ----------------------------------------------------------------------
# EditorWrapper auto-subscribe behaviour
# ----------------------------------------------------------------------


class _StubEditorBase(BaseEditor):
    """Minimal concrete BaseEditor subclass usable as a parent in tests."""

    class_identity = _identity()

    def draw(self, context, container):
        pass


class _RedrawEditor(_StubEditorBase):
    class_identity = _identity("test:editor:redraw")

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self.calls: list[tuple[str, ContextSignal]] = []

    @redraw_on(_EventA)
    def on_a(self, ctx, event):
        self.calls.append(("on_a", event))


def test_wrapper_subscribes_decorated_methods_after_instantiate():
    session = _make_session()
    wrapper = _make_wrapper(_RedrawEditor, session)
    assert wrapper._bus_unsubscribes == []

    assert wrapper._instantiate() is True
    assert len(wrapper._bus_unsubscribes) == 1


def test_wrapper_redraw_on_handler_triggers_wrapper_redraw():
    session = _make_session()
    wrapper = _make_wrapper(_RedrawEditor, session)
    assert wrapper._instantiate() is True

    redraw_calls: list[EditorWrapper] = []
    wrapper.set_redraw_callback(lambda w: redraw_calls.append(w))

    event = _EventA()
    session.publish(event)

    assert wrapper.instance is not None
    assert wrapper.instance.calls == [("on_a", event)]  # type: ignore[attr-defined]
    assert redraw_calls == [wrapper]


class _ReactEditor(_StubEditorBase):
    class_identity = _identity("test:editor:react")

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self.calls: list[ContextSignal] = []

    @react_on(_EventB)
    def on_b(self, ctx, event):
        self.calls.append(event)


def test_wrapper_react_on_handler_does_not_trigger_redraw():
    session = _make_session()
    wrapper = _make_wrapper(_ReactEditor, session)
    assert wrapper._instantiate() is True

    redraw_calls: list[EditorWrapper] = []
    wrapper.set_redraw_callback(lambda w: redraw_calls.append(w))

    session.publish(_EventB())

    assert wrapper.instance is not None
    assert len(wrapper.instance.calls) == 1  # type: ignore[attr-defined]
    assert redraw_calls == []  # react_on is side-effect only


class _MultiHandlerEditor(_StubEditorBase):
    class_identity = _identity("test:editor:multi")

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self.log: list[str] = []

    @redraw_on(_EventA)
    def first(self, ctx, event):
        self.log.append("first")

    @redraw_on(_EventA)
    def second(self, ctx, event):
        self.log.append("second")


def test_wrapper_multiple_redraw_handlers_for_one_event_all_fire():
    """Both handlers fire; per the design decision in Step 5a we accept
    that this triggers wrapper.redraw() once per handler. The user
    explicitly dropped the once-per-pass coalescing requirement."""
    session = _make_session()
    wrapper = _make_wrapper(_MultiHandlerEditor, session)
    assert wrapper._instantiate() is True

    redraw_calls: list[EditorWrapper] = []
    wrapper.set_redraw_callback(lambda w: redraw_calls.append(w))

    session.publish(_EventA())

    assert wrapper.instance is not None
    assert wrapper.instance.log == ["first", "second"]  # type: ignore[attr-defined]
    assert len(redraw_calls) == 2  # one redraw per @redraw_on handler


class _RaisingEditor(_StubEditorBase):
    class_identity = _identity("test:editor:raise")

    @redraw_on(_EventA)
    def on_a(self, ctx, event):
        raise RuntimeError("intentional handler boom")


def test_wrapper_handler_exception_captures_error_runtime_and_suppresses_redraw():
    session = _make_session()
    wrapper = _make_wrapper(_RaisingEditor, session)
    assert wrapper._instantiate() is True
    assert wrapper.state.error_runtime is None

    redraw_calls: list[EditorWrapper] = []
    wrapper.set_redraw_callback(lambda w: redraw_calls.append(w))

    # Bus is error-isolated so this must not raise.
    session.publish(_EventA())

    assert wrapper.state.error_runtime is not None
    assert redraw_calls == []  # do not redraw on failure


class _IndependentEditor(_StubEditorBase):
    class_identity = _identity("test:editor:independent")

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self.calls = 0

    @redraw_on(_EventA)
    def on_a(self, ctx, event):
        self.calls += 1


def test_wrapper_cleanup_drops_bus_subscriptions():
    session = _make_session()
    wrapper = _make_wrapper(_IndependentEditor, session)
    assert wrapper._instantiate() is True
    assert len(wrapper._bus_unsubscribes) == 1

    wrapper.cleanup()
    assert wrapper._bus_unsubscribes == []

    # Publishes after cleanup do not reach the (now-stale) instance.
    # The instance still exists in the test's reference, but the wrapper
    # has cleared its own _instance pointer; bus has no subscribers left.
    session.publish(_EventA())
    # No exception, no reattach, no further calls.


def test_wrapper_hot_reload_re_subscribes_against_new_class():
    """After a successful CLASS_RELOADED event, the wrapper drops the old
    subscription and the next _instantiate() rebinds the new class.
    """
    session = _make_session()
    wrapper = _make_wrapper(_IndependentEditor, session)
    assert wrapper._instantiate() is True
    original_unsubs = list(wrapper._bus_unsubscribes)
    assert len(original_unsubs) == 1

    # Simulate hot-reload: build a fresh class object equivalent to the
    # original, fire CLASS_RELOADED through the wrapper's lifecycle handler.
    class _ReloadedEditor(_StubEditorBase):
        class_identity = _identity("test:editor:independent")

        def __init__(self, wrapper):
            super().__init__(wrapper)
            self.calls = 0

        @redraw_on(_EventA)
        def on_a(self, ctx, event):
            self.calls += 1

    reload_event = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_RELOADED,
        registry_key="test:editor:independent",
        affected_class=_ReloadedEditor,
        library_identity=_FAKE_LIBRARY_IDENTITY,
    )
    wrapper._on_lifecycle_event(reload_event)

    # Old subscriptions dropped immediately on the reload path.
    assert wrapper._bus_unsubscribes == []
    assert wrapper.instance is None
    assert wrapper.editor_cls is _ReloadedEditor

    # The next instantiate produces a fresh instance + new subscription.
    assert wrapper._instantiate() is True
    assert len(wrapper._bus_unsubscribes) == 1
    assert isinstance(wrapper.instance, _ReloadedEditor)

    # And the new instance is the one that receives events — the old
    # subscription is gone so only one call lands.
    session.publish(_EventA())
    assert wrapper.instance.calls == 1  # type: ignore[attr-defined]


class _OneOf(_StubEditorBase):
    class_identity = _identity("test:editor:isolation:a")

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self.calls = 0

    @redraw_on(_EventA)
    def on_a(self, ctx, event):
        self.calls += 1


class _OtherOf(_StubEditorBase):
    class_identity = _identity("test:editor:isolation:b")

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self.calls = 0

    @redraw_on(_EventA)
    def on_a(self, ctx, event):
        self.calls += 1


def test_two_wrappers_in_one_session_each_receive_events_independently():
    session = _make_session()
    w1 = _make_wrapper(_OneOf, session)
    w2 = _make_wrapper(_OtherOf, session)
    assert w1._instantiate() is True
    assert w2._instantiate() is True

    session.publish(_EventA())
    assert w1.instance.calls == 1  # type: ignore[attr-defined]
    assert w2.instance.calls == 1  # type: ignore[attr-defined]

    # Cleaning up one doesn't affect the other.
    w1.cleanup()
    session.publish(_EventA())
    assert w1.instance is None
    assert w2.instance.calls == 2  # type: ignore[attr-defined]


class _UndecoratedEditor(_StubEditorBase):
    class_identity = _identity("test:editor:plain")


def test_wrapper_with_no_decorated_methods_creates_no_subscriptions():
    session = _make_session()
    wrapper = _make_wrapper(_UndecoratedEditor, session)
    assert wrapper._instantiate() is True
    assert wrapper._bus_unsubscribes == []
