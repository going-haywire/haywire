"""Tests for EditorWrapper and EditorWrapperState."""

from types import SimpleNamespace

from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui.editor.wrapper import EditorWrapperState


def test_state_default_is_valid():
    state = EditorWrapperState()
    assert state.is_valid() is True
    assert state.get_errors() is None


def test_state_with_error_import_is_invalid():
    state = EditorWrapperState()
    state.error_import = HaywireException.create("import failed")
    state.is_imported = False
    assert state.is_valid() is False
    errs = state.get_errors()
    assert errs is not None and len(errs) == 1


def test_state_with_error_instantiate_is_invalid():
    state = EditorWrapperState()
    state.error_instantiate = HaywireException.create("instantiate failed")
    assert state.is_valid() is False


def test_state_get_errors_collects_all():
    state = EditorWrapperState()
    state.error_import = HaywireException.create("imp")
    state.error_instantiate = HaywireException.create("inst")
    state.error_runtime = HaywireException.create("rt")
    errs = state.get_errors()
    assert errs is not None and len(errs) == 3


def test_state_clear_errors_resets_runtime_and_instantiate():
    state = EditorWrapperState()
    state.error_import = HaywireException.create("imp")
    state.error_instantiate = HaywireException.create("inst")
    state.error_runtime = HaywireException.create("rt")
    state._clear_errors()
    # error_import is preserved (only cleared on hot-reload, mirroring NodeWrapperState)
    assert state.error_import is not None
    assert state.error_instantiate is None
    assert state.error_runtime is None


# ---------------------------------------------------------------------------
# Task 3: EditorWrapper construction, identity, cleanup
# ---------------------------------------------------------------------------

from haywire.ui.editor.wrapper import EditorWrapper  # noqa: E402
from haywire.ui.editor.registry import EditorTypeRegistry  # noqa: E402


class _FakeEditorCls:
    class_identity = SimpleNamespace(
        registry_key="fake:editor:1",
        label="Fake",
        default_slot="main",
        opens=None,
    )


def _make_session():
    return SimpleNamespace(context=SimpleNamespace())


def test_wrapper_construction_with_class_sets_imported():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=session,
    )
    assert w.editor_key == "fake:editor:1"
    assert w.editor_cls is _FakeEditorCls
    assert w._binding_id is None
    assert w.state.is_imported is True
    assert w.state.error_import is None
    assert w.state.is_valid() is True


def test_wrapper_construction_with_none_class_sets_error_import():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="missing:editor:1",
        editor_cls=None,
        registry=reg,
        session=session,
    )
    assert w.editor_cls is None
    assert w.state.is_imported is False
    assert w.state.error_import is not None
    assert w.state.is_valid() is False


def test_wrapper_subscribes_to_registry_on_construction():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=session,
    )
    # Internal: the wrapper's _on_lifecycle_event should be in the per-key list
    assert "fake:editor:1" in reg._lifecycle_event_subscribers
    assert w._on_lifecycle_event in reg._lifecycle_event_subscribers["fake:editor:1"]


def test_wrapper_cleanup_unsubscribes_from_registry():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=session,
    )
    w.cleanup()
    assert "fake:editor:1" not in reg._lifecycle_event_subscribers


def test_wrapper_binding_id_without_payload():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    assert w.editor_binding_id == "fake:editor:1"


def test_wrapper_binding_id_with_payload():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        binding_id="/tmp/x",
    )
    assert w.editor_binding_id == "fake:editor:1::/tmp/x"


def test_wrapper_split_id_static():
    assert EditorWrapper.split_id("fake:editor:1") == ("fake:editor:1", None)
    assert EditorWrapper.split_id("fake:editor:1::/tmp/x") == ("fake:editor:1", "/tmp/x")


# ---------------------------------------------------------------------------
# Task 4: _instantiate — lazy construction with error capture
# ---------------------------------------------------------------------------


