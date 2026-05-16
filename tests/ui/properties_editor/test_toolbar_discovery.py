# tests/ui/properties_editor/test_toolbar_discovery.py
"""PropertiesEditor toolbar = registry.get_display_focuses(), sorted by Focus.order."""

from __future__ import annotations

from haywire.core.library.identity import LibraryIdentity
from haywire.ui.panel import BasePanel, PanelRegistry, panel
from haywire.ui.panel.focus import Focus


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


class _LowOrderFocus(Focus):
    id = "library_low_order_focus_test"
    label = "Low"
    icon = "library_books"
    order = 10

    @classmethod
    def available(cls, ctx):
        return True


class _HighOrderFocus(Focus):
    id = "library_high_order_focus_test"
    label = "High"
    icon = "library_books"
    order = 90

    @classmethod
    def available(cls, ctx):
        return True


# Display panels — no actions: annotation, so they appear in the toolbar.
@panel(focus=_LowOrderFocus, label="Low Panel")
class _LowOrderPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(focus=_HighOrderFocus, label="High Panel")
class _HighOrderPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


def _stub_wrapper():
    """Minimal wrapper stand-in — toolbar discovery never reads it."""
    from typing import cast
    from haywire.ui.editor.wrapper import EditorWrapper

    return cast(EditorWrapper, object())


def test_toolbar_empty_registry_yields_no_focuses():
    """With no panels registered, the toolbar is empty."""
    from haybale_studio.editors.properties_editor import PropertiesEditor

    editor = PropertiesEditor(_stub_wrapper())
    focuses = editor._compute_toolbar_focuses(PanelRegistry())
    assert focuses == []


def test_toolbar_includes_library_focus_via_registry():
    """A library-defined focus appears in the toolbar via registry discovery."""
    from haybale_studio.editors.properties_editor import PropertiesEditor

    reg = PanelRegistry()
    reg._register_class(_LowOrderPanel, _FAKE_LIBRARY_IDENTITY)
    editor = PropertiesEditor(_stub_wrapper())
    focuses = editor._compute_toolbar_focuses(reg)
    assert _LowOrderFocus in focuses


def test_toolbar_focuses_are_sorted_by_focus_order():
    from haybale_studio.editors.properties_editor import PropertiesEditor

    reg = PanelRegistry()
    # Register in reverse-order so the discovered set order doesn't trivially match.
    reg._register_class(_HighOrderPanel, _FAKE_LIBRARY_IDENTITY)
    reg._register_class(_LowOrderPanel, _FAKE_LIBRARY_IDENTITY)
    editor = PropertiesEditor(_stub_wrapper())
    focuses = editor._compute_toolbar_focuses(reg)
    low_idx = focuses.index(_LowOrderFocus)  # order 10
    high_idx = focuses.index(_HighOrderFocus)  # order 90
    assert low_idx < high_idx
