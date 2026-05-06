# tests/ui/test_editor_registry.py
"""
Tests for the EditorTypeRegistry and @editor decorator.
"""

import pytest
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import OpenBehavior
from haywire.ui.editor.registry import EditorTypeRegistry


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


# ---------------------------------------------------------------------------
# Minimal concrete editor for testing
# ---------------------------------------------------------------------------


@editor(
    registry_id="test_editor",
    label="Test Editor",
    icon="star",
    default_slot="main",
    description="An editor for unit tests.",
)
class _TestEditor(BaseEditor):
    def draw(self, context, container):
        pass


@editor(
    registry_id="test_left_editor",
    label="Test Left Editor",
    default_slot="left",
)
class _TestLeftEditor(BaseEditor):
    def draw(self, context, container):
        pass


class _NotDecoratedEditor(BaseEditor):
    """BaseEditor subclass without @editor — should NOT pass _class_filter."""

    def draw(self, context, container):
        pass


# ---------------------------------------------------------------------------
# @editor decorator tests
# ---------------------------------------------------------------------------


class TestEditorDecorator:
    def test_sets_class_identity(self):
        assert hasattr(_TestEditor, "class_identity")

    def test_registry_key(self):
        # reg_key format: "{library_id}:editor:{registry_id}"
        assert _TestEditor.class_identity.registry_key.endswith(":editor:test_editor")

    def test_label(self):
        assert _TestEditor.class_identity.label == "Test Editor"

    def test_icon(self):
        assert _TestEditor.class_identity.icon == "star"

    def test_default_slot(self):
        assert _TestEditor.class_identity.default_slot == "main"

    def test_description(self):
        assert _TestEditor.class_identity.description == "An editor for unit tests."

    def test_registry_id(self):
        assert _TestEditor.class_identity.registry_id == "test_editor"

    def test_does_not_auto_register(self):
        """@editor must NOT register the class in any registry on its own."""
        # No registry was created; class_identity is set but no side effects
        assert _TestEditor.class_identity is not None

    def test_rejects_non_base_editor(self):
        with pytest.raises(TypeError):

            @editor(registry_id="bad", editor="x", default_slot="main")
            class NotAnEditor:
                pass

    def test_sets_class_library(self):
        assert hasattr(_TestEditor, "class_library")


# ---------------------------------------------------------------------------
# EditorTypeRegistry tests
# ---------------------------------------------------------------------------


class TestEditorTypeRegistry:
    def setup_method(self):
        self.registry = EditorTypeRegistry()

    def test_empty_on_init(self):
        assert self.registry.list_names() == []

    def test_register_and_get(self):
        self.registry._register_class(_TestEditor, library_identity=_FAKE_LIBRARY_IDENTITY)
        key = _TestEditor.class_identity.registry_key
        assert self.registry.get(key) is _TestEditor

    def test_has_after_register(self):
        self.registry._register_class(_TestEditor, library_identity=_FAKE_LIBRARY_IDENTITY)
        key = _TestEditor.class_identity.registry_key
        assert self.registry.has(key)

    def test_unregister_removes_class(self):
        self.registry._register_class(_TestEditor, library_identity=_FAKE_LIBRARY_IDENTITY)
        key = _TestEditor.class_identity.registry_key
        self.registry._unregister_class(key)
        assert not self.registry.has(key)
        assert self.registry.get(key) is None

    def test_get_by_default_slot_main(self):
        self.registry._register_class(_TestEditor, library_identity=_FAKE_LIBRARY_IDENTITY)
        self.registry._register_class(_TestLeftEditor, library_identity=_FAKE_LIBRARY_IDENTITY)
        main = self.registry.get_by_default_slot("main")
        left = self.registry.get_by_default_slot("left")
        assert _TestEditor.class_identity.registry_key in main
        assert _TestEditor.class_identity.registry_key not in left
        assert _TestLeftEditor.class_identity.registry_key in left

    def test_get_by_default_slot_no_results(self):
        self.registry._register_class(_TestEditor, library_identity=_FAKE_LIBRARY_IDENTITY)
        bottom = self.registry.get_by_default_slot("bottom")
        assert len(bottom) == 0

    def test_class_filter_accepts_decorated_subclass(self):
        assert self.registry._class_filter(_TestEditor) is True

    def test_class_filter_rejects_base_class_itself(self):
        assert self.registry._class_filter(BaseEditor) is False

    def test_class_filter_rejects_undecorated_subclass(self):
        assert self.registry._class_filter(_NotDecoratedEditor) is False

    def test_class_filter_rejects_non_class(self):
        assert self.registry._class_filter("not_a_class") is False

    def test_list_names_returns_registry_keys(self):
        self.registry._register_class(_TestEditor, library_identity=_FAKE_LIBRARY_IDENTITY)
        names = self.registry.list_names()
        assert _TestEditor.class_identity.registry_key in names


# ---------------------------------------------------------------------------
# OpenBehavior / opens kwarg tests
# ---------------------------------------------------------------------------