class _RaisingEditorCls:
    class_identity = SimpleNamespace(
        registry_key="raising:editor:1",
        label="Raising",
        default_slot="main",
        opens=None,
    )

    def __init__(self):
        raise RuntimeError("constructor explodes")


def test_instantiate_creates_instance_and_assigns_wrapper():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    ok = w._instantiate()
    assert ok is True
    assert w.instance is not None
    assert w.instance.wrapper is w
    assert w.state.error_instantiate is None


def test_instantiate_captures_exception_into_error_instantiate():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="raising:editor:1",
        editor_cls=_RaisingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    ok = w._instantiate()
    assert ok is False
    assert w.instance is None
    assert w.state.error_instantiate is not None
    assert w.state.is_valid() is False


def test_instantiate_returns_false_when_editor_cls_is_none():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="missing:editor:1",
        editor_cls=None,
        registry=reg,
        session=_make_session(),
    )
    ok = w._instantiate()
    assert ok is False
    assert w.instance is None


# ---------------------------------------------------------------------------
# Task 5: _on_lifecycle_event — hot-reload state transitions
# ---------------------------------------------------------------------------

from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType  # noqa: E402
from haywire.core.library.identity import LibraryIdentity  # noqa: E402


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


class _NewFakeEditorCls:
    class_identity = SimpleNamespace(
        registry_key="fake:editor:1",
        label="NewFake",
        default_slot="main",
        opens=None,
    )


def test_lifecycle_class_reloaded_updates_class_clears_instance_fires_redraw():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    redraw_calls: list[EditorWrapper] = []
    w.set_redraw_callback(lambda wr: redraw_calls.append(wr))
    # Force lazy instantiate so we have an instance to clear
    w._instantiate()
    assert w.instance is not None

    event = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_RELOADED,
        registry_key="fake:editor:1",
        affected_class=_NewFakeEditorCls,
        library_identity=_FAKE_LIBRARY_IDENTITY,
    )
    w._on_lifecycle_event(event)

    assert w.editor_cls is _NewFakeEditorCls
    assert w.instance is None  # cleared so next draw re-instantiates with new class
    assert w.state.error_import is None
    assert w.state.is_imported is True
    assert redraw_calls == [w]


def test_lifecycle_class_removed_keeps_instance_sets_error_import():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    redraw_calls: list[EditorWrapper] = []
    w.set_redraw_callback(lambda wr: redraw_calls.append(wr))
    w._instantiate()
    instance_before = w.instance
    assert instance_before is not None

    event = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_REMOVED,
        registry_key="fake:editor:1",
        affected_class=None,
        library_identity=_FAKE_LIBRARY_IDENTITY,
    )
    w._on_lifecycle_event(event)

    # NodeWrapper-style: instance and class kept alive
    assert w.instance is instance_before
    assert w.editor_cls is _FakeEditorCls
    # but error_import is set
    assert w.state.error_import is not None
    assert w.state.is_imported is False
    assert redraw_calls == [w]


def test_lifecycle_recovery_after_removal_clears_error_and_updates_class():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    # Force into removed state
    w._on_lifecycle_event(
        LifeCycleEvent(
            event_type=LifeCycleEventType.CLASS_REMOVED,
            registry_key="fake:editor:1",
            affected_class=None,
            library_identity=_FAKE_LIBRARY_IDENTITY,
        )
    )
    assert w.state.error_import is not None

    redraw_calls: list[EditorWrapper] = []
    w.set_redraw_callback(lambda wr: redraw_calls.append(wr))

    # Now CLASS_ADDED brings it back
    w._on_lifecycle_event(
        LifeCycleEvent(
            event_type=LifeCycleEventType.CLASS_ADDED,
            registry_key="fake:editor:1",
            affected_class=_NewFakeEditorCls,
            library_identity=_FAKE_LIBRARY_IDENTITY,
        )
    )
    assert w.editor_cls is _NewFakeEditorCls
    assert w.state.error_import is None
    assert w.state.is_imported is True
    assert redraw_calls == [w]


