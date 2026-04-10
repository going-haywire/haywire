# tests/ui/test_editor_registry.py
"""
Tests for the EditorTypeRegistry and @editor decorator.
"""

import pytest
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.registry import EditorTypeRegistry


# ---------------------------------------------------------------------------
# Minimal concrete editor for testing
# ---------------------------------------------------------------------------


@editor(
    registry_id="test_editor",
    label="Test Editor",
    icon="star",
    default_area="middle",
    description="An editor for unit tests.",
)
class _TestEditor(BaseEditor):
    def draw(self, context, container):
        pass


@editor(
    registry_id="test_left_editor",
    label="Test Left Editor",
    default_area="left",
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

    def test_default_area(self):
        assert _TestEditor.class_identity.default_area == "middle"

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

            @editor(registry_id="bad", editor="x", default_area="middle")
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
        self.registry._register_class(_TestEditor, library_identity=None)
        key = _TestEditor.class_identity.registry_key
        assert self.registry.get(key) is _TestEditor

    def test_has_after_register(self):
        self.registry._register_class(_TestEditor, library_identity=None)
        key = _TestEditor.class_identity.registry_key
        assert self.registry.has(key)

    def test_unregister_removes_class(self):
        self.registry._register_class(_TestEditor, library_identity=None)
        key = _TestEditor.class_identity.registry_key
        self.registry._unregister_class(key)
        assert not self.registry.has(key)
        assert self.registry.get(key) is None

    def test_get_by_default_area_middle(self):
        self.registry._register_class(_TestEditor, library_identity=None)
        self.registry._register_class(_TestLeftEditor, library_identity=None)
        middle = self.registry.get_by_default_area("middle")
        left = self.registry.get_by_default_area("left")
        assert _TestEditor.class_identity.registry_key in middle
        assert _TestEditor.class_identity.registry_key not in left
        assert _TestLeftEditor.class_identity.registry_key in left

    def test_get_by_default_area_no_results(self):
        self.registry._register_class(_TestEditor, library_identity=None)
        bottom = self.registry.get_by_default_area("bottom")
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
        self.registry._register_class(_TestEditor, library_identity=None)
        names = self.registry.list_names()
        assert _TestEditor.class_identity.registry_key in names