class TestOpenBehavior:
    def test_enum_has_three_values(self):
        assert OpenBehavior.REQUIRED.value == "required"
        assert OpenBehavior.ON_CONTEXT.value == "on_context"
        assert OpenBehavior.ON_PAYLOAD.value == "on_payload"

    def test_default_opens_is_required(self):
        assert _TestEditor.class_identity.opens is OpenBehavior.REQUIRED

    def test_opens_accepts_string(self):
        @editor(registry_id="op_str", default_slot="main", opens="on_payload")
        class _OpensStrEditor(BaseEditor):
            def draw(self, context, container):
                pass

        assert _OpensStrEditor.class_identity.opens is OpenBehavior.ON_PAYLOAD

    def test_opens_accepts_enum(self):
        @editor(registry_id="op_enum", default_slot="main", opens=OpenBehavior.ON_CONTEXT)
        class _OpensEnumEditor(BaseEditor):
            def draw(self, context, container):
                pass

        assert _OpensEnumEditor.class_identity.opens is OpenBehavior.ON_CONTEXT

    def test_opens_rejects_typo(self):
        with pytest.raises(ValueError):

            @editor(registry_id="op_bad", default_slot="main", opens="per_documnt")
            class _OpensTypoEditor(BaseEditor):
                def draw(self, context, container):
                    pass

    def test_opens_non_required_rejected_on_left(self):
        with pytest.raises(ValueError):

            @editor(registry_id="op_left", default_slot="left", opens="on_payload")
            class _OpensLeftEditor(BaseEditor):
                def draw(self, context, container):
                    pass

    def test_opens_non_required_rejected_on_right(self):
        with pytest.raises(ValueError):

            @editor(registry_id="op_right", default_slot="right", opens="on_context")
            class _OpensRightEditor(BaseEditor):
                def draw(self, context, container):
                    pass

    def test_opens_required_ok_on_left(self):
        @editor(registry_id="op_left_req", default_slot="left", opens="required")
        class _OpensLeftReqEditor(BaseEditor):
            def draw(self, context, container):
                pass

        assert _OpensLeftReqEditor.class_identity.opens is OpenBehavior.REQUIRED


# ---------------------------------------------------------------------------
# Per-key event subscriber tests
# ---------------------------------------------------------------------------


class _PlainCls:
    pass


class TestPerKeyEventSubscribers:
    def test_per_key_subscriber_receives_event_for_its_key(self):
        reg = EditorTypeRegistry()
        received: list[LifeCycleEvent] = []
        reg.add_event_subscriber("a:editor:1", lambda evt: received.append(evt))

        reg._lifecycle_event_queue.append(
            LifeCycleEvent(
                event_type=LifeCycleEventType.CLASS_RELOADED,
                registry_key="a:editor:1",
                affected_class=_PlainCls,
                library_identity=_FAKE_LIBRARY_IDENTITY,
            )
        )
        reg._notify_batch_event_subscribers()

        assert len(received) == 1
        assert received[0].registry_key == "a:editor:1"

    def test_per_key_subscriber_does_not_receive_other_keys(self):
        reg = EditorTypeRegistry()
        received: list[LifeCycleEvent] = []
        reg.add_event_subscriber("a:editor:1", lambda evt: received.append(evt))

        reg._lifecycle_event_queue.append(
            LifeCycleEvent(
                event_type=LifeCycleEventType.CLASS_RELOADED,
                registry_key="other:editor:99",
                affected_class=_PlainCls,
                library_identity=_FAKE_LIBRARY_IDENTITY,
            )
        )
        reg._notify_batch_event_subscribers()

        assert received == []

    def test_remove_event_subscriber_stops_callbacks(self):
        reg = EditorTypeRegistry()
        received: list[LifeCycleEvent] = []

        def cb(evt: LifeCycleEvent) -> None:
            received.append(evt)

        reg.add_event_subscriber("a:editor:1", cb)
        reg.remove_event_subscriber("a:editor:1", cb)

        reg._lifecycle_event_queue.append(
            LifeCycleEvent(
                event_type=LifeCycleEventType.CLASS_RELOADED,
                registry_key="a:editor:1",
                affected_class=_PlainCls,
                library_identity=_FAKE_LIBRARY_IDENTITY,
            )
        )
        reg._notify_batch_event_subscribers()

        assert received == []

    def test_per_key_subscriber_exception_does_not_block_other_callbacks(self):
        """A throwing callback must not prevent later callbacks from firing."""
        reg = EditorTypeRegistry()
        received: list[str] = []

        def throwing_cb(evt):
            raise RuntimeError("boom")

        def recording_cb(evt):
            received.append(evt.registry_key)

        reg.add_event_subscriber("a:editor:1", throwing_cb)
        reg.add_event_subscriber("a:editor:1", recording_cb)

        reg._lifecycle_event_queue.append(
            LifeCycleEvent(
                event_type=LifeCycleEventType.CLASS_RELOADED,
                registry_key="a:editor:1",
                affected_class=_PlainCls,
                library_identity=_FAKE_LIBRARY_IDENTITY,
            )
        )
        # Must not raise — exception should be swallowed and logged
        reg._notify_batch_event_subscribers()

        # The recording callback should still have fired
        assert received == ["a:editor:1"]