def test_lifecycle_redraw_callback_safe_when_unset():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    # No redraw_callback set; must not raise
    w._on_lifecycle_event(
        LifeCycleEvent(
            event_type=LifeCycleEventType.CLASS_RELOADED,
            registry_key="fake:editor:1",
            affected_class=_NewFakeEditorCls,
            library_identity=_FAKE_LIBRARY_IDENTITY,
        )
    )
    assert w.editor_cls is _NewFakeEditorCls


# ---------------------------------------------------------------------------
# Task 6: Runtime entry points — draw / on_focus / on_signal / redraw_on_signal
# ---------------------------------------------------------------------------


class _RecordingEditorCls:
    """Editor stub that records calls to draw/on_focus/on_signal/redraw_on_signal."""

    class_identity = SimpleNamespace(
        registry_key="rec:editor:1",
        label="Rec",
        default_slot="main",
        opens=None,
    )

    def __init__(self):
        self.draw_calls: list = []
        self.focus_calls: list = []
        self.on_signal_calls: list = []
        self.redraw_on_signal_calls: list = []
        self.cleanup_calls = 0
        self.wrapper = None
        self.redraw_on_signal_returns = False

    def draw(self, context, container):
        self.draw_calls.append((context, container))

    def on_focus(self, context):
        self.focus_calls.append(context)

    def on_signal(self, context, event):
        self.on_signal_calls.append((context, event))

    def redraw_on_signal(self, context, event):
        self.redraw_on_signal_calls.append((context, event))
        return self.redraw_on_signal_returns

    def cleanup(self):
        self.cleanup_calls += 1


class _FakePanel:
    def __init__(self):
        self.cleared = 0
        self.children: list = []

    def clear(self):
        self.cleared += 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_draw_lazy_instantiates_and_delegates_to_instance():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="rec:editor:1",
        editor_cls=_RecordingEditorCls,
        registry=reg,
        session=session,
    )
    panel = _FakePanel()
    assert w.instance is None
    w.draw(panel)
    assert w.instance is not None
    assert panel.cleared == 1
    assert len(w.instance.draw_calls) == 1
    assert w.instance.draw_calls[0] == (session.context, panel)


def test_draw_renders_placeholder_when_instantiate_fails(monkeypatch):
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="raising:editor:1",
        editor_cls=_RaisingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    panel = _FakePanel()
    placeholder_calls: list[str] = []

    # Stub ui.label so we can detect placeholder creation without a real NiceGUI client
    import haywire.ui.editor.wrapper as wrapper_mod

    class _FakeLabel:
        def classes(self, *a, **k):
            return self

    def _fake_label(text):
        placeholder_calls.append(text)
        return _FakeLabel()

    monkeypatch.setattr(wrapper_mod.ui, "label", _fake_label)

    w.draw(panel)
    assert w.instance is None
    assert panel.cleared == 1
    assert len(placeholder_calls) == 1
    assert "raising:editor:1" in placeholder_calls[0]


def test_draw_captures_runtime_exception_into_error_runtime():
    class _DrawRaisingCls:
        class_identity = SimpleNamespace(
            registry_key="dr:editor:1",
            label="DR",
            default_slot="main",
            opens=None,
        )

        def __init__(self):
            self.wrapper = None

        def draw(self, context, container):
            raise RuntimeError("draw boom")

    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="dr:editor:1",
        editor_cls=_DrawRaisingCls,
        registry=reg,
        session=_make_session(),
    )
    panel = _FakePanel()
    w.draw(panel)
    assert w.state.error_runtime is not None


def test_on_focus_delegates_to_instance():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="rec:editor:1",
        editor_cls=_RecordingEditorCls,
        registry=reg,
        session=session,
    )
    w._instantiate()
    w.on_focus()
    assert w.instance.focus_calls == [session.context]


