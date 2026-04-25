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
    assert w.payload is None
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
    assert w.binding_id == "fake:editor:1"


def test_wrapper_binding_id_with_payload():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        payload="/tmp/x",
    )
    assert w.binding_id == "fake:editor:1::/tmp/x"


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
        )
    )
    assert w.editor_cls is _NewFakeEditorCls


# ---------------------------------------------------------------------------
# Task 6: Runtime entry points — draw / on_focus / poll
# ---------------------------------------------------------------------------


class _RecordingEditorCls:
    """Editor stub that records calls to draw/on_focus/poll."""

    class_identity = SimpleNamespace(
        registry_key="rec:editor:1",
        label="Rec",
        default_slot="main",
        opens=None,
    )

    def __init__(self):
        self.draw_calls: list = []
        self.focus_calls: list = []
        self.poll_calls: list = []
        self.cleanup_calls = 0
        self.wrapper = None
        self.poll_returns = False

    def draw(self, context, container):
        self.draw_calls.append((context, container))

    def on_focus(self, context):
        self.focus_calls.append(context)

    def poll(self, context, event):
        self.poll_calls.append((context, event))
        return self.poll_returns

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
    on first activation (e.g. GraphEditor.on_focus sets context.active_graph)."""
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


def test_poll_delegates_and_returns_instance_value():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="rec:editor:1",
        editor_cls=_RecordingEditorCls,
        registry=reg,
        session=session,
    )
    w._instantiate()
    w.instance.poll_returns = True
    fake_event = SimpleNamespace()
    assert w.poll(fake_event) is True
    assert w.instance.poll_calls == [(session.context, fake_event)]


def test_poll_returns_false_without_instance():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="missing:editor:1",
        editor_cls=None,
        registry=reg,
        session=_make_session(),
    )
    fake_event = SimpleNamespace()
    assert w.poll(fake_event) is False


def test_poll_captures_runtime_exception_returns_false():
    class _PollRaisingCls:
        class_identity = SimpleNamespace(
            registry_key="pr:editor:1",
            label="PR",
            default_slot="main",
            opens=None,
        )

        def __init__(self):
            self.wrapper = None

        def poll(self, context, event):
            raise RuntimeError("poll boom")

    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="pr:editor:1",
        editor_cls=_PollRaisingCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    fake_event = SimpleNamespace()
    assert w.poll(fake_event) is False
    assert w.state.error_runtime is not None


def test_repayload_updates_payload_and_binding_id():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        payload="__unsaved_3__",
    )
    assert w.binding_id == "fake:editor:1::__unsaved_3__"
    w.repayload("/tmp/saved.haywire")
    assert w.payload == "/tmp/saved.haywire"
    assert w.binding_id == "fake:editor:1::/tmp/saved.haywire"


def test_repayload_to_none_removes_suffix():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        payload="x",
    )
    w.repayload(None)
    assert w.payload is None
    assert w.binding_id == "fake:editor:1"