def test_on_focus_no_op_without_instance():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="missing:editor:1",
        editor_cls=None,
        registry=reg,
        session=_make_session(),
    )
    # Must not raise
    w.on_focus()


def test_on_focus_lazy_instantiates_when_instance_missing():
    """on_focus must lazy-instantiate so editors can update session context
    on first activation (e.g. GraphEditor.on_focus sets
    ``ctx.data[EditState].active_graph``)."""
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="rec:editor:1",
        editor_cls=_RecordingEditorCls,
        registry=reg,
        session=session,
    )
    assert w.instance is None
    w.on_focus()
    assert w.instance is not None
    assert w.instance.focus_calls == [session.context]


def test_on_focus_captures_runtime_exception():
    class _FocusRaisingCls:
        class_identity = SimpleNamespace(
            registry_key="fr:editor:1",
            label="FR",
            default_slot="main",
            opens=None,
        )

        def __init__(self):
            self.wrapper = None

        def on_focus(self, context):
            raise RuntimeError("focus boom")

    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fr:editor:1",
        editor_cls=_FocusRaisingCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    w.on_focus()
    assert w.state.error_runtime is not None


def test_redraw_on_signal_delegates_and_returns_instance_value():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="rec:editor:1",
        editor_cls=_RecordingEditorCls,
        registry=reg,
        session=session,
    )
    w._instantiate()
    w.instance.redraw_on_signal_returns = True
    fake_event = SimpleNamespace()
    assert w.redraw_on_signal(fake_event) is True
    assert w.instance.redraw_on_signal_calls == [(session.context, fake_event)]


def test_redraw_on_signal_returns_false_without_instance():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="missing:editor:1",
        editor_cls=None,
        registry=reg,
        session=_make_session(),
    )
    fake_event = SimpleNamespace()
    assert w.redraw_on_signal(fake_event) is False


def test_redraw_on_signal_captures_runtime_exception_returns_false():
    class _RaisingCls:
        class_identity = SimpleNamespace(
            registry_key="pr:editor:1",
            label="PR",
            default_slot="main",
            opens=None,
        )

        def __init__(self):
            self.wrapper = None

        def redraw_on_signal(self, context, event):
            raise RuntimeError("redraw_on_signal boom")

    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="pr:editor:1",
        editor_cls=_RaisingCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    fake_event = SimpleNamespace()
    assert w.redraw_on_signal(fake_event) is False
    assert w.state.error_runtime is not None


def test_on_signal_delegates_and_returns_none():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="rec:editor:1",
        editor_cls=_RecordingEditorCls,
        registry=reg,
        session=session,
    )
    w._instantiate()
    fake_event = SimpleNamespace()
    assert w.on_signal(fake_event) is None
    assert w.instance.on_signal_calls == [(session.context, fake_event)]


def test_on_signal_noop_without_instance():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="missing:editor:1",
        editor_cls=None,
        registry=reg,
        session=_make_session(),
    )
    # Should not raise even though no instance exists.
    w.on_signal(SimpleNamespace())


def test_on_signal_captures_runtime_exception():
    class _RaisingCls:
        class_identity = SimpleNamespace(
            registry_key="pr:editor:1",
            label="PR",
            default_slot="main",
            opens=None,
        )

        def __init__(self):
            self.wrapper = None

        def on_signal(self, context, event):
            raise RuntimeError("on_signal boom")

    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="pr:editor:1",
        editor_cls=_RaisingCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    w.on_signal(SimpleNamespace())
    assert w.state.error_runtime is not None


def test_repayload_updates_payload_and_binding_id():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        binding_id="__unsaved_3__",
    )
    assert w.editor_binding_id == "fake:editor:1::__unsaved_3__"
    w.repayload("/tmp/saved.haywire")
    assert w._binding_id == "/tmp/saved.haywire"
    assert w.editor_binding_id == "fake:editor:1::/tmp/saved.haywire"


def test_repayload_to_none_removes_suffix():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        binding_id="x",
    )
    w.repayload(None)
    assert w._binding_id is None


# ---------------------------------------------------------------------------
# Task 1: is_dirty state + set_dirty mutator
# ---------------------------------------------------------------------------


def test_state_default_is_not_dirty():
    state = EditorWrapperState()
    assert state.is_dirty is False


def test_set_dirty_updates_state_flag():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    assert w.state.is_dirty is False
    w.set_dirty(True)
    assert w.state.is_dirty is True
    w.set_dirty(False)
    assert w.state.is_dirty is False


def test_set_dirty_coerces_truthy_values_to_bool():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w.set_dirty(1)  # truthy non-bool
    assert w.state.is_dirty is True
    assert isinstance(w.state.is_dirty, bool)


# ---------------------------------------------------------------------------
# Task 2: _slot back-reference
# ---------------------------------------------------------------------------


def test_wrapper_slot_starts_as_none():
    """Until a slot adopts the wrapper via add_binding, _slot is None."""
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    assert w._slot is None


def test_wrapper_cleanup_clears_slot_reference():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    # Simulate slot adoption (slot would do this in add_binding).
    sentinel_slot = object()
    w._slot = sentinel_slot
    assert w._slot is sentinel_slot
    w.cleanup()
    assert w._slot is None


# ---------------------------------------------------------------------------
# Task 3: BaseEditor.handle_close_request default
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402


def _run_async(coro):
    """Run an awaitable synchronously, even when a loop is already running.

    Runs the coroutine in a worker thread with its own fresh event loop —
    bypasses the running loop NiceGUI sometimes leaves attached to the main
    thread during the test session.
    """
    import threading

    box: list = []

    def _runner():
        loop = asyncio.new_event_loop()
        try:
            box.append(("ok", loop.run_until_complete(coro)))
        except BaseException as e:
            box.append(("err", e))
        finally:
            loop.close()

    t = threading.Thread(target=_runner)
    t.start()
    t.join()
    tag, value = box[0]
    if tag == "err":
        raise value
    return value


def test_base_editor_handle_close_request_defaults_to_true():
    """The framework default is 'allow close' — editors override to veto."""
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.identity import EditorIdentity

    class _MinimalEditor(BaseEditor):
        class_identity = EditorIdentity(
            registry_id="close-default",
            registry_key="test:close-default",
            label="Test",
            default_slot="main",
        )

        def draw(self, context, container):
            pass

    editor = _MinimalEditor()
    result = _run_async(editor.handle_close_request())
    assert result is True


# ---------------------------------------------------------------------------
# Task 4: request_close / close / force_close
# ---------------------------------------------------------------------------


def test_request_close_returns_true_when_no_instance():
    """A wrapper with no instance allows close (nothing to ask)."""
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    # No instance yet (lazy)
    assert w._instance is None
    result = _run_async(w.request_close())
    assert result is True


class _ConsentingEditorCls:
    """Stub editor that records handle_close_request calls and returns a
    configurable value."""

    class_identity = SimpleNamespace(
        registry_key="consent:editor:1",
        label="Consent",
        default_slot="main",
        opens=None,
    )

    def __init__(self):
        self.wrapper = None
        self.consent_calls = 0
        self.consent_response = True

    async def handle_close_request(self):
        self.consent_calls += 1
        return self.consent_response


def test_request_close_delegates_to_instance_handle_close_request():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="consent:editor:1",
        editor_cls=_ConsentingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    result = _run_async(w.request_close())
    assert result is True
    assert w._instance.consent_calls == 1


def test_request_close_returns_false_when_editor_vetoes():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="consent:editor:1",
        editor_cls=_ConsentingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    w._instance.consent_response = False
    result = _run_async(w.request_close())
    assert result is False


def test_request_close_allows_when_handle_close_request_raises():
    """A buggy handle_close_request must not strand the user with an
    unclosable tab. Allow close on exception."""

    class _RaisingConsentCls:
        class_identity = SimpleNamespace(
            registry_key="rc:editor:1",
            label="RC",
            default_slot="main",
            opens=None,
        )

        def __init__(self):
            self.wrapper = None

        async def handle_close_request(self):
            raise RuntimeError("buggy editor")

    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="rc:editor:1",
        editor_cls=_RaisingConsentCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    result = _run_async(w.request_close())
    assert result is True
    # Failure is captured into structured state, mirroring draw/on_focus/on_signal/redraw_on_signal.
    assert w.state.error_runtime is not None


class _FakeSlot:
    """Stub slot that records close_tab calls."""

    def __init__(self):
        self.close_calls: list = []

    def close_tab(self, editor_key, binding_id):
        self.close_calls.append((editor_key, binding_id))
        return True


def test_force_close_calls_slot_close_tab():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        binding_id="/tmp/x",
    )
    fake_slot = _FakeSlot()
    w._slot = fake_slot
    w.force_close()
    assert fake_slot.close_calls == [("fake:editor:1", "/tmp/x")]


def test_force_close_no_op_when_no_slot():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    # No slot attached — must not raise
    w.force_close()


def test_close_calls_slot_close_tab_on_consent():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="consent:editor:1",
        editor_cls=_ConsentingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    fake_slot = _FakeSlot()
    w._slot = fake_slot
    closed = _run_async(w.close())
    assert closed is True
    assert len(fake_slot.close_calls) == 1


def test_close_does_not_call_slot_when_editor_vetoes():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="consent:editor:1",
        editor_cls=_ConsentingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    w._instance.consent_response = False
    fake_slot = _FakeSlot()
    w._slot = fake_slot
    closed = _run_async(w.close())
    assert closed is False
    assert fake_slot.close_calls == []


# ---------------------------------------------------------------------------
# Task 5: repayload delegates to slot
# ---------------------------------------------------------------------------


class _RepayloadTrackingSlot:
    """Stub slot recording repayload_tab calls."""

    def __init__(self):
        self.repayload_calls: list = []

    def repayload_tab(self, editor_key, old_payload, new_payload, new_label):
        self.repayload_calls.append((editor_key, old_payload, new_payload, new_label))
        return True

    def close_tab(self, editor_key, binding_id):
        return True


def test_repayload_with_slot_delegates_to_slot_repayload_tab():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        binding_id="__unsaved_3__",
    )
    fake_slot = _RepayloadTrackingSlot()
    w._slot = fake_slot
    w.repayload("/tmp/saved.haywire", new_label="saved.haywire")
    assert fake_slot.repayload_calls == [
        ("fake:editor:1", "__unsaved_3__", "/tmp/saved.haywire", "saved.haywire")
    ]


def test_repayload_without_slot_just_updates_field():
    """Detached wrapper (no slot) — repayload still updates binding_id field
    so unit tests can verify identity changes without a slot."""
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        binding_id="x",
    )
    # No _slot set
    w.repayload("y", new_label="Y")
    assert w._binding_id == "y"
    assert w.label == "Y"


def test_repayload_label_is_optional():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        binding_id="x",
    )
    w.repayload("y")  # no new_label
    assert w._binding_id == "y"


# ---------------------------------------------------------------------------
# Task 6: hot-reload clears is_dirty
# ---------------------------------------------------------------------------


def test_lifecycle_class_reloaded_clears_is_dirty():
    """Hot-reload replaces the instance; in-memory unsaved state is gone
    along with it, so the dirty flag must clear."""
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w.set_dirty(True)
    assert w.state.is_dirty is True

    event = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_RELOADED,
        registry_key="fake:editor:1",
        affected_class=_NewFakeEditorCls,
        library_identity=_FAKE_LIBRARY_IDENTITY,
    )
    w._on_lifecycle_event(event)

    assert w.state.is_dirty is False
